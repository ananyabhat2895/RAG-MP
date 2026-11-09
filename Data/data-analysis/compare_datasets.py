"""Compare botanical names in the canonical plant dataset with an external file.

This is deliberately a deterministic baseline. It does not use embeddings,
fuzzy matching, synonyms, network access, or an LLM.

Examples:
    python data-analysis/compare_datasets.py ^
        --source DataExtraction/normalized/plants.jsonl ^
        --external external_dataset.tsv

    python data-analysis/compare_datasets.py ^
        --source our_plants.json ^
        --external external_dataset.json ^
        --external-name-field scientific_name ^
        --output-dir comparison_output

Supported input formats: CSV, TSV, JSON, and JSONL.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable


OUTPUT_COLUMNS = (
    "our_botanical_name",
    "external_botanical_name",
    "match_type",
    "match_confidence",
)

# These substitutions address typography/formatting only. They do not remove
# author citations, abbreviations, or taxonomic content.
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
    """Normalize only conservative case, whitespace, and punctuation variants."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(PUNCTUATION_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\s*([,.;:()[\]{}])\s*", r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def _records_from_json(value: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records = value
    elif isinstance(value, dict):
        # Support a single record and common list-wrapper JSON exports.
        list_values = [
            item
            for item in value.values()
            if isinstance(item, list) and all(isinstance(row, dict) for row in item)
        ]
        records = list_values[0] if list_values else [value]
    else:
        raise ValueError(f"{path} must contain a JSON object or array.")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError(f"{path} must contain objects representing records.")
    return records


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load CSV, TSV, JSON array/object, or JSONL records without network access."""
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = "\t" if suffix == ".tsv" else ","
            return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]

    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".jsonl":
        records = []
        for line_number, line in enumerate(text.splitlines(), start=1):
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

    try:
        return _records_from_json(json.loads(text), path)
    except json.JSONDecodeError:
        # Permit newline-delimited JSON even when the file has a .json suffix.
        records = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path} is not valid JSON or JSONL: line {line_number}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object.")
            records.append(record)
        return records


def get_name(record: dict[str, Any], field: str, path: Path) -> str:
    value = record.get(field, "")
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(
            f"{path} field '{field}' must be a scalar botanical name, not "
            f"{type(value).__name__}."
        )
    return str(value or "").strip()


def write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def compare(
    source_records: list[dict[str, Any]],
    external_records: list[dict[str, Any]],
    source_name_field: str,
    external_name_field: str,
    source_path: Path,
    external_path: Path,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, Any],
]:
    source_names = [
        get_name(record, source_name_field, source_path) for record in source_records
    ]
    external_names = [
        get_name(record, external_name_field, external_path)
        for record in external_records
    ]

    external_by_normalized: dict[str, list[int]] = {}
    for index, name in enumerate(external_names):
        normalized = normalize_name(name)
        if normalized:
            external_by_normalized.setdefault(normalized, []).append(index)

    matched_rows: list[dict[str, str]] = []
    unmatched_source_rows: list[dict[str, str]] = []
    comparison_rows: list[dict[str, str]] = []
    matched_source_count = 0
    for source_name in source_names:
        candidates = external_by_normalized.get(normalize_name(source_name), [])
        external_name = external_names[candidates[0]] if candidates else ""
        row = {
            "our_botanical_name": source_name,
            "external_botanical_name": external_name,
            "match_type": "exact_normalized" if candidates else "unmatched",
            "match_confidence": "1.0" if candidates else "0.0",
        }
        comparison_rows.append(row)
        if candidates:
            matched_source_count += 1
            matched_rows.append(row)
        else:
            unmatched_source_rows.append(row)

    source_name_keys = {
        normalize_name(name) for name in source_names if normalize_name(name)
    }
    unmatched_external_rows = [
        {
            "our_botanical_name": "",
            "external_botanical_name": name,
            "match_type": "external_unmatched",
            "match_confidence": "0.0",
        }
        for name in external_names
        if not normalize_name(name) or normalize_name(name) not in source_name_keys
    ]
    unmatched_rows = unmatched_source_rows + unmatched_external_rows

    total_source = len(source_records)
    coverage = (matched_source_count / total_source * 100) if total_source else 0.0
    report = {
        "source_file": str(source_path),
        "external_file": str(external_path),
        "source_name_field": source_name_field,
        "external_name_field": external_name_field,
        "total_plants_in_existing_dataset": total_source,
        "total_records_in_external_dataset": len(external_records),
        "exact_normalized_matches": matched_source_count,
        "unmatched_existing_plants": len(unmatched_source_rows),
        "external_records_without_a_match": len(unmatched_external_rows),
        "coverage_percentage": round(coverage, 4),
        "normalization": [
            "Unicode compatibility normalization",
            "lowercase",
            "trim leading/trailing whitespace",
            "normalize repeated whitespace",
            "normalize obvious punctuation spacing and dash variants",
        ],
        "matching_limitations": [
            "Only exact normalized botanical-name matches are included.",
            "Botanical synonyms are not used.",
            "Fuzzy matching and author-citation removal are not performed.",
            "If duplicate external names exist, the first external record is shown for a matched source plant.",
        ],
    }
    return matched_rows, unmatched_rows, comparison_rows, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Existing plant CSV, TSV, JSON, or JSONL file.",
    )
    parser.add_argument(
        "--external",
        type=Path,
        required=True,
        help="External CSV, TSV, JSON, or JSONL file.",
    )
    parser.add_argument(
        "--source-name-field",
        default="botanical_name",
        help="Botanical-name field in the source file (default: botanical_name).",
    )
    parser.add_argument(
        "--external-name-field",
        default="botanical_name",
        help="Botanical-name field in the external file (default: botanical_name).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("comparison_output"),
        help="Directory for generated reports (default: comparison_output).",
    )
    args = parser.parse_args()

    try:
        source_records = load_records(args.source)
        external_records = load_records(args.external)
        matched, unmatched, comparison, report = compare(
            source_records,
            external_records,
            args.source_name_field,
            args.external_name_field,
            args.source,
            args.external,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / "matched_plants.csv", matched)
        write_csv(args.output_dir / "unmatched_plants.csv", unmatched)
        write_csv(args.output_dir / "comparison_report.csv", comparison)
        (args.output_dir / "coverage_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Existing plants: {report['total_plants_in_existing_dataset']}")
    print(f"External records: {report['total_records_in_external_dataset']}")
    print(f"Exact normalized matches: {report['exact_normalized_matches']}")
    print(f"Unmatched existing plants: {report['unmatched_existing_plants']}")
    print(f"External records without a match: {report['external_records_without_a_match']}")
    print(f"Coverage: {report['coverage_percentage']:.4f}%")
    print(f"Reports written to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
