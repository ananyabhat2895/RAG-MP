"""Validate generated semantic chunks without modifying pipeline data."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PLANTS_PATH = ROOT / "normalized" / "plants.jsonl"
CHUNKS_DIR = ROOT / "chunks"
INDEX_PATH = CHUNKS_DIR / "index.json"

ALLOWED_SECTIONS = {
    "identification",
    "botanical_synonyms",
    "vernacular_names",
    "systems_of_medicine",
    "bibliography",
    "distribution",
    "images",
}
CHUNK_ID_RE = re.compile(
    r"^(?P<plant_id>plant_[0-9a-f]{16})"
    r"__(?P<section>[a-z_]+)__(?P<sequence>[0-9]{3})$"
)
STRUCTURED_PREFIXES = {
    "vernacular_names": ":",  # one complete language group per line
    "bibliography": "Bibliography entry:",
    "distribution": "Distribution entry:",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path}: cannot parse JSON: {exc}") from exc


def add_issue(issues: list[str], message: str) -> None:
    issues.append(message)


def main() -> int:
    issues: list[str] = []
    plants: list[dict[str, Any]] = []
    if not PLANTS_PATH.exists():
        add_issue(issues, f"missing normalized input: {PLANTS_PATH}")
    else:
        try:
            plants = [
                json.loads(line)
                for line in PLANTS_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except Exception as exc:
            add_issue(issues, f"cannot parse plants.jsonl: {exc}")

    plant_by_id: dict[str, dict[str, Any]] = {}
    plant_id_duplicates: set[str] = set()
    for plant in plants:
        plant_id = plant.get("plant_id")
        if not plant_id:
            add_issue(issues, "normalized plant missing plant_id")
        elif plant_id in plant_by_id:
            plant_id_duplicates.add(plant_id)
        else:
            plant_by_id[plant_id] = plant
    for plant_id in sorted(plant_id_duplicates):
        add_issue(issues, f"duplicate normalized plant_id: {plant_id}")

    chunk_files = (
        sorted(CHUNKS_DIR.glob("*.json"))
        if CHUNKS_DIR.exists()
        else []
    )
    chunk_paths = [path for path in chunk_files if path.name != INDEX_PATH.name]
    chunks: list[dict[str, Any]] = []
    chunk_file_ids: list[str] = []
    for path in chunk_paths:
        try:
            chunk = load_json(path)
        except ValueError as exc:
            add_issue(issues, str(exc))
            continue
        chunks.append(chunk)
        chunk_file_ids.append(path.stem)
        if path.stem != chunk.get("chunk_id"):
            add_issue(
                issues,
                f"filename/chunk_id mismatch: {path.name} vs {chunk.get('chunk_id')}",
            )

    chunk_ids = [chunk.get("chunk_id", "") for chunk in chunks]
    duplicate_chunk_ids = sorted(
        chunk_id for chunk_id, count in Counter(chunk_ids).items()
        if chunk_id and count > 1
    )
    for chunk_id in duplicate_chunk_ids:
        add_issue(issues, f"duplicate chunk_id: {chunk_id}")

    chunks_by_plant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata_conflicts: dict[str, dict[str, list[str]]] = {}
    section_counts: Counter[str] = Counter()
    sizes: list[int] = []
    oversized_valid: list[str] = []
    oversized_problematic: list[str] = []
    small_chunks: list[str] = []
    required_chunk_fields = {
        "chunk_id",
        "plant_id",
        "plant_name",
        "botanical_name",
        "botanical_authority",
        "family",
        "section",
        "content",
        "source_urls",
        "source_record_ids",
        "source_metadata",
    }

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "")
        plant_id = chunk.get("plant_id", "")
        section = chunk.get("section", "")
        content = chunk.get("content", "")
        if not chunk_id:
            add_issue(issues, "chunk missing chunk_id")
        else:
            match = CHUNK_ID_RE.fullmatch(chunk_id)
            if not match:
                add_issue(issues, f"non-deterministic chunk_id format: {chunk_id}")
            elif match.group("plant_id") != plant_id or match.group("section") != section:
                add_issue(issues, f"chunk_id metadata mismatch: {chunk_id}")
        if not plant_id:
            add_issue(issues, f"chunk missing plant_id: {chunk_id}")
        elif plant_id not in plant_by_id:
            add_issue(issues, f"orphan chunk plant_id: {plant_id} ({chunk_id})")
        else:
            chunks_by_plant[plant_id].append(chunk)
        if section not in ALLOWED_SECTIONS:
            add_issue(issues, f"invalid section {section!r}: {chunk_id}")
        else:
            section_counts[section] += 1
        if not isinstance(content, str) or not content.strip():
            add_issue(issues, f"empty content: {chunk_id}")
            content = ""
        sizes.append(len(content))
        if len(content) < 30:
            small_chunks.append(chunk_id)
        if len(content) > 2500:
            prefix = STRUCTURED_PREFIXES.get(section)
            lines = content.splitlines()
            is_structured = bool(prefix) and all(
                line.startswith(prefix) if prefix != ":" else ":" in line
                for line in lines
                if line.strip()
            )
            (oversized_valid if is_structured else oversized_problematic).append(chunk_id)
        missing_fields = required_chunk_fields - set(chunk)
        if missing_fields:
            add_issue(
                issues,
                f"missing required metadata {sorted(missing_fields)}: {chunk_id}",
            )
        if not isinstance(chunk.get("source_metadata"), dict):
            add_issue(issues, f"invalid source_metadata: {chunk_id}")
        if not isinstance(chunk.get("source_urls"), list):
            add_issue(issues, f"invalid source_urls: {chunk_id}")
        if not isinstance(chunk.get("source_record_ids"), list) or not chunk.get(
            "source_record_ids"
        ):
            add_issue(issues, f"missing source_record_ids: {chunk_id}")
        if plant_id in plant_by_id and plant_by_id[plant_id].get("source_urls"):
            if not chunk.get("source_urls"):
                add_issue(issues, f"missing source URLs where available: {chunk_id}")

    for plant_id, plant_chunks in sorted(chunks_by_plant.items()):
        fields = ("plant_name", "botanical_name", "botanical_authority", "family")
        conflicts = {
            field: sorted(
                {
                    str(chunk.get(field, ""))
                    for chunk in plant_chunks
                }
            )
            for field in fields
        }
        conflicts = {
            field: values
            for field, values in conflicts.items()
            if len(values) > 1
        }
        if conflicts:
            metadata_conflicts[plant_id] = conflicts

    index: dict[str, Any] = {}
    if not INDEX_PATH.exists():
        add_issue(issues, f"missing index: {INDEX_PATH}")
    else:
        try:
            index = load_json(INDEX_PATH)
            if not isinstance(index, dict):
                add_issue(issues, "index.json must contain an object")
                index = {}
        except ValueError as exc:
            add_issue(issues, str(exc))

    index_references = [
        chunk_id
        for plant_id, references in index.items()
        if isinstance(references, list)
        for chunk_id in references
    ]
    duplicate_references = sorted(
        chunk_id for chunk_id, count in Counter(index_references).items()
        if count > 1
    )
    for plant_id, references in index.items():
        if plant_id not in plant_by_id:
            add_issue(issues, f"index plant_id not in plants.jsonl: {plant_id}")
        if not isinstance(references, list):
            add_issue(issues, f"index references are not a list: {plant_id}")
            continue
        for chunk_id in references:
            if not (CHUNKS_DIR / f"{chunk_id}.json").exists():
                add_issue(issues, f"index references missing chunk file: {chunk_id}")
    for chunk_id in duplicate_references:
        add_issue(issues, f"duplicate index reference: {chunk_id}")

    chunk_id_set = set(chunk_ids)
    file_id_set = set(chunk_file_ids)
    index_id_set = set(index_references)
    for chunk_id in sorted(chunk_id_set - index_id_set):
        add_issue(issues, f"generated chunk is not indexed: {chunk_id}")
    for chunk_id in sorted(index_id_set - file_id_set):
        add_issue(issues, f"index references non-generated chunk: {chunk_id}")
    for plant_id, references in index.items():
        if isinstance(references, list):
            for chunk_id in references:
                matching = [
                    chunk for chunk in chunks if chunk.get("chunk_id") == chunk_id
                ]
                if matching and any(chunk.get("plant_id") != plant_id for chunk in matching):
                    add_issue(issues, f"index plant/chunk mismatch: {plant_id}/{chunk_id}")

    indexed_plant_ids = set(index)
    zero_chunk_plants = sorted(set(plant_by_id) - indexed_plant_ids)

    print("SEMANTIC CHUNK VALIDATION REPORT")
    print("=" * 36)
    print(f"canonical plants: {len(plant_by_id)}")
    print(f"total chunks: {len(chunks)}")
    print(f"chunks per section: {dict(sorted(section_counts.items()))}")
    print(f"average content size: {sum(sizes) / len(sizes) if sizes else 0:.2f}")
    print(f"minimum content size: {min(sizes) if sizes else 0}")
    print(f"maximum content size: {max(sizes) if sizes else 0}")
    print(f"plants with zero chunks: {len(zero_chunk_plants)}")
    if zero_chunk_plants:
        print(f"  {', '.join(zero_chunk_plants)}")
    print()
    print("CHUNK ID")
    print(f"  missing chunk_id: {sum(not chunk.get('chunk_id') for chunk in chunks)}")
    print(f"  duplicate chunk_id values: {len(duplicate_chunk_ids)}")
    print(f"  invalid chunk_id formats: {sum('non-deterministic chunk_id format' in issue for issue in issues)}")
    print()
    print("PLANT ID")
    print(f"  chunks missing plant_id: {sum(not chunk.get('plant_id') for chunk in chunks)}")
    print(f"  chunks with unknown plant_id: {sum('orphan chunk plant_id' in issue for issue in issues)}")
    source_xplant_by_plant_id = defaultdict(set)
    for plant in plants:
        if plant.get("plant_id"):
            source_xplant_by_plant_id[plant["plant_id"]].add(
                plant.get("source_xplant_id", "")
            )
    source_xplant_conflicts = {
        plant_id: values
        for plant_id, values in source_xplant_by_plant_id.items()
        if len(values) != 1
    }
    print(
        "  plant_id-to-source_xplant_id conflicts: "
        f"{len(source_xplant_conflicts)}"
    )
    print()
    print("METADATA CONSISTENCY")
    print(f"  plants with conflicting chunk metadata: {len(metadata_conflicts)}")
    for plant_id, conflicts in sorted(metadata_conflicts.items()):
        print(f"  {plant_id}: {json.dumps(conflicts, ensure_ascii=False, sort_keys=True)}")
    print()
    print("CONTENT")
    print(f"  empty content failures: {sum('empty content' in issue for issue in issues)}")
    print(f"  chunks below 30 characters: {len(small_chunks)}")
    if small_chunks:
        print(f"    {', '.join(small_chunks)}")
    print(f"  chunks above 2500 characters: {len(oversized_valid) + len(oversized_problematic)}")
    print(f"    valid structured groups: {len(oversized_valid)}")
    if oversized_valid:
        print(f"      {', '.join(oversized_valid)}")
    print(f"    potentially problematic: {len(oversized_problematic)}")
    if oversized_problematic:
        print(f"      {', '.join(oversized_problematic)}")
    print()
    print("PROVENANCE")
    print(f"  provenance/integrity failures: {sum('source' in issue or 'metadata' in issue for issue in issues)}")
    print()
    print("INDEX INTEGRITY")
    print(f"  index plant IDs missing from plants.jsonl: {sum('index plant_id not' in issue for issue in issues)}")
    print(f"  missing referenced chunk files: {sum('index references missing' in issue for issue in issues)}")
    print(f"  generated chunks not referenced: {sum('generated chunk is not' in issue for issue in issues)}")
    print(f"  duplicate index references: {len(duplicate_references)}")
    print(f"  index exactly matches generated chunk set: {chunk_id_set == file_id_set == index_id_set}")
    print()
    print("RESULT")
    print(f"  integrity failures: {len(issues)}")
    print(f"  status: {'FAIL' if issues else 'PASS'}")
    if issues:
        print()
        print("FAILURE DETAILS")
        for issue in issues:
            print(f"  - {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
