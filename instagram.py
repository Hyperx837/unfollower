import asyncio

import aiohttp
from playwright.async_api import Request, async_playwright
from rich.console import Console

import credentials

console = Console()
headers_acquired = asyncio.Event()


class state:
    headers = {}
    session = None
    auth = {
        "username": getattr(credentials, "username", ""),
        "password": getattr(credentials, "password", ""),
    }
    userid = None
    follower_count = 0


def intercept_request(request: Request):
    if "api/v1/friendships/43823686937/following" in request.url:
        state.headers = request.headers
        headers_acquired.set()


async def find_following():
    async with state.session.get(
        f"/friendships/{state.userid}/following/?count={state.follower_count}&max_id=1"
    ) as resp:
        try:
            return await resp.json()
        except Exception as e:
            console.log(e.args)
            exit(1)


async def is_follower(id: str):
    async with state.session.get(
        f"/friendships/{id}/following/?count=1&max_id=1"
    ) as resp:
        (user,) = (await resp.json())["users"]
        if user["pk"] != state.userid:
            console.log(f"user `{user['username']}` isn't following you back")
            return False


async def find_followers():
    users = (await find_following())["users"]
    results = {
        user["username"]: asyncio.create_task(is_follower(user["pk"])) for user in users
    }
    console.log(results.values())
    await asyncio.gather(*results.values())
    console.log(results)
    for user, is_followed in results:
        if not is_followed:
            console.log(f"user `{user}` isn't following you back")


async def set_headers():
    async with async_playwright() as apw:
        browser = await apw.firefox.launch()
        console.log("Browser Launched")
        page = await browser.new_page()
        await page.goto("https://instagram.com/")
        await page.wait_for_selector("input")
        username, passw = await page.query_selector_all("input")
        await username.fill(state.auth["username"])
        await passw.fill(state.auth["password"])
        await page.locator("'Log in'").click()
        await page.locator("'Not Now'").click()
        console.log("Logged in")
        await page.goto("https://instagram.com/carnate_77/following")
        page.on("request", intercept_request)
        await headers_acquired.wait()


async def set_userid():
    async with state.session.get(
        f"/users/web_profile_info/?usernam={state.auth['username']}",
        headers={"X-IG-App-ID": "936619743392459"},
    ) as resp:
        data = await resp.json()
        state.userid = data["data"]["user"]["id"]
        state.follower_count = data["data"]["user"]["edge_followed_by"]


async def main():
    conn = aiohttp.TCPConnector(limit=70)
    state.session = aiohttp.ClientSession(
        base_url="https://www.instagram.com/api/v1", connector=conn
    )

    if not (state.auth["username"] or state.auth["password"]):
        state.auth["username"] = console.input("Enter Your Instagram Username: ")
        state.auth["password"] = console.input("Enter Your Password: ")

    tasks = [asyncio.create_task(set_headers()), asyncio.create_task(set_userid())]
    await asyncio.gather(*tasks)
    state.session.headers = state.headers
    console.log("Headers and UserID acquired")
    await find_followers()
    await state.session.close()
    console.log("Gracefully shutting down")


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        console.log("Interrupt signal recieved. shutting down...")
