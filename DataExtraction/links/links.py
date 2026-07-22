import random
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


# ==========================================================
# Configuration
# ==========================================================

INPUT_CSV = "../names/names.csv"
OUTPUT_CSV = "links.csv"

SEARCH_URL = (
    "https://www.medicinalplants.in/"
    "ayurvedasearchpage/getayurvedabotanical/pageno/0"
)

BASE_URL = "https://www.medicinalplants.in/"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.medicinalplants.in/ayurvedasearchpage"
}


# ==========================================================
# Create Session
# ==========================================================

session = requests.Session()
session.headers.update(HEADERS)


# ==========================================================
# Read CSV
# ==========================================================

df = pd.read_csv(INPUT_CSV)

# Remove spaces around column names
df.columns = df.columns.str.strip()

if "Botanical correlations" not in df.columns:
    raise Exception(
        f"'Botanical correlations' column not found.\nColumns available: {df.columns.tolist()}"
    )

plant_names = (
    df["Botanical correlations"]
    .dropna()
    .astype(str)
    .str.strip()
    .unique()
)

print(f"\nFound {len(plant_names)} plants.\n")


# ==========================================================
# Search every plant
# ==========================================================

results = []

for plant in tqdm(plant_names):

    try:

        payload = {
            "fname": plant
        }

        response = session.post(
            SEARCH_URL,
            data=payload,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        result = soup.select_one("li.result a")

        if result and result.get("href"):

            detail_url = "https://www.medicinalplants.in/" + result["href"].lstrip("/")

            status = "Found"

        else:

            detail_url = ""

            status = "Not Found"

        results.append({
            "Plant Name": plant,
            "Status": status,
            "Detail URL": detail_url
        })

        print(f"{plant} --> {status}")

        time.sleep(1)

    except Exception as e:

        print(f"\nError while searching {plant}")

        print(e)

        results.append({
            "Plant Name": plant,
            "Status": "Error",
            "Detail URL": ""
        })


# ==========================================================
# Save Results
# ==========================================================

output_df = pd.DataFrame(results)

output_df.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig"
)

print("\n===================================")
print("Finished Successfully!")
print(f"Saved to: {OUTPUT_CSV}")
print("===================================")