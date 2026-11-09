import argparse
from playwright.sync_api import sync_playwright
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "raw" / "shlokas" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--overwrite",
    action="store_true",
    help="allow writing over existing shloka image files",
)
args = parser.parse_args()
if any(OUTPUT_DIR.iterdir()) and not args.overwrite:
    raise FileExistsError(
        f"Shloka images already exist in {OUTPUT_DIR}; pass --overwrite to confirm."
    )

def save_image(response):
    if ".jpg" in response.url:
        name = response.url.split("/")[-1]

        image_path = OUTPUT_DIR / name
        with image_path.open("wb") as f:
            f.write(response.body())
        print("Saved", image_path)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.on("response", save_image)

    page.goto("https://www.medicinalplants.in/sanskritappnuse")

    page.wait_for_timeout(10000)

    browser.close()