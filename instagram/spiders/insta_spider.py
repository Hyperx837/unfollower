import asyncio
import webbrowser

import scrapy
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
from rich.console import Console
from scrapy.http import FormRequest, Response
from scrapy_playwright.page import PageMethod

console = Console()


def export_page(response: Response):
    print(response.body, file=open("output.html", "w"))
    console.log(response.url)
    webbrowser.open("output.html")


class InstaSpider(scrapy.Spider):
    name = "insta"
    allowed_domains = ["instagram.com"]

    # async def get_cookies(self):
    #     async with async_playwright() as p:
    #         browser = await p.firefox.launch(headless=False)
    #         page = await browser.new_page()
    #         await page.goto("https://instagram.com/")
    #         username, passw = await page.query_selector_all("input")
    #         await username.fill("username")
    #         await passw.fill("password")
    #         await page.locator("'Log in'").click()
    #         return await page.context.cookies()

    def get_cookies(self):
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=False)
            page = browser.new_page()
            page.goto("https://instagram.com/")
            username, passw = page.query_selector_all("input")
            username.fill("username")
            passw.fill("password")
            page.locator("'Log in'").click()
            return page.context.cookies()

    async def get_followers(self):
        self.cookies = await self.get_cookies()
        console.log(self.cookies)

    def start_requests(self):
        from instagram.utils import loop

        cookies = self.get_cookies()
        print(cookies)
        # loop.create_task(self.get_followers())
        # while True:
        #     if hasattr(self, "cookies"):
        #         break

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
        }
        yield scrapy.Request(
            "https://google.com/login",
            self.parse,
            headers=headers,
            meta={
                "playwright": True,
                "playwright_page_methods": [PageMethod("wait_for_selector", "input")],
            },
        )

    def parse(self, response: Response):
        formdata = {"username": "username", "password": "password"}
        yield FormRequest.from_response(
            response,
            formdata=formdata,
            # clickdata={"name": "commit"},
            meta={"playwright": True},
            callback=export_page,
        )
