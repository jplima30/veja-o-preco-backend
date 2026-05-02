from playwright.sync_api import sync_playwright
import os

try:
    with sync_playwright() as p:
        print("Trying Webkit...")
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto("https://google.com")
        print(f"Success! Title: {page.title()}")
        browser.close()
except Exception as e:
    print(f"Failed Webkit: {e}")
