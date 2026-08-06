from playwright.sync_api import sync_playwright
import os

os.makedirs("images", exist_ok=True)

def save_image(response):
    if ".jpg" in response.url:
        name = response.url.split("/")[-1]

        try:
            with open(f"images/{name}", "wb") as f:
                f.write(response.body())
            print("Saved", name)
        except:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.on("response", save_image)

    page.goto("https://www.medicinalplants.in/sanskritappnuse")

    page.wait_for_timeout(10000)

    browser.close()