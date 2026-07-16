import pandas as pd
import re

# ============================================
# Load CSV
# ============================================

df = pd.read_csv("identity.csv")

# ============================================
# Define column names
# ============================================

drug_col = "Ref. Drug Name"
botanical_col = "Botanical correlations"
status_col = "Status of correlation"
discussion_col = "Discussions on its identity by experts with reference"
reference_col = "References"

# ============================================
# Clean all text columns
# ============================================

text_columns = [
    drug_col,
    botanical_col,
    status_col,
    discussion_col,
    reference_col
]

for col in text_columns:
    if col in df.columns:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.replace(r'[\r\n\t]+', ' ', regex=True)   # Remove newlines/tabs
            .str.replace(r'\s+', ' ', regex=True)          # Collapse multiple spaces
            .str.replace('""', '"', regex=False)          # Fix double quotes
            .str.strip()
        )

# ============================================
# Remove rows with missing botanical names
# ============================================

df = df[df[botanical_col] != ""]

# ============================================
# Remove rows where BOTH status and discussion
# are empty
# ============================================

df = df[
    ~(
        (df[status_col] == "") &
        (df[discussion_col] == "")
    )
]

# ============================================
# Remove placeholder values
# ============================================

placeholder_values = {
    "?",
    "-",
    "n/a",
    "na",
    "none",
    "null"
}

status_placeholder = df[status_col].str.lower().isin(placeholder_values)
discussion_placeholder = df[discussion_col].str.lower().isin(placeholder_values)

# Remove rows where BOTH fields contain only placeholders
df = df[~(status_placeholder & discussion_placeholder)]

# ============================================
# Print available statuses
# ============================================

print("\nAvailable Statuses:\n")
print(df[status_col].value_counts(dropna=False))

# ============================================
# Remove unwanted correlation statuses
# ============================================

remove_status = [
    "Suggested Source",
    "Substituted source"
]

df = df[
    ~df[status_col]
    .str.lower()
    .isin([s.lower() for s in remove_status])
]

# ============================================
# Remove duplicate entries
# ============================================

df = df.drop_duplicates(
    subset=[
        drug_col,
        botanical_col
    ]
)

# ============================================
# Reset index
# ============================================

df = df.reset_index(drop=True)

# ============================================
# Save cleaned dataset
# ============================================

output_file = "identity_cleaned.csv"

df.to_csv(
    output_file,
    index=False,
    encoding="utf-8-sig"
)

# ============================================
# Summary
# ============================================

print("\n========== CLEANING SUMMARY ==========")
print(f"Final rows: {len(df)}")
print(f"Output saved as: {output_file}")
print("======================================")