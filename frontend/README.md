# RAG-MP frontend

This React/Vite chat UI sends questions to the FastAPI RAG backend. During
local development, Vite proxies `/api/rag-query` to the backend's `POST /chat`
endpoint at `http://127.0.0.1:8000`.

Run the Python backend first, then from this folder install and start the
frontend:

```powershell
npm ci
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. To use a
different backend URL, set `VITE_RAG_API_URL` in a frontend `.env` file.
If calling a separately hosted backend directly, configure its CORS policy to
allow the frontend's origin.

See the [root README](../README.md#run-the-complete-application-locally) for
full setup instructions, including Python, Ollama, and ChromaDB.
