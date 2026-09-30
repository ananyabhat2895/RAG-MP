"""Create deterministic semantic chunks from normalized plant records."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "normalized" / "plants.jsonl"
OUTPUT_DIR = ROOT / "chunks"
INDEX_PATH = OUTPUT_DIR / "index.json"

# These are only split triggers. Records are always split at complete semantic
# units, never at a character offset.
DEFAULT_MAX_CONTENT_CHARS = 6000
LARGE_SECTION_MAX_CONTENT_CHARS = 2500
LARGE_SECTIONS = {"vernacular_names", "bibliography", "distribution"}


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def non_empty(value: Any) -> bool:
    return value not in (None, "", [], {}, ())


def render_value(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(
            f"{clean(key)}: {render_value(item)}"
            for key, item in value.items()
            if non_empty(item)
        )
    if isinstance(value, list):
        return "; ".join(render_value(item) for item in value if non_empty(item))
    return clean(value)


def render_entry(entry: Any) -> str:
    if isinstance(entry, dict):
        return "; ".join(
            f"{clean(key)}: {render_value(value)}"
            for key, value in entry.items()
            if non_empty(value)
        )
    return render_value(entry)


def split_units(
    units: Iterable[str],
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    current_size = 0
    for unit in units:
        unit = clean(unit)
        if not unit:
            continue
        additional = len(unit) + (1 if current else 0)
        if current and current_size + additional > max_content_chars:
            groups.append("\n".join(current))
            current = []
            current_size = 0
        current.append(unit)
        current_size += len(unit) + (1 if len(current) > 1 else 0)
    if current:
        groups.append("\n".join(current))
    return groups


def section_units(plant: dict[str, Any], section: str) -> list[str]:
    if section == "identification":
        fields = [
            ("Plant name", plant.get("plant_name")),
            ("Botanical name", plant.get("botanical_name")),
            ("Botanical authority", plant.get("botanical_authority")),
            ("Family", plant.get("family")),
            ("Source xplant ID", plant.get("source_xplant_id")),
        ]
        return [
            "\n".join(f"{label}: {clean(value)}" for label, value in fields if non_empty(value))
        ]
    if section == "botanical_synonyms":
        return [f"Synonym: {render_entry(value)}" for value in plant.get(section, [])]
    if section == "vernacular_names":
        return [
            f"{language}: {', '.join(render_value(name) for name in names)}"
            for language, names in plant.get(section, {}).items()
            if names
        ]
    if section == "systems_of_medicine":
        values = plant.get(section, [])
        return [f"System of medicine: {render_value(value)}" for value in values]
    if section in {"bibliography", "distribution"}:
        label = "Bibliography entry" if section == "bibliography" else "Distribution entry"
        return [f"{label}: {render_entry(value)}" for value in plant.get(section, [])]
    return []


def metadata_for(plant: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_urls": plant.get("source_urls", []),
        "source_record_ids": plant.get("source_record_ids", []),
        "source_records": plant.get("source_records", []),
        "source_xplant_id": plant.get("source_xplant_id", ""),
        "image_urls": plant.get("image_urls", []),
    }


def make_chunk(
    plant: dict[str, Any],
    section: str,
    sequence: int,
    content: str,
) -> dict[str, Any]:
    return {
        "chunk_id": f"{plant['plant_id']}__{section}__{sequence:03d}",
        "plant_id": plant["plant_id"],
        "plant_name": plant.get("plant_name", ""),
        "botanical_name": plant.get("botanical_name", ""),
        "botanical_authority": plant.get("botanical_authority", ""),
        "family": plant.get("family", ""),
        "section": section,
        "content": content,
        "source_urls": plant.get("source_urls", []),
        "source_record_ids": plant.get("source_record_ids", []),
        "source_metadata": metadata_for(plant),
    }


def chunks_for_plant(plant: dict[str, Any]) -> list[dict[str, Any]]:
    sections = [
        "identification",
        "botanical_synonyms",
        "vernacular_names",
        "systems_of_medicine",
        "bibliography",
        "distribution",
    ]
    chunks: list[dict[str, Any]] = []
    for section in sections:
        units = section_units(plant, section)
        if not units:
            continue
        max_content_chars = (
            LARGE_SECTION_MAX_CONTENT_CHARS
            if section in LARGE_SECTIONS
            else DEFAULT_MAX_CONTENT_CHARS
        )
        for sequence, content in enumerate(
            split_units(units, max_content_chars), start=1
        ):
            chunks.append(make_chunk(plant, section, sequence, content))
    if plant.get("image_urls"):
        chunks.append(
            make_chunk(
                plant,
                "images",
                1,
                "Image references are available in source_metadata.image_urls.",
            )
        )
    return chunks


def load_plants() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in INPUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    plants = load_plants()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_chunk in OUTPUT_DIR.glob("*.json"):
        old_chunk.unlink()

    index: dict[str, list[str]] = {}
    all_chunks: list[dict[str, Any]] = []
    for plant in sorted(plants, key=lambda item: item["plant_id"]):
        chunks = chunks_for_plant(plant)
        index[plant["plant_id"]] = [chunk["chunk_id"] for chunk in chunks]
        all_chunks.extend(chunks)

    for chunk in all_chunks:
        path = OUTPUT_DIR / f"{chunk['chunk_id']}.json"
        path.write_text(
            json.dumps(chunk, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sizes = [len(chunk["content"]) for chunk in all_chunks]
    sections = Counter(chunk["section"] for chunk in all_chunks)
    duplicate_ids = len(all_chunks) - len({chunk["chunk_id"] for chunk in all_chunks})
    required = {
        "chunk_id", "plant_id", "plant_name", "botanical_name",
        "botanical_authority", "family", "section", "content", "source_urls",
    }
    missing_metadata = sum(
        1 for chunk in all_chunks
        if required - set(chunk) or not chunk.get("source_record_ids") or "source_metadata" not in chunk
    )
    print(f"total plants processed: {len(plants)}")
    print(f"total chunks generated: {len(all_chunks)}")
    print("chunks per section:")
    for section, count in sorted(sections.items()):
        print(f"  {section}: {count}")
    print(f"minimum content size: {min(sizes) if sizes else 0}")
    print(f"maximum content size: {max(sizes) if sizes else 0}")
    print(f"average content size: {sum(sizes) / len(sizes) if sizes else 0:.2f}")
    print(f"plants with zero chunks: {sum(not index[plant['plant_id']] for plant in plants)}")
    print(f"duplicate chunk IDs: {duplicate_ids}")
    print(f"chunks missing plant_id: {sum(not chunk.get('plant_id') for chunk in all_chunks)}")
    print(f"chunks missing required metadata: {missing_metadata}")


if __name__ == "__main__":
    main()
