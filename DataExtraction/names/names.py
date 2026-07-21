import pandas as pd

# ==========================
# Input & Output filenames
# ==========================
INPUT_FILE = "identity.csv"
OUTPUT_FILE = "names.csv"

# ==========================
# Load CSV and extract column
# ==========================
df = pd.read_csv(INPUT_FILE)

# Extract 'Botanical correlations' column
botanical_data = df[["Botanical correlations"]]

# Remove rows with missing values
botanical_data = botanical_data.dropna()

# Save
botanical_data.to_csv(OUTPUT_FILE, index=False)

print(f"Extracted {len(botanical_data)} botanical correlations to '{OUTPUT_FILE}'")