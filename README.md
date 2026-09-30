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

- **Normalized plant dataset:** DataExtraction/normalized/plants.jsonl — Canonical plant records grouped using the source `xplant_id` extracted from authoritative plant detail URLs. Each canonical plant has a deterministic `plant_id`; source URLs, source record IDs, and raw/source values are retained for provenance. Produced by `DataExtraction/normalize_plants.py` and checked by `DataExtraction/normalized/validate_normalized.py`.

- **Semantic plant chunks:** DataExtraction/chunks/ — JSON chunks produced by `DataExtraction/chunk_plants.py`, with `DataExtraction/chunks/index.json` mapping each plant to its chunks. Plant data is split into meaningful semantic sections while preserving semantic boundaries: `identification`, `botanical_synonyms`, `vernacular_names`, `systems_of_medicine`, `bibliography`, `distribution`, and `images`. Every chunk has a deterministic unique `chunk_id` and retains the corresponding `plant_id`, so all chunks for the same plant remain linked. Chunk metadata and provenance are preserved. The chunker does not arbitrarily split text by character count; structured sections are split only at valid semantic boundaries where refinement is needed.

- **Chunk validation:** DataExtraction/validate_chunks.py — Validates chunk IDs, plant IDs, metadata consistency, content, provenance, coverage, and index integrity. The current verified dataset contains 951 canonical plants and 6,290 total chunks, with validation status **PASS**; these counts may change if the dataset is regenerated.

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
python DataExtraction/chunk_plants.py
python DataExtraction/validate_chunks.py
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
