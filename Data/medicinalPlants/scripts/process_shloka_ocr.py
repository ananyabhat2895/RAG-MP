import argparse
import os
import re

base_folder = os.path.dirname(os.path.abspath(__file__))
data_root = os.path.dirname(base_folder)
input_folder = os.path.join(data_root, "raw", "shlokas", "images")
combined_path = os.path.join(data_root, "raw", "shlokas", "combined_raw.txt")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--overwrite",
    action="store_true",
    help="replace the existing combined OCR text",
)
args = parser.parse_args()
if os.path.exists(combined_path) and not args.overwrite:
    raise FileExistsError(
        f"Refusing to replace {combined_path}; pass --overwrite to confirm."
    )
if not os.path.isdir(input_folder):
    raise FileNotFoundError(f"Shloka image directory not found: {input_folder}")
image_files = [
    name
    for name in os.listdir(input_folder)
    if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
]
if not image_files:
    raise ValueError(f"No supported shloka images found in {input_folder}")

import easyocr
reader = easyocr.Reader(["en"])

# Clear previous output
with open(combined_path, "w", encoding="utf-8") as f:
    pass


for file_name in sorted(os.listdir(input_folder)):
    if not file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        continue

    image_path = os.path.join(input_folder, file_name)
    result = reader.readtext(image_path, detail=0)

    clean_words = []

    for line in result:
        # Split OCR line into individual words
        words = line.split()

        for word in words:
            # Remove punctuation at the beginning/end
            word = word.strip(".,;:!?()[]{}\"'")

            # Keep only proper English words
            # Allows letters, apostrophes and hyphens
            if re.fullmatch(r"[A-Za-z]+(?:['-][A-Za-z]+)*", word):
                clean_words.append(word)

    with open(combined_path, "a", encoding="utf-8") as combined_file:
        heading = os.path.splitext(file_name)[0]
        combined_file.write(f"=== {heading} ===\n")
        combined_file.write(" ".join(clean_words))
        combined_file.write("\n\n")

    print(f"Processed: {file_name}")

print(f"Done! Combined OCR saved in: {combined_path}")