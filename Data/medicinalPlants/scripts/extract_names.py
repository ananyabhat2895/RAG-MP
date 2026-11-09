import argparse
import pandas as pd
from pathlib import Path

# ==========================
# Input & Output filenames
# ==========================
ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "raw" / "names" / "identity.csv"
OUTPUT_FILE = ROOT / "raw" / "names" / "names.csv"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--overwrite",
    action="store_true",
    help="replace the existing names.csv",
)
args = parser.parse_args()
if OUTPUT_FILE.exists() and not args.overwrite:
    raise FileExistsError(
        f"Refusing to replace {OUTPUT_FILE}; pass --overwrite to confirm."
    )

# ==========================
# Load CSV and extract column
# ==========================
df = pd.read_csv(INPUT_FILE)

# Extract 'Botanical correlations' column
botanical_data = df[["Botanical correlations"]]

# Remove rows with missing values
botanical_data = botanical_data.dropna()
if botanical_data.empty:
    raise ValueError(f"No botanical correlations found in {INPUT_FILE}; output was not changed.")

# Save
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
botanical_data.to_csv(OUTPUT_FILE, index=False)

print(f"Extracted {len(botanical_data)} botanical correlations to '{OUTPUT_FILE}'")