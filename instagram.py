import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Literal

import aiohttp
from playwright.async_api import Request, async_playwright
from rich.console import Console

import credentials

console = Console()
headers_acquired = asyncio.Event()


@dataclass
class state:
    userid: str
    session: aiohttp.ClientSession
    headers: dict
    following_count: int
    follower_count: int
    user: str = credentials.username
    passw: str = credentials.password


def is_set_method():
    """there are 2 methods to fetch the people who doesn't follow you back
        1.  go through everyone in the following list and check whether that person
            follows you
        2.  get the intersection of the following and followers list

    the second method sounds pretty good until you consider the number of followers.
    so this function will determine whether the first or the second method will be
    used. it is important to notice that no matter the method, you have do get the
    following accounts. what I've noticed is that it is possible to check whether
    to download the list or not based on how much of a fraction is following you.
    and if you have somewhere around 500 followers, you could use."""


def intercept_request(request: Request):
    if f"api/v1/friendships/{state.userid}/following" in request.url:
        state.session.headers.update(request.headers)
        headers_acquired.set()


async def fetch(target: Literal["following"] | Literal["follower"]):
    if target == "following":
        url = f"/api/v1/friendships/{state.userid}/following/?count={state.following_count}&max_id=1"

    elif target == "follower":
        url = f"/api/v1/friendships/{state.userid}/followers/?count={state.follower_count}"
    else:
        ValueError("`target` should be either 'following' or 'follower'")

    async with state.session.get(url) as resp:
        if resp.status == 429:
            console.log(
                "[red]You have been making too many requests in a short amount of time, try again later."
            )
            exit()

        try:
            return (await resp.json())["users"]

        except KeyError:
            console.log("Unable to make contact right now. try again later")
            await shutdown()

        except Exception as e:
            console.log(e.args)
            await shutdown(1)


async def is_follower(id: str):
    async with state.session.get(
        f"/api/v1/friendships/{id}/following/?count=1&max_id=1"
    ) as resp:
        (user,) = (await resp.json())["users"]
        if user["pk"] != state.userid:
            return False


async def find_bastards():
    following = {user["username"] for user in await fetch("following")}
    followers = {user["username"] for user in await fetch("follower")}
    bastards = following - followers
    for user in bastards:
        console.log(f"user `{user}` isn't following you back")

    console.log(f"[blue]Which makes it a total of {len(bastards)} bastards")
    json.dump(
        {"followers": list(followers), "following": list(following)},
        fp=open(f"{state.user}.json", "w"),
    )


async def set_headers():
    async with async_playwright() as apw:
        browser = await apw.firefox.launch(headless=False)
        console.log("Browser Launched")
        page = await browser.new_page()
        await page.goto("https://instagram.com/")
        await page.wait_for_selector("input")
        username, passw = await page.query_selector_all("input")
        await username.fill(state.user)
        await passw.fill(state.passw)
        await page.locator("'Log in'").click()
        await page.locator("'Not Now'").click()
        console.log("Logged in")
        await page.goto(f"https://instagram.com/{state.user}/following")
        page.on("request", intercept_request)
        await headers_acquired.wait()


async def set_userid():
    async with state.session.get(
        f"/api/v1/users/web_profile_info/?username={state.user}",
        headers={"X-IG-App-ID": "936619743392459"},
    ) as resp:
        data = await resp.json()
        state.userid = data["data"]["user"]["id"]
        state.following_count = data["data"]["user"]["edge_follow"]["count"]
        state.follower_count = data["data"]["user"]["edge_followed_by"]["count"]


async def main():
    conn = aiohttp.TCPConnector(limit=70)
    state.session = aiohttp.ClientSession(
        base_url="https://www.instagram.com", connector=conn
    )

    if not (state.user or state.passw):
        state.user = console.input("Enter Your Instagram Username: ")
        state.passw = console.input("Enter Your Password: ")

    tasks = [set_userid(), set_headers()]
    await asyncio.gather(*tasks)
    console.log("Headers and UserID acquired")
    await find_bastards()
    await shutdown()


async def shutdown(ext_code: int = 0):
    with console.status(
        f"[bold steel_blue]Terminating all pending tasks...",
        spinner="dots12",
    ):
        await state.session.close()
        pending = asyncio.all_tasks()
        [task.cancel() for task in pending]

    if ext_code == 0:
        console.log("[green]Gracefully shutting down...")
        sys.exit()

    else:
        console.log("[red]Shutting down...")
        sys.exit(ext_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        console.log("Interrupt signal recieved. shutting down...")
