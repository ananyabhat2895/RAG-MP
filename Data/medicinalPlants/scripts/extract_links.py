import argparse
import csv
import random
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


# ==========================================================
# Configuration
# ==========================================================

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "raw" / "names" / "names.csv"
OUTPUT_CSV = ROOT / "raw" / "links" / "links.csv"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--overwrite",
    action="store_true",
    help="replace the existing links.csv",
)
parser.add_argument(
    "--allow-fewer",
    action="store_true",
    help="allow replacing links.csv with fewer records",
)
args = parser.parse_args()
if OUTPUT_CSV.exists() and not args.overwrite:
    raise FileExistsError(
        f"Refusing to replace {OUTPUT_CSV}; pass --overwrite to confirm."
    )

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
if len(plant_names) == 0:
    raise ValueError(f"No plant names found in {INPUT_CSV}; output was not changed.")

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

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
if not any(result["Status"] == "Found" for result in results):
    raise ValueError("No plant links were found; the existing links file was not changed.")
if OUTPUT_CSV.exists() and not args.allow_fewer:
    with OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        existing_count = sum(1 for _ in csv.DictReader(handle))
    if len(results) < existing_count:
        raise ValueError(
            f"Refusing to replace {existing_count} link rows with only "
            f"{len(results)}; pass --allow-fewer to confirm."
        )
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