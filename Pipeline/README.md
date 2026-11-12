# RAG backend

The FastAPI backend in `medicinal_plants_rag.py` loads the existing ChromaDB
collection from the repository root and serves the React frontend's questions.
It uses Ollama for query embeddings and answer generation; the current model
settings are `qwen3-embedding:0.6b` and `qwen2.5:3b`.

## Run the API

From the repository root, install the Python requirements if you have not
already done so:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r Pipeline\requirements.txt
```

Make sure Ollama is running and both configured models are available:

```powershell
ollama pull qwen3-embedding:0.6b
ollama pull qwen2.5:3b
```

Start the API:

```powershell
python Pipeline\medicinal_plants_rag.py
```

The health endpoint is `http://127.0.0.1:8000/health`; API docs are available
at `http://127.0.0.1:8000/docs`. The chat endpoint accepts a JSON body such as
`{"question":"What are the medicinal uses of neem?"}` at `POST /chat`.

For instructions to start the frontend and run both services together, see
the [root README](../README.md#run-the-complete-application-locally).
