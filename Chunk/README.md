# Chunked medicinal plant data

Run the chunk generator from the project root:

```powershell
python Chunk\chunk_dataset.py
```

It reads `Data\combined\medicinal_plants_combined.jsonl` and writes one JSON
file per plant into `Chunk\chunks\`, named with its `plant_id`. Each file
contains only that plant's chunk objects. Nested objects and arrays are
flattened into path-labeled lines, with each chunk limited to 6,000 characters.
All source fields are retained across the generated chunks.

The JSON files contain arrays of chunk objects and are compatible with the
recursive JSON loader in `embedding\embed.py`. To regenerate the output, use:

```powershell
python Chunk\chunk_dataset.py --force
```
