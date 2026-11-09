"""Create a validated, additive IMPPAT enrichment of the canonical plant JSONL.

This script performs only the same conservative exact normalized-name matching
as compare_datasets.py. It does not use fuzzy matching, synonyms, embeddings,
network access, or an LLM.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "DataExtraction" / "normalized" / "plants.jsonl"
DEFAULT_PLANTS = ROOT / "external-data" / "impatt_plants.tsv"
DEFAULT_USES = ROOT / "external-data" / "impatt_therapeutic_uses.tsv"
DEFAULT_OUTPUT_DIR = ROOT / "data-analysis" / "output"

SUMMARY_COLUMNS = (
    "our_botanical_name",
    "imppat_plant_identifier",
    "imppat_botanical_name",
    "match_type",
    "therapeutic_use_count",
    "has_therapeutic_data",
)

PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
    }
)


def normalize_name(value: Any) -> str:
    """Keep matching rules identical to compare_datasets.py."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(PUNCTUATION_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\s*([,.;:()[\]{}])\s*", r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def load_source(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    records = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object.")
            records.append(record)
    return records


def load_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def scalar(record: dict[str, Any], field: str, path: Path) -> str:
    value = record.get(field, "")
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"{path} field '{field}' must be scalar.")
    return str(value or "")


def indexed_plants(
    records: list[dict[str, str]], path: Path
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    by_name: dict[str, list[dict[str, str]]] = {}
    by_identifier: dict[str, dict[str, str]] = {}
    for record in records:
        identifier = scalar(record, "Plant_identifier", path).strip()
        name = scalar(record, "Indian_Medicinal_plant", path).strip()
        if not identifier or not name:
            raise ValueError(f"{path} contains a plant row without identifier or name.")
        if identifier in by_identifier:
            raise ValueError(f"{path} contains duplicate Plant_identifier: {identifier}")
        by_identifier[identifier] = record
        by_name.setdefault(normalize_name(name), []).append(record)
    return by_identifier, by_name


def validate_use_rows(
    use_rows: list[dict[str, str]],
    plant_by_identifier: dict[str, dict[str, str]],
    path: Path,
) -> None:
    for row_number, row in enumerate(use_rows, start=2):
        identifier = scalar(row, "IMPPAT_Plant_identifier", path).strip()
        if not identifier:
            raise ValueError(f"{path}:{row_number} has an empty plant identifier.")
        if identifier not in plant_by_identifier:
            raise ValueError(
                f"{path}:{row_number} references unknown plant identifier {identifier}."
            )
        if not scalar(row, "Therapeutic_use", path).strip():
            raise ValueError(f"{path}:{row_number} has an empty Therapeutic_use.")


def make_use_associations(
    use_rows: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    associations: dict[str, list[dict[str, Any]]] = {}
    seen_by_plant: dict[str, set[tuple[str | None, str]]] = {}
    deduplicated = 0
    for row in use_rows:
        identifier = row["IMPPAT_Plant_identifier"].strip()
        raw_part = row.get("Plant_part", "")
        plant_part = raw_part if raw_part.strip() else None
        use = row["Therapeutic_use"]
        key = (plant_part, use)
        seen = seen_by_plant.setdefault(identifier, set())
        if key in seen:
            deduplicated += 1
            continue
        seen.add(key)
        associations.setdefault(identifier, []).append(
            {"plant_part": plant_part, "use": use}
        )
    return associations, sum(len(items) for items in associations.values()), deduplicated


def enrich(
    source_records: list[dict[str, Any]],
    external_plants: list[dict[str, str]],
    external_uses: list[dict[str, str]],
    source_path: Path,
    plants_path: Path,
    uses_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    plant_by_identifier, plants_by_name = indexed_plants(external_plants, plants_path)
    validate_use_rows(external_uses, plant_by_identifier, uses_path)
    uses_by_identifier, deduplicated_associations, duplicate_rows_removed = make_use_associations(external_uses)

    enriched: list[dict[str, Any]] = []
    summary: list[dict[str, str]] = []
    matched_count = 0
    matched_with_uses = 0
    matched_without_uses = 0
    attached_associations = 0
    matched_identifiers: set[str] = set()

    for original in source_records:
        botanical_name = scalar(original, "botanical_name", source_path)
        candidates = plants_by_name.get(normalize_name(botanical_name), [])
        record = copy.deepcopy(original)
        if not candidates:
            record["imppat"] = None
            summary.append(
                {
                    "our_botanical_name": botanical_name,
                    "imppat_plant_identifier": "",
                    "imppat_botanical_name": "",
                    "match_type": "unmatched",
                    "therapeutic_use_count": "0",
                    "has_therapeutic_data": "false",
                }
            )
            enriched.append(record)
            continue

        external = candidates[0]
        identifier = external["Plant_identifier"].strip()
        therapeutic_uses = copy.deepcopy(uses_by_identifier.get(identifier, []))
        matched_count += 1
        matched_identifiers.add(identifier)
        if therapeutic_uses:
            matched_with_uses += 1
            attached_associations += len(therapeutic_uses)
        else:
            matched_without_uses += 1
        record["imppat"] = {
            "plant_identifier": identifier,
            "indian_medicinal_plant": external["Indian_Medicinal_plant"],
            "synonymous_names": external.get("Synonymous names", ""),
            "common_name": external.get("Common_name", ""),
            "family": external.get("Family", ""),
            "system_of_medicine": external.get("System_of_Medicine", ""),
            "iucn_red_list_category": external.get("IUCN_Red_List_Category", ""),
            "therapeutic_uses": therapeutic_uses,
            "source": "IMPPAT 3.0",
            "source_type": "external_research_database",
        }
        summary.append(
            {
                "our_botanical_name": botanical_name,
                "imppat_plant_identifier": identifier,
                "imppat_botanical_name": external["Indian_Medicinal_plant"],
                "match_type": "exact_normalized",
                "therapeutic_use_count": str(len(therapeutic_uses)),
                "has_therapeutic_data": str(bool(therapeutic_uses)).lower(),
            }
        )
        enriched.append(record)

    report = {
        "source_file": str(source_path),
        "imppat_plants_file": str(plants_path),
        "imppat_therapeutic_uses_file": str(uses_path),
        "total_existing_plants": len(source_records),
        "total_imppat_plants": len(external_plants),
        "exact_normalized_matches": matched_count,
        "unmatched_existing_plants": len(source_records) - matched_count,
        "matched_plants_with_at_least_one_therapeutic_use_record": matched_with_uses,
        "matched_plants_with_zero_therapeutic_use_records": matched_without_uses,
        "total_therapeutic_use_rows_loaded": len(external_uses),
        "total_therapeutic_use_associations_attached": attached_associations,
        "total_deduplicated_therapeutic_use_associations": attached_associations,
        "total_deduplicated_imppat_associations_available": deduplicated_associations,
        "duplicate_therapeutic_use_rows_removed": duplicate_rows_removed,
        "percentage_of_existing_plants_enriched_with_therapeutic_data": round(
            matched_with_uses / len(source_records) * 100, 4
        )
        if source_records
        else 0.0,
        "matching": {
            "match_type": "exact_normalized",
            "synonyms_used": False,
            "fuzzy_matching_used": False,
            "llm_used": False,
        },
        "validation": {},
    }
    return enriched, summary, report


def validate(
    original: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
    external_plants: list[dict[str, str]],
    external_uses: list[dict[str, str]],
    summary: list[dict[str, str]],
) -> None:
    if len(original) != len(enriched):
        raise ValueError("Validation failed: output plant count differs from input.")
    _, plants_by_name = indexed_plants(external_plants, Path("IMPPAT plants"))
    valid_use_pairs = {
        (
            row["IMPPAT_Plant_identifier"].strip(),
            row["Plant_part"] if row.get("Plant_part", "").strip() else None,
            row["Therapeutic_use"],
        )
        for row in external_uses
    }
    for index, (before, after) in enumerate(zip(original, enriched), start=1):
        if before.get("botanical_name") != after.get("botanical_name"):
            raise ValueError(f"Validation failed: botanical_name changed at row {index}.")
        expected_candidates = plants_by_name.get(normalize_name(before.get("botanical_name", "")), [])
        imppat = after.get("imppat")
        if not expected_candidates:
            if imppat is not None:
                raise ValueError(f"Validation failed: unmatched row {index} has IMPPAT data.")
            continue
        if not isinstance(imppat, dict):
            raise ValueError(f"Validation failed: matched row {index} has no IMPPAT object.")
        identifier = imppat.get("plant_identifier")
        expected = expected_candidates[0]
        if identifier != expected["Plant_identifier"].strip():
            raise ValueError(f"Validation failed: incorrect IMPPAT identifier at row {index}.")
        if imppat.get("indian_medicinal_plant") != expected["Indian_Medicinal_plant"]:
            raise ValueError(f"Validation failed: incorrect IMPPAT name at row {index}.")
        output_uses = imppat.get("therapeutic_uses")
        if not isinstance(output_uses, list):
            raise ValueError(f"Validation failed: therapeutic_uses is not a list at row {index}.")
        local_pairs: set[tuple[str | None, str]] = set()
        for association in output_uses:
            part = association.get("plant_part")
            use = association.get("use")
            pair = (part, use)
            if pair in local_pairs:
                raise ValueError(f"Validation failed: duplicate association at row {index}.")
            local_pairs.add(pair)
            source_pair = (identifier, part, use)
            if source_pair not in valid_use_pairs:
                raise ValueError(f"Validation failed: fabricated or orphan use at row {index}.")
        if len(output_uses) != int(summary[index - 1]["therapeutic_use_count"]):
            raise ValueError(f"Validation failed: summary count mismatch at row {index}.")


def write_outputs(
    output_dir: Path,
    enriched: list[dict[str, Any]],
    summary: list[dict[str, str]],
    report: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "enriched_plants.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in enriched:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    (output_dir / "enrichment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "enriched_plants_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(summary)


def print_examples(enriched: list[dict[str, Any]]) -> None:
    examples: list[dict[str, Any]] = []
    multiple = next((item for item in enriched if item.get("imppat") and len(item["imppat"]["therapeutic_uses"]) > 1), None)
    with_part = next((item for item in enriched if item.get("imppat") and any(use["plant_part"] is not None for use in item["imppat"]["therapeutic_uses"]) and item is not multiple), None)
    without_part = next((item for item in enriched if item.get("imppat") and any(use["plant_part"] is None for use in item["imppat"]["therapeutic_uses"]) and item is not multiple and item is not with_part), None)
    for item in (multiple, with_part, without_part):
        if item is not None and item not in examples:
            examples.append(item)
    print("Example enriched plants:")
    for item in examples[:3]:
        imppat = item["imppat"]
        print(json.dumps({
            "botanical_name": item.get("botanical_name"),
            "imppat": {
                "plant_identifier": imppat["plant_identifier"],
                "therapeutic_use_count": len(imppat["therapeutic_uses"]),
                "therapeutic_uses_sample": imppat["therapeutic_uses"][:3],
            },
        }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--imppat-plants", type=Path, default=DEFAULT_PLANTS)
    parser.add_argument("--imppat-uses", type=Path, default=DEFAULT_USES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        source = load_source(args.source)
        plants = load_tsv(args.imppat_plants)
        uses = load_tsv(args.imppat_uses)
        enriched, summary, report = enrich(source, plants, uses, args.source, args.imppat_plants, args.imppat_uses)
        validate(source, enriched, plants, uses, summary)
        report["validation"] = {"status": "PASS", "checks_run": 8}
        write_outputs(args.output_dir, enriched, summary, report)
        print_examples(enriched)
        print(f"Wrote validated outputs to: {args.output_dir}")
        print(f"Plants enriched with therapeutic data: {report['matched_plants_with_at_least_one_therapeutic_use_record']}")
        print(f"Therapeutic-use associations attached: {report['total_therapeutic_use_associations_attached']}")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
