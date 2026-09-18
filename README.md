RAG-MP
======

DataExtraction — Brief overview
-------------------------------

This project extracts plant identity information, detail pages, and shloka images/text from medicinalplants.in and related sources. Below is a concise description of the datasets produced and how they are created.

- **Identity CSV:** DataExtraction/names/identity.csv — Raw table scraped from the Sanskrit authentication site. Contains full rows (e.g., `Ref. Drug Name`, `Botanical correlations`, `Status of correlation`, `Discussions on its identity by experts`, `References`). Produced by `DataExtraction/names/extract.py` (Playwright DOM scraping of an iframe and pagination).

- **Names CSV:** DataExtraction/names/names.csv — Extracted `Botanical correlations` column (one plant name per row). Produced by `DataExtraction/names/names.py` which reads `identity.csv` and writes the filtered column.

- **Search results (links):** DataExtraction/links/links.csv — For each plant name: `Status` (Found / Not Found / Error) and `Detail URL` (first matching result). Produced by `DataExtraction/links/links.py` which posts plant names to the site search endpoint and parses the HTML response.

- **Parsed plant details (JSON):** DataExtraction/parser/plant_details.json — Structured output for each plant detail page including headings, botanical synonyms, vernacular names, bibliography, distribution, image URLs, and source URL. Produced by `DataExtraction/parser/parser.py` which requests each `Detail URL` and parses it with BeautifulSoup.

- **Parsed plant details (CSV):** DataExtraction/parser/plant_details.csv — Flattened CSV export of the JSON results for spreadsheet analysis. Also produced by `DataExtraction/parser/parser.py` (conversion/flattening step).
- **Normalized plant dataset:** DataExtraction/normalized/plants.jsonl — Canonical plant-level records grouped only by the xplant_id extracted from authoritative plant detail URLs. Original source rows, URLs, and raw values are retained.

- **Shlokas images:** DataExtraction/shlokas/images/ — Captured page image files saved by `DataExtraction/shlokas/parser.py` using Playwright to listen to network responses while visiting the shloka page.

- **Shlokas OCR text:** DataExtraction/shlokas/text/ — Per-image `.txt` files produced by `DataExtraction/shlokas/ocr_parser.py`. The script runs EasyOCR on each image, filters lines containing Latin letters, and writes text files.

How to regenerate
------------------
Run the scripts (from project root) in this order to reproduce the extracted data:

```bash
python DataExtraction/names/extract.py
python DataExtraction/names/names.py
python DataExtraction/links/links.py
python DataExtraction/parser/parser.py
python DataExtraction/normalize_plants.py
python DataExtraction/normalized/validate_normalized.py
python DataExtraction/shlokas/parser.py
python DataExtraction/shlokas/ocr_parser.py
```

Dependencies
------------
- Python packages: `pandas`, `requests`, `beautifulsoup4`, `playwright`, `tqdm`, `easyocr`.
- Playwright requires browser install: `playwright install` (after `pip install playwright`).

Contact / Notes
---------------
If you want a more detailed table of columns, field mappings, or improvements (rate limiting, retries, headless option, output normalization), say which part to expand.
