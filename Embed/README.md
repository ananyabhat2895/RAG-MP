# ChromaDB embeddings

Create persistent ChromaDB vectors for the plant-specific chunks:

```powershell
python Embed\embed_chunks.py
```

The script reads every JSON file in `Chunk\chunks\`, validates that chunks
match their filename's `plant_id`, and upserts them into the `medicinal_plants`
collection in `Embed\chroma_db\`. It uses Ollama's `qwen3-embedding:0.6b`
embedding model. Unchanged chunks are skipped on subsequent runs.

Options are available for custom paths or collection names:

```powershell
python Embed\embed_chunks.py --chunks Chunk\chunks --vector-db Embed\chroma_db --collection medicinal_plants
```
