"""Create isolated chunks for the verified IMPPAT + SEPASAL dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data-analysis" / "output" / "enriched_plants_combined.jsonl"
DEFAULT_OUTPUT = ROOT / "DataExtraction" / "chunks_combined_test"
MAX_CONTENT_CHARS = 2500


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def non_empty(value: Any) -> bool:
    return value not in (None, "", [], {}, ())


def render(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(
            f"{clean(key)}: {render(item)}"
            for key, item in value.items()
            if non_empty(item)
        )
    if isinstance(value, list):
        return "; ".join(render(item) for item in value if non_empty(item))
    return clean(value)


def base_chunk(plant: dict[str, Any], section: str, sequence: int, content: str) -> dict[str, Any]:
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
        "source_metadata": {
            "source_xplant_id": plant.get("source_xplant_id", ""),
            "source_urls": plant.get("source_urls", []),
            "source_record_ids": plant.get("source_record_ids", []),
            "source_records": plant.get("source_records", []),
            "image_urls": plant.get("image_urls", []),
        },
    }


def identification_chunk(plant: dict[str, Any]) -> dict[str, Any]:
    fields = [
        ("Plant name", plant.get("plant_name")),
        ("Botanical name", plant.get("botanical_name")),
        ("Botanical authority", plant.get("botanical_authority")),
        ("Family", plant.get("family")),
        ("Source xplant ID", plant.get("source_xplant_id")),
    ]
    content = "\n".join(f"{label}: {clean(value)}" for label, value in fields if non_empty(value))
    return base_chunk(plant, "identification", 1, content)


def imppat_chunks(plant: dict[str, Any]) -> list[dict[str, Any]]:
    imppat = plant.get("imppat")
    if not isinstance(imppat, dict):
        return []
    uses = imppat.get("therapeutic_uses")
    if not isinstance(uses, list):
        return []
    chunks = []
    grouped: dict[str, list[str]] = {}
    for association in uses:
        if not isinstance(association, dict):
            raise ValueError("Invalid IMPPAT association object")
        use = association.get("use")
        if not isinstance(use, str) or not use.strip():
            raise ValueError("IMPPAT association has empty use")
        grouped.setdefault(association.get("plant_part") or "", []).append(use)
    sequence = 1
    for part, grouped_uses in grouped.items():
        for use in grouped_uses:
            content = "\n".join([
                f"Plant: {plant.get('plant_name', '')}",
                f"Botanical name: {plant.get('botanical_name', '')}",
                f"Family: {plant.get('family', '')}",
                "",
                "IMPPAT Therapeutic Uses",
                f"Plant part: {part or 'Not specified'}",
                f"Therapeutic use: {use}",
            ])
            chunk = base_chunk(plant, "imppat_therapeutic_uses", sequence, content)
            chunk.update({
                "imppat_plant_identifier": imppat.get("plant_identifier", ""),
                "imppat_source": imppat.get("source", ""),
                "imppat_source_type": imppat.get("source_type", ""),
                "imppat_plant_part": part or None,
            })
            chunks.append(chunk)
            sequence += 1
    return chunks


def sepasal_content(plant: dict[str, Any], item: dict[str, Any]) -> str:
    s = item["sepasal"]
    lines = [
        f"Plant: {plant.get('plant_name', '')}",
        f"Botanical name: {plant.get('botanical_name', '')}",
        f"Family: {plant.get('family', '')}",
        "",
        "SEPASAL Reported Traditional Medicinal Use",
        "This source reports traditional use categories; it is not a claim of clinical efficacy.",
        f"Source scientific name: {s.get('source_scientific_name', '')}",
        f"TaxKey: {s.get('tax_key', '')}",
        f"Classification: {s.get('use12_text', '')}",
        f"Use category: {s.get('use_category', '')}",
    ]
    if s.get("detail_values"):
        lines.append(f"Detailed use values: {render(s['detail_values'])}")
    if s.get("plant_parts"):
        lines.append(f"Plant parts: {render(s['plant_parts'])}")
    if s.get("medicinal_applications"):
        lines.append(f"Medicinal applications: {render(s['medicinal_applications'])}")
    if s.get("vernacular_name"):
        lines.append(f"Vernacular name: {s['vernacular_name']} ({s.get('vernacular_language') or 'language not specified'})")
    lines.append(f"Association status: {s.get('association_status', '')}")
    lines.append(f"SEPASAL source file: {s.get('source_file', '')}")
    lines.append(f"SEPASAL source record ID: {s.get('source_record_id', '')}")
    for reference in s.get("references", []):
        rendered = render(reference)
        if rendered:
            lines.append(f"Reference: {rendered}")
    return "\n".join(lines)


def sepasal_chunks(plant: dict[str, Any]) -> list[dict[str, Any]]:
    records = plant.get("sepasal_medicinal_uses")
    if not isinstance(records, list):
        return []
    chunks = []
    for sequence, item in enumerate(records, 1):
        if not isinstance(item, dict) or not isinstance(item.get("sepasal"), dict):
            raise ValueError(f"Invalid SEPASAL record for {plant.get('plant_id')}")
        content = sepasal_content(plant, item)
        if not content.strip():
            continue
        chunk = base_chunk(plant, "sepasal_medicinal_uses", sequence, content)
        chunk["sepasal"] = item["sepasal"]
        chunk["sepasal_source"] = item.get("source", {})
        chunks.append(chunk)
    return chunks


def read_plants(path: Path) -> list[dict[str, Any]]:
    plants = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path}:{line_number} is not an object")
                plants.append(record)
    return plants


def main(args: argparse.Namespace) -> None:
    plants = read_plants(args.input)
    if len(plants) != 951:
        raise ValueError(f"Expected 951 plants, found {len(plants)}")
    chunks = []
    index = {}
    for plant in sorted(plants, key=lambda item: item["plant_id"]):
        plant_chunks = [identification_chunk(plant)]
        plant_chunks.extend(imppat_chunks(plant))
        plant_chunks.extend(sepasal_chunks(plant))
        index[plant["plant_id"]] = [chunk["chunk_id"] for chunk in plant_chunks]
        chunks.extend(plant_chunks)
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate chunk IDs generated")
    if any(not chunk["content"].strip() for chunk in chunks):
        raise ValueError("Empty chunk content generated")
    sepasal_chunks_out = [chunk for chunk in chunks if chunk["section"] == "sepasal_medicinal_uses"]
    if len(sepasal_chunks_out) != sum(len(plant.get("sepasal_medicinal_uses", [])) for plant in plants):
        raise ValueError("Not all SEPASAL records were represented")

    args.output.mkdir(parents=True, exist_ok=True)
    for chunk in chunks:
        (args.output / f"{chunk['chunk_id']}.json").write_text(
            json.dumps(chunk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (args.output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = {
        "input_plants": len(plants),
        "output_chunks": len(chunks),
        "plants_represented": len(index),
        "sepasal_input_records": sum(len(plant.get("sepasal_medicinal_uses", [])) for plant in plants),
        "sepasal_chunks": len(sepasal_chunks_out),
        "sections": dict(Counter(chunk["section"] for chunk in chunks)),
        "duplicate_chunk_ids": 0,
        "empty_content": 0,
        "sepasal_chunks_with_attribution": sum(
            bool(chunk.get("sepasal_source", {}).get("license") == "CC BY 4.0")
            for chunk in sepasal_chunks_out
        ),
        "sepasal_chunks_with_references": sum(bool(chunk.get("sepasal", {}).get("references")) for chunk in sepasal_chunks_out),
        "output_dir": str(args.output),
    }
    (args.output / "chunk_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    main(parser.parse_args())
