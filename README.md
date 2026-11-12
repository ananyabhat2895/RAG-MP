# RAG-MP application

## Run the complete application locally

The application has a React/Vite chat frontend, a FastAPI RAG backend, an
existing ChromaDB collection, and Ollama for local embeddings and answer
generation. The backend uses the existing database; you do not need to
re-chunk the data or recreate embeddings to run the app.

### Prerequisites

- Python 3.11 or later
- Node.js and npm
- Ollama installed and running
- The existing ChromaDB directory in the repository root

The current backend configuration uses `qwen3-embedding:0.6b` for query
embeddings and `qwen2.5:3b` for answer generation. Pull them once if they are
not already available:

```powershell
ollama pull qwen3-embedding:0.6b
ollama pull qwen2.5:3b
```

Ollama Desktop normally starts its service automatically. Run `ollama serve`
only if Ollama is not already running; otherwise it may report that port
11434 is already in use.

### 1. Set up and start the Python backend

From the repository root, create a virtual environment and install the
backend requirements:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Pipeline\requirements.txt
```

Start the RAG API in this terminal:

```powershell
python Pipeline\medicinal_plants_rag.py
```

The API listens on `http://127.0.0.1:8000`. Check that it is ready at
`http://127.0.0.1:8000/health`; interactive API documentation is at
`http://127.0.0.1:8000/docs`.

### 2. Install and start the frontend

Open a second PowerShell terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. The Vite
development proxy forwards chat requests to the Python API. The frontend
submits questions to `POST /chat` through that proxy, and displays the answer
and human-readable plant/section labels returned by the backend.

If the backend is unavailable, the chat displays a connection error. Start
both the Ollama service and Python API, then retry. Stop the frontend and API
with Ctrl+C in their respective terminals.

The frontend API URL can be overridden with `VITE_RAG_API_URL` in a frontend
environment file. For a directly hosted backend, configure its CORS origins
to include the frontend's origin.

## Data extraction and final CSV pipeline

This guide covers the workflow in order: install the Python dependencies,
refresh medicinal-plant data from the website, validate and normalize it, then
combine it with the enriched dataset to produce the CSV for later chunking.
Run commands from the repository root in PowerShell.

## 1. Set up Python and install dependencies

Use Python 3.10 or later. Create and activate a virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install the libraries used by the medicinal-plant web extraction scripts:

```powershell
python -m pip install pandas requests beautifulsoup4 tqdm playwright
python -m playwright install chromium
```

The identity and shloka image extractors use a visible Chromium browser.
Approve any browser prompts and follow the website's access rules. OCR is
optional and is not required to generate the plant or combined CSVs. To run
the optional OCR step, install EasyOCR separately:

```powershell
python -m pip install easyocr
```

## 2. Know which existing inputs are used

The normal web refresh uses the saved botanical names list at
`Data/medicinalPlants/raw/names/names.csv` as its search terms. It refreshes
the links and plant details from the website; it does not refresh the identity
table unless you explicitly request that in step 3. The final merge also uses
the existing enriched dataset at
`Data/data-analysis/processed/enriched_plants_combined.jsonl`. You do not need
to check whether generated output files exist before running the pipeline.

## 3. Extract and normalize medicinal-plant data

Run the domain pipeline with its web-extraction option:

```powershell
python Data\medicinalPlants\run_pipeline.py --extract-web
```

This command runs the following steps in order:

1. Search the website for each botanical name in the existing names CSV and
   write search results to `Data/medicinalPlants/raw/links/links.csv`.
2. Fetch and parse the linked plant detail pages into
   `Data/medicinalPlants/raw/parser/`.
3. Normalize the extracted plant records into
   `Data/medicinalPlants/normalized/plants.jsonl`.
4. Validate the normalized records.
5. Rebuild the plant CSV, enriched CSV, and final combined outputs (steps 4
   through 6 below).

This command always refreshes and overwrites the existing links, parsed
details, normalized dataset, and generated CSV/combined output files; no
pre-run file-existence check or extra overwrite flag is needed. A successful
but smaller scrape also replaces the old records. Empty or wholly failed
extractions still stop the pipeline so a temporary website failure does not
replace good data with an empty dataset.

By default, the pipeline uses the existing names list. To also re-scrape the
identity table and replace the names list before searching for detail pages,
run:

```powershell
python Data\medicinalPlants\run_pipeline.py --extract-web --refresh-identity-names
```

This overwrites `identity.csv` and `names.csv` too. The refreshed identity
source has fewer entries than the preserved names list, so this option can
reduce the number of plants searched; use the default command if you want to
keep the current list of names.

## 4. Use the existing enriched dataset

The final merge uses
`Data/data-analysis/processed/enriched_plants_combined.jsonl`, which is
already in the repository. It includes the available IMPPAT and SEPASAL
enrichment fields. The original raw IMPPAT and SEPASAL source datasets are not
available in this project, and this workflow does not download or fabricate
them. Therefore, re-running the web extraction does not regenerate the
enrichment itself.

If you already have valid raw IMPPAT and SEPASAL inputs, the analysis scripts
are in `Data/data-analysis/scripts/`; see their `--help` output before running
them. Once the processed enriched JSONL is available, export and merge it
with the current normalized medicinal-plant records using:

```powershell
python Data\data-analysis\run_pipeline.py
```

This analysis-folder runner does not scrape or rerun enrichment; it rebuilds
the exports and combined dataset from the two processed JSONL inputs.

## 5. Final CSV for later chunking

The web-extraction command in step 3 already runs validation and regenerates
these outputs. The final CSV intended as the input to a later chunking step is:

```text
Data/combined/medicinal_plants_combined.csv
```

Other generated files are:

- `Data/medicinalPlants/csv/medicinal_plants.csv` — normalized medicinal
  plants.
- `Data/data-analysis/csv/enriched_plants.csv` — the existing enriched
  records.
- `Data/combined/medicinal_plants_combined.jsonl` — lossless combined records.
- `Data/combined/merge_report.csv` — input, match, unmatched, ambiguous, and
  final record counts.

To rebuild the exports and final combined files later without scraping (this
also overwrites existing generated outputs), run:

```powershell
python Data\run_data_pipeline.py --force
```

The merge tries unique plant IDs first, then exact normalized botanical names,
then verified botanical synonyms. Ambiguous or unmatched records are retained
instead of being merged speculatively. The combined CSV keeps the original
medicinal and enriched records in separate JSON-encoded columns so their
fields are not lost. Nested cells can be large; JSONL is the lossless
alternative if a spreadsheet application cannot handle a CSV cell.

This pipeline prepares data for chunking but does **not** create chunks or
embeddings. The preserved shloka assets are images and OCR text, not verified
Sanskrit shloka records linked to individual plants, so they are not added as
plant records to the combined CSV.
