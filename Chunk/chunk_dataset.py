import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "Data"
    / "combined"
    / "medicinal_plants_combined.jsonl"
)
OUTPUT_DIR = Path(__file__).resolve().parent / "chunks"
MAX_CONTENT_CHARS = 6000
PLANT_ID_PATTERN = re.compile(r"plant_[A-Za-z0-9_-]+")


def flatten(value: Any, path: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        if not value:
            yield f"{path}: {{}}"
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from flatten(child, child_path)
    elif isinstance(value, list):
        if not value:
            yield f"{path}: []"
        for index, child in enumerate(value):
            yield from flatten(child, f"{path}[{index}]")
    else:
        yield f"{path}: {json.dumps(value, ensure_ascii=False)}"


def make_chunks(record: dict[str, Any]) -> list[dict[str, Any]]:
    plant_data = record.get("medicinal_plants")
    if not isinstance(plant_data, dict):
        plant_data = {}
    analysis_data = record.get("data_analysis")
    if not isinstance(analysis_data, dict):
        analysis_data = {}

    plant_id = str(record.get("plant_id") or "")
    botanical_name = str(
        record.get("botanical_name")
        or plant_data.get("botanical_name")
        or analysis_data.get("botanical_name")
        or ""
    )
    plant_name = str(
        plant_data.get("plant_name")
        or analysis_data.get("plant_name")
        or botanical_name
    )
    header = (
        f"Plant Name: {plant_name}\n"
        f"Botanical Name: {botanical_name}\n"
    )

    sections = [
        ("record_metadata", {
            key: value
            for key, value in record.items()
            if key not in {"medicinal_plants", "data_analysis"}
        }),
        ("medicinal_plants", plant_data),
        ("data_analysis", analysis_data),
    ]

    source_urls = []
    source_record_ids = []
    for data in (plant_data, analysis_data):
        for url in data.get("source_urls", []) or []:
            if url not in source_urls:
                source_urls.append(url)
        for source_id in data.get("source_record_ids", []) or []:
            if source_id not in source_record_ids:
                source_record_ids.append(source_id)

    result = []
    for section, data in sections:
        lines = list(flatten(data))
        if not lines:
            lines = ["(no fields)"]

        content_parts: list[str] = []
        base_content_size = len(header) + len(f"Section: {section}\nData:\n")
        current_size = base_content_size
        part = 1
        for line in lines:
            line_size = len(line) + 1
            if content_parts and current_size + line_size > MAX_CONTENT_CHARS:
                result.append(make_chunk(
                    plant_id, plant_name, botanical_name, section, part,
                    header, content_parts, plant_data, analysis_data,
                    source_urls, source_record_ids,
                ))
                part += 1
                content_parts = []
                current_size = base_content_size
            content_parts.append(line)
            current_size += line_size

        result.append(make_chunk(
            plant_id, plant_name, botanical_name, section, part,
            header, content_parts, plant_data, analysis_data,
            source_urls, source_record_ids,
        ))

    return result


def make_chunk(
    plant_id: str,
    plant_name: str,
    botanical_name: str,
    section: str,
    part: int,
    header: str,
    lines: list[str],
    plant_data: dict[str, Any],
    analysis_data: dict[str, Any],
    source_urls: list[Any],
    source_record_ids: list[Any],
) -> dict[str, Any]:
    return {
        "chunk_id": f"{plant_id}_{section}_{part:04d}",
        "plant_id": plant_id,
        "plant_name": plant_name,
        "botanical_name": botanical_name,
        "botanical_authority": (
            plant_data.get("botanical_authority")
            or analysis_data.get("botanical_authority")
            or ""
        ),
        "family": plant_data.get("family") or analysis_data.get("family") or "",
        "section": section,
        "content": (
            f"{header}Section: {section}\nData:\n" + "\n".join(lines)
        ),
        "source_urls": source_urls,
        "source_record_ids": source_record_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chunk the combined medicinal plants JSONL dataset."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace previously generated plant and batch JSON files.",
    )
    args = parser.parse_args()

    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"Dataset not found: {SOURCE_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        list(OUTPUT_DIR.glob("chunks_*.json"))
        + list(OUTPUT_DIR.glob("plant_*.json"))
    )
    if existing and not args.force:
        raise FileExistsError(
            f"Generated chunk files already exist in {OUTPUT_DIR}. "
            "Use --force to replace them."
        )

    records = []
    with SOURCE_FILE.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {error}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object on line {line_number}."
                )
            records.append(record)

    chunks_by_plant: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        plant_id = str(record.get("plant_id") or "")
        if not PLANT_ID_PATTERN.fullmatch(plant_id):
            raise ValueError(f"Missing or invalid plant_id: {plant_id!r}")
        if plant_id in chunks_by_plant:
            raise ValueError(f"Duplicate plant_id in source data: {plant_id}")
        chunks_by_plant[plant_id] = make_chunks(record)

    chunks = [
        chunk
        for plant_chunks in chunks_by_plant.values()
        for chunk in plant_chunks
    ]
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate chunk IDs generated.")

    if args.force:
        for path in existing:
            path.unlink()

    for plant_id, plant_chunks in chunks_by_plant.items():
        output_file = OUTPUT_DIR / f"{plant_id}.json"
        output_file.write_text(
            json.dumps(
                plant_chunks, ensure_ascii=False, separators=(",", ":")
            ) + "\n",
            encoding="utf-8",
        )

    print(f"Source records: {len(records)}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Plant files: {len(chunks_by_plant)}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
