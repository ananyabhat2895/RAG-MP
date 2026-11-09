# Data workspace

This folder is a copy-based workspace for the existing plant catalogue and
the available IMPPAT/SEPASAL enriched output. The original `DataExtraction`
and `data-analysis` folders are left untouched.

## Layout

- `medicinalPlants/raw/` contains copied links, names, parsed plant details,
  shloka images, and the existing OCR text.
- `medicinalPlants/normalized/plants.jsonl` is the copied canonical plant
  dataset, one JSON object per line.
- `medicinalPlants/csv/medicinal_plants.csv` is generated from that JSONL.
- `data-analysis/processed/enriched_plants_combined.jsonl` is the copied
  IMPPAT + SEPASAL dataset. It already contains canonical plant fields,
  `imppat`, and `sepasal_medicinal_uses`.
- `data-analysis/csv/enriched_plants.csv` is generated from the enriched JSONL.
- `combined/` contains lossless combined JSONL/CSV exports and a count report.
- `data-analysis/raw/IMPPAT/` and `data-analysis/raw/SEPASAL/` are reserved
  for source datasets. No raw IMPPAT or SEPASAL source files were available
  to copy, so these directories are empty.
- `data-analysis/reports/` contains copied analysis and validation reports.

The combined records keep each complete input under `medicinal_plants` and
`data_analysis` so overlapping fields cannot overwrite one another. Matching
uses plant ID first, then exact normalized botanical name, then an explicitly
listed botanical synonym. Ambiguous candidates are retained separately and
reported rather than merged.

The copied shloka material consists of image files and `combined_raw.txt`.
The existing OCR process filters to English-letter words; it is not verified
Sanskrit text and was not converted into shloka records.

## Generate exports

From the project root, run:

```powershell
python Data\run_data_pipeline.py
```

The script does not scrape websites or regenerate enrichment. It reads only
the copied normalized and enriched JSONL files. It refuses to overwrite
generated output files by default. To regenerate them after a prior run:

```powershell
python Data\run_data_pipeline.py --force
```

Nested values are stored as JSON strings in CSV cells. Some cells are larger
than Python's default CSV field limit; Python readers may need to increase
`csv.field_size_limit`. Spreadsheet applications may also impose cell-size
limits, so JSONL is the lossless format for the full nested records.

The copied normalizer refuses to replace `normalized/plants.jsonl` without
`--overwrite`, and it will not write a zero-record result.

## Run a domain pipeline

To validate the current plant dataset and rebuild the CSV exports without
scraping:

```powershell
python Data\medicinalPlants\run_pipeline.py
```

To refresh links and plant details from the website using the existing
`raw/names/names.csv`:

```powershell
python Data\medicinalPlants\run_pipeline.py --extract-web
```

This refreshes website links and plant details, then overwrites the existing
links, parsed details, normalized dataset, and generated CSV/combined outputs.
It does not check whether those output files already exist. A smaller
successful result replaces the prior data; empty or wholly failed extraction
results are still rejected.

By default, the current names CSV is retained. To also refresh
`identity.csv` and regenerate/overwrite `names.csv` before extracting plant
details, run:

```powershell
python Data\medicinalPlants\run_pipeline.py --extract-web --refresh-identity-names
```

The refreshed identity source has fewer entries than the preserved names
list, so refreshing it can reduce the plants searched.

To separately recapture the shloka-page images and refresh the OCR text:

```powershell
python Data\medicinalPlants\run_pipeline.py --extract-shlokas
```

These are preserved as image/OCR assets; they are not currently linked to
individual plants and are not represented as verified shloka records in the
combined CSV.

The analysis-folder pipeline exports the existing enriched dataset and
rebuilds the final combined CSV without regenerating the enrichment:

```powershell
python Data\data-analysis\run_pipeline.py
```

The final CSV is an export for later chunking; this pipeline does not create
chunks.

Copied enrichment scripts are under `data-analysis/scripts/`. The enrichment
and reprocessing scripts require original IMPPAT/SEPASAL inputs that are not
present in this workspace; their updated defaults point to the reserved
`data-analysis/raw/` directories and fail clearly if required inputs are
missing.
