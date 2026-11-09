"""Export and safely combine the existing Data datasets without scraping."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MEDICINAL_INPUT = ROOT / "medicinalPlants" / "normalized" / "plants.jsonl"
ENRICHED_INPUT = ROOT / "data-analysis" / "processed" / "enriched_plants_combined.jsonl"
MEDICINAL_CSV = ROOT / "medicinalPlants" / "csv" / "medicinal_plants.csv"
ENRICHED_CSV = ROOT / "data-analysis" / "csv" / "enriched_plants.csv"
COMBINED_JSONL = ROOT / "combined" / "medicinal_plants_combined.jsonl"
COMBINED_CSV = ROOT / "combined" / "medicinal_plants_combined.csv"
MERGE_REPORT = ROOT / "combined" / "merge_report.csv"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required JSONL input is missing: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            records.append(record)
    return records


def normalize_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*-\s*", "-", text)


def string_values(value: Any) -> set[str]:
    if isinstance(value, str):
        normalized = normalize_name(value)
        return {normalized} if normalized else set()
    if isinstance(value, list):
        return set().union(*(string_values(item) for item in value)) if value else set()
    return set()


def names_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_name = normalize_name(left.get("botanical_name"))
    right_name = normalize_name(right.get("botanical_name"))
    if not left_name or not right_name or left_name == right_name:
        return True
    left_synonyms = string_values(left.get("botanical_synonyms"))
    right_synonyms = string_values(right.get("botanical_synonyms"))
    return left_name in right_synonyms or right_name in left_synonyms


def write_temp(path: Path, writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            writer(handle)
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def csv_cell(value: Any) -> str:
    if value is None or isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_records_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    def write(handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for record in records:
            writer.writerow({key: csv_cell(value) for key, value in record.items()})

    write_temp(path, write)


def botanical_synonyms(record: dict[str, Any]) -> set[str]:
    return string_values(record.get("botanical_synonyms"))


def candidate_graph(
    medicinal: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
    medicinal_indexes: list[int],
    enriched_indexes: list[int],
    synonym_only: bool,
) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = defaultdict(set)
    enriched_by_name: dict[str, set[int]] = defaultdict(set)
    for enriched_index in enriched_indexes:
        name = normalize_name(enriched[enriched_index].get("botanical_name"))
        if name:
            enriched_by_name[name].add(enriched_index)

    for medicinal_index in medicinal_indexes:
        medicinal_record = medicinal[medicinal_index]
        medicinal_name = normalize_name(medicinal_record.get("botanical_name"))
        if not medicinal_name:
            continue
        if not synonym_only:
            for enriched_index in enriched_by_name.get(medicinal_name, set()):
                graph[medicinal_index].add(enriched_index)
            continue

        medicinal_synonyms = botanical_synonyms(medicinal_record)
        for enriched_index in enriched_indexes:
            enriched_record = enriched[enriched_index]
            enriched_name = normalize_name(enriched_record.get("botanical_name"))
            if (
                enriched_name in medicinal_synonyms
                or medicinal_name in botanical_synonyms(enriched_record)
            ):
                graph[medicinal_index].add(enriched_index)
    return graph


def unique_matches(
    graph: dict[int, set[int]],
    available_enriched: set[int],
    ambiguous_medicinal: set[int],
    ambiguous_enriched: set[int],
) -> list[tuple[int, int]]:
    reverse: dict[int, set[int]] = defaultdict(set)
    for medicinal_index, candidates in graph.items():
        for enriched_index in candidates:
            reverse[enriched_index].add(medicinal_index)

    ambiguous_pairs = {
        (medicinal_index, enriched_index)
        for medicinal_index, candidates in graph.items()
        for enriched_index in candidates
        if len(candidates) != 1 or len(reverse[enriched_index]) != 1
    }
    for medicinal_index, enriched_index in ambiguous_pairs:
        ambiguous_medicinal.add(medicinal_index)
        ambiguous_enriched.add(enriched_index)

    return [
        (medicinal_index, next(iter(candidates)))
        for medicinal_index, candidates in graph.items()
        if len(candidates) == 1
        and medicinal_index not in ambiguous_medicinal
        and next(iter(candidates)) in available_enriched
        and len(reverse[next(iter(candidates))]) == 1
    ]


def match_records(
    medicinal: list[dict[str, Any]], enriched: list[dict[str, Any]]
) -> tuple[list[tuple[int, int, str]], set[int], set[int]]:
    matched: list[tuple[int, int, str]] = []
    used_medicinal: set[int] = set()
    used_enriched: set[int] = set()
    ambiguous_medicinal: set[int] = set()
    ambiguous_enriched: set[int] = set()
    medicinal_by_id: dict[str, list[int]] = defaultdict(list)
    enriched_by_id: dict[str, list[int]] = defaultdict(list)

    for index, record in enumerate(medicinal):
        plant_id = record.get("plant_id")
        if isinstance(plant_id, str) and plant_id:
            medicinal_by_id[plant_id].append(index)
    for index, record in enumerate(enriched):
        plant_id = record.get("plant_id")
        if isinstance(plant_id, str) and plant_id:
            enriched_by_id[plant_id].append(index)

    for group in medicinal_by_id.values():
        if len(group) > 1:
            ambiguous_medicinal.update(group)
    for group in enriched_by_id.values():
        if len(group) > 1:
            ambiguous_enriched.update(group)

    for plant_id in medicinal_by_id.keys() & enriched_by_id.keys():
        medicinal_group = medicinal_by_id[plant_id]
        enriched_group = enriched_by_id[plant_id]
        if (
            len(medicinal_group) != 1
            or len(enriched_group) != 1
            or medicinal_group[0] in ambiguous_medicinal
            or enriched_group[0] in ambiguous_enriched
        ):
            ambiguous_medicinal.update(medicinal_group)
            ambiguous_enriched.update(enriched_group)
            continue
        medicinal_index = medicinal_group[0]
        enriched_index = enriched_group[0]
        if not names_compatible(medicinal[medicinal_index], enriched[enriched_index]):
            ambiguous_medicinal.add(medicinal_index)
            ambiguous_enriched.add(enriched_index)
            continue
        matched.append((medicinal_index, enriched_index, "plant_id"))
        used_medicinal.add(medicinal_index)
        used_enriched.add(enriched_index)

    available_medicinal = set(range(len(medicinal))) - used_medicinal - ambiguous_medicinal
    available_enriched = set(range(len(enriched))) - used_enriched - ambiguous_enriched

    exact_graph = candidate_graph(
        medicinal, enriched, sorted(available_medicinal), sorted(available_enriched), False
    )
    exact_matches = unique_matches(
        exact_graph, available_enriched, ambiguous_medicinal, ambiguous_enriched
    )
    for medicinal_index, enriched_index in exact_matches:
        matched.append((medicinal_index, enriched_index, "exact_botanical_name"))
        used_medicinal.add(medicinal_index)
        used_enriched.add(enriched_index)

    available_medicinal = set(range(len(medicinal))) - used_medicinal - ambiguous_medicinal
    available_enriched = set(range(len(enriched))) - used_enriched - ambiguous_enriched
    synonym_graph = candidate_graph(
        medicinal, enriched, sorted(available_medicinal), sorted(available_enriched), True
    )
    synonym_matches = unique_matches(
        synonym_graph, available_enriched, ambiguous_medicinal, ambiguous_enriched
    )
    for medicinal_index, enriched_index in synonym_matches:
        matched.append((medicinal_index, enriched_index, "verified_botanical_synonym"))
        used_medicinal.add(medicinal_index)
        used_enriched.add(enriched_index)

    return matched, ambiguous_medicinal, ambiguous_enriched


def combined_record(
    medicinal_record: dict[str, Any] | None,
    enriched_record: dict[str, Any] | None,
    status: str,
    method: str,
) -> dict[str, Any]:
    identity = medicinal_record or enriched_record or {}
    return {
        "plant_id": identity.get("plant_id", ""),
        "botanical_name": identity.get("botanical_name", ""),
        "match_status": status,
        "match_method": method,
        "medicinal_plants": medicinal_record,
        "data_analysis": enriched_record,
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    def write(handle) -> None:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    write_temp(path, write)


def run(force: bool = False) -> dict[str, int]:
    outputs = [MEDICINAL_CSV, ENRICHED_CSV, COMBINED_JSONL, COMBINED_CSV, MERGE_REPORT]
    existing = [path for path in outputs if path.exists()]
    if existing and not force:
        paths = "\n".join(f"  {path}" for path in existing)
        raise FileExistsError(
            "Generated outputs already exist. Re-run with --force to replace them:\n"
            + paths
        )

    medicinal = load_jsonl(MEDICINAL_INPUT)
    enriched = load_jsonl(ENRICHED_INPUT)
    if not medicinal:
        raise ValueError(f"Medicinal plant input contains no records: {MEDICINAL_INPUT}")
    if not enriched:
        raise ValueError(f"Enriched plant input contains no records: {ENRICHED_INPUT}")

    write_records_csv(MEDICINAL_CSV, medicinal)
    write_records_csv(ENRICHED_CSV, enriched)

    matched, ambiguous_medicinal, ambiguous_enriched = match_records(medicinal, enriched)
    matched_medicinal = {left for left, _, _ in matched}
    matched_enriched = {right for _, right, _ in matched}

    combined: list[dict[str, Any]] = []
    methods = {"plant_id": 0, "exact_botanical_name": 0, "verified_botanical_synonym": 0}
    for medicinal_index, enriched_index, method in matched:
        methods[method] += 1
        combined.append(
            combined_record(
                medicinal[medicinal_index],
                enriched[enriched_index],
                "matched",
                method,
            )
        )
    for index, record in enumerate(medicinal):
        if index in matched_medicinal:
            continue
        status = "ambiguous" if index in ambiguous_medicinal else "unmatched"
        combined.append(combined_record(record, None, status, ""))
    for index, record in enumerate(enriched):
        if index in matched_enriched:
            continue
        status = "ambiguous" if index in ambiguous_enriched else "unmatched"
        combined.append(combined_record(None, record, status, ""))

    report = {
        "medicinal_input_records": len(medicinal),
        "enriched_input_records": len(enriched),
        "matched_records": len(matched),
        "matched_by_plant_id": methods["plant_id"],
        "matched_by_exact_botanical_name": methods["exact_botanical_name"],
        "matched_by_verified_synonym": methods["verified_botanical_synonym"],
        "unmatched_medicinal_records": len(medicinal)
        - len(matched_medicinal)
        - len(ambiguous_medicinal),
        "unmatched_enriched_records": len(enriched)
        - len(matched_enriched)
        - len(ambiguous_enriched),
        "ambiguous_medicinal_records": len(ambiguous_medicinal),
        "ambiguous_enriched_records": len(ambiguous_enriched),
        "ambiguous_matches": len(ambiguous_medicinal),
        "final_combined_records": len(combined),
    }

    write_jsonl(COMBINED_JSONL, combined)
    write_records_csv(COMBINED_CSV, combined)

    def write_report(handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=["metric", "count"])
        writer.writeheader()
        writer.writerows({"metric": key, "count": value} for key, value in report.items())

    write_temp(MERGE_REPORT, write_report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace generated CSV and combined outputs if they already exist",
    )
    args = parser.parse_args()
    report = run(force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
