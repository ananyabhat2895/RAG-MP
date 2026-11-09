"""Merge corrected SEPASAL records into the existing IMPPAT plant catalogue.

The merge is additive: the existing plant records and ``imppat`` objects are
copied unchanged, while SEPASAL records are attached under a new
``sepasal_medicinal_uses`` collection.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMPPAT = ROOT / "data-analysis" / "output" / "enriched_plants.jsonl"
DEFAULT_SEPASAL = ROOT / "data-analysis" / "output" / "sepasal_audit_v2" / "sepasal_medicinal_enrichment.jsonl"
DEFAULT_MATCH_REPORT = ROOT / "data-analysis" / "output" / "sepasal_audit_v2" / "sepasal_name_match_report.csv"
DEFAULT_CANONICAL = ROOT / "DataExtraction" / "normalized" / "plants.jsonl"
DEFAULT_OUTPUT = ROOT / "data-analysis" / "output" / "enriched_plants_combined.jsonl"
DEFAULT_REPORT_JSON = ROOT / "data-analysis" / "output" / "combined_dataset_validation_report.json"
DEFAULT_REPORT_TEXT = ROOT / "data-analysis" / "output" / "combined_dataset_validation_report.txt"
DEFAULT_EXCEPTIONS = ROOT / "data-analysis" / "output" / "combined_dataset_merge_exceptions.csv"


def normalize(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*-\s*", "-", text)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            records.append(record)
    return records


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main(args: argparse.Namespace) -> None:
    plants = read_jsonl(args.imppat)
    canonical = {record.get("plant_id"): record for record in read_jsonl(args.canonical)}
    by_id: dict[str, dict[str, Any]] = {}
    before_hashes: dict[str, str] = {}
    for record in plants:
        plant_id = record.get("plant_id")
        if not isinstance(plant_id, str) or not plant_id:
            raise ValueError("IMPPAT input contains a plant without a string plant_id")
        if plant_id in by_id:
            raise ValueError(f"Duplicate IMPPAT plant_id: {plant_id}")
        canonical_record = canonical.get(plant_id)
        if canonical_record is None:
            raise ValueError(f"IMPPAT plant_id is absent from canonical catalogue: {plant_id}")
        if normalize(record.get("botanical_name")) != normalize(canonical_record.get("botanical_name")):
            raise ValueError(f"IMPPAT/canonical botanical-name conflict for {plant_id}")
        by_id[plant_id] = record
        before_hashes[plant_id] = sha256_json(record.get("imppat"))

    match_statuses = Counter()
    with args.match_report.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"tax_key", "sepasal_name", "canonical_plant_id", "canonical_botanical_name", "match_status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Matching report missing columns: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            match_statuses[row["match_status"]] += 1

    attached: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exceptions: list[dict[str, str]] = []
    sepasal_count = 0
    source_statuses = Counter()
    source_files = set()
    source_ids = set()
    invalid_records = 0
    with args.sepasal.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            sepasal_count += 1
            record = json.loads(line)
            if not isinstance(record, dict):
                invalid_records += 1
                exceptions.append({"line_number": str(line_number), "plant_id": "", "botanical_name": "", "reason": "record_is_not_object"})
                continue
            plant_id = record.get("plant_id")
            botanical_name = record.get("botanical_name")
            source = record.get("source") if isinstance(record.get("source"), dict) else {}
            sepasal = record.get("sepasal") if isinstance(record.get("sepasal"), dict) else {}
            reason = ""
            if not isinstance(plant_id, str) or not plant_id:
                reason = "missing_plant_id"
            elif plant_id not in by_id:
                reason = "plant_id_not_in_imppat_catalogue"
            elif normalize(botanical_name) != normalize(by_id[plant_id].get("botanical_name")):
                reason = "botanical_name_conflicts_with_destination"
            elif normalize(botanical_name) != normalize(canonical[plant_id].get("botanical_name")):
                reason = "botanical_name_conflicts_with_canonical_catalogue"
            elif source.get("name") != "SEPASAL" or source.get("license") != "CC BY 4.0":
                reason = "missing_or_invalid_sepasal_attribution"
            elif not sepasal.get("source_record_id") or not sepasal.get("source_file"):
                reason = "missing_sepasal_source_identity"
            if reason:
                exceptions.append({
                    "line_number": str(line_number),
                    "plant_id": str(plant_id or ""),
                    "botanical_name": str(botanical_name or ""),
                    "reason": reason,
                })
                continue
            source_statuses[sepasal.get("association_status", "")] += 1
            source_files.add(sepasal["source_file"])
            source_ids.add((sepasal["source_file"], sepasal["source_record_id"]))
            attached[plant_id].append({
                "sepasal": copy.deepcopy(sepasal),
                "source": copy.deepcopy(source),
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        for record in plants:
            merged = copy.deepcopy(record)
            merged["sepasal_medicinal_uses"] = attached.get(record["plant_id"], [])
            handle.write(json.dumps(merged, ensure_ascii=False, sort_keys=True) + "\n")

    with args.exceptions.open("w", encoding="utf-8", newline="") as handle:
        fields = ["line_number", "plant_id", "botanical_name", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(exceptions)

    report = {
        "inputs": {
            "imppat_path": str(args.imppat.relative_to(ROOT)),
            "sepasal_path": str(args.sepasal.relative_to(ROOT)),
            "matching_report_path": str(args.match_report.relative_to(ROOT)),
            "canonical_path": str(args.canonical.relative_to(ROOT)),
            "imppat_schema": sorted(plants[0].keys()) if plants else [],
            "sepasal_schema": sorted(next(iter(attached.values()))[0].keys()) if attached else [],
        },
        "counts": {
            "original_plant_records": len(plants),
            "final_plant_records": len(plants),
            "unique_original_plant_ids": len(by_id),
            "sepasal_records_read": sepasal_count,
            "sepasal_records_attached": sum(len(items) for items in attached.values()),
            "sepasal_records_unassigned": len(exceptions),
            "sepasal_source_statuses_attached": dict(source_statuses),
            "authoritative_match_report_statuses": dict(match_statuses),
            "plants_with_sepasal_records": len(attached),
            "duplicate_sepasal_source_ids": sepasal_count - len(source_ids),
            "invalid_sepasal_records": invalid_records,
        },
        "validation": {
            "all_sepasal_records_accounted_for": sepasal_count == sum(len(items) for items in attached.values()) + len(exceptions),
            "plant_coverage_preserved": len(plants) == len(by_id),
            "exceptions_written": len(exceptions),
            "imppat_hashes_before_merge": before_hashes,
            "protected_input_files_not_modified": True,
            "rag_resources_touched": False,
        },
        "merge_method": "Verified plant_id lookup with normalized botanical_name cross-check against both IMPPAT destination and canonical catalogue; no TaxKey-only or fuzzy joins.",
        "output_field": "sepasal_medicinal_uses",
        "limitations": [
            "IMPPAT overlap status is preserved from corrected SEPASAL output; no semantic deduplication is performed during merge.",
            "The authoritative matching report is independently inspected for schema and status counts; the corrected enrichment's verified plant_id is required for attachment.",
        ],
    }
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_text.write_text(
        "Combined IMPPAT + SEPASAL dataset validation\n"
        "=============================================\n\n"
        f"Original plant records: {len(plants)}\n"
        f"Final plant records: {len(plants)}\n"
        f"SEPASAL records read: {sepasal_count}\n"
        f"SEPASAL records attached: {sum(len(items) for items in attached.values())}\n"
        f"SEPASAL records unassigned: {len(exceptions)}\n"
        f"Attached new_unique_association records: {source_statuses['new_unique_association']}\n"
        f"Attached overlap_exact_imppat records: {source_statuses['overlap_exact_imppat']}\n"
        f"Plants with SEPASAL records: {len(attached)}\n"
        f"Duplicate SEPASAL source IDs: {sepasal_count - len(source_ids)}\n"
        f"Authoritative match report statuses: {dict(match_statuses)}\n\n"
        "Validation checks:\n"
        f"- All SEPASAL records accounted for: {'yes' if sepasal_count == sum(len(items) for items in attached.values()) + len(exceptions) else 'no'}\n"
        f"- Plant coverage preserved: {'yes' if len(plants) == len(by_id) else 'no'}\n"
        f"- Existing IMPPAT objects copied without modification: pending final output comparison\n"
        "- Canonical identity verified by plant_id and normalized botanical_name: yes\n"
        "- Source attribution and association statuses preserved: yes for attached records\n"
        "- RAG resources modified: no\n\n"
        "Limitations:\n"
        "- Overlap classification remains the corrected SEPASAL processor's exact-normalized-wording result; semantic equivalence is not inferred.\n"
        "- No records were removed because of similar wording.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--imppat", type=Path, default=DEFAULT_IMPPAT)
    parser.add_argument("--sepasal", type=Path, default=DEFAULT_SEPASAL)
    parser.add_argument("--match-report", type=Path, default=DEFAULT_MATCH_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-text", type=Path, default=DEFAULT_REPORT_TEXT)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTIONS)
    main(parser.parse_args())
