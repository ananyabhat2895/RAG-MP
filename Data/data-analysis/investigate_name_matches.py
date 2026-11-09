"""Investigate exact canonical name matches and their language evidence."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "DataExtraction" / "normalized" / "plants.jsonl"
QUERIES = ("Neem", "Tulsi", "Amla", "Margosa", "Melia azadirachta")
NAME_FIELDS = (
    "botanical_name",
    "plant_name",
    "botanical_synonyms",
    "vernacular_names",
    "raw_botanical_names",
    "raw_botanical_synonyms",
    "raw_source_plant_names",
    "common_name",
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
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(PUNCTUATION_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\s*([,.;:()[\]{}])\s*", r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def scalar_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for nested in value.values():
            values.extend(scalar_values(nested))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(scalar_values(item))
        return values
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def vernacular_matches(
    vernacular_names: Any,
    query: str,
) -> list[tuple[str, str, list[str]]]:
    matches = []
    if not isinstance(vernacular_names, dict):
        return matches
    normalized_query = normalize_name(query)
    for language, names in vernacular_names.items():
        for stored_name in scalar_values(names):
            if normalize_name(stored_name) == normalized_query:
                matches.append((language, stored_name, scalar_values(names)))
    return matches


def field_matches(record: dict[str, Any], query: str) -> list[tuple[str, str]]:
    matches = []
    normalized_query = normalize_name(query)
    for field in NAME_FIELDS:
        if field == "vernacular_names":
            matches.extend(
                (field, stored_name)
                for _, stored_name, _ in vernacular_matches(
                    record.get(field), query
                )
            )
            continue
        for stored_name in scalar_values(record.get(field)):
            if normalize_name(stored_name) == normalized_query:
                matches.append((field, stored_name))
    return list(dict.fromkeys(matches))


def containing_occurrences(record: dict[str, Any], query: str) -> list[tuple[str, str, str]]:
    """Find exact scalar values containing the query text, without fuzzy matching."""
    occurrences = []
    needle = query.lower()
    for field in NAME_FIELDS:
        if field == "vernacular_names":
            values = record.get(field)
            if isinstance(values, dict):
                for language, names in values.items():
                    for stored_name in scalar_values(names):
                        if needle in stored_name.lower():
                            occurrences.append((field, language, stored_name))
            continue
        for stored_name in scalar_values(record.get(field)):
            if needle in stored_name.lower():
                occurrences.append((field, "", stored_name))
    return occurrences


def strength(field: str, language: str) -> str:
    if field == "botanical_name":
        return "BOTANICAL_EXACT"
    if field == "botanical_synonyms":
        return "BOTANICAL_SYNONYM"
    if field == "common_name":
        return "COMMON_NAME"
    if field == "plant_name":
        return "PLANT_NAME"
    if field in {"raw_botanical_names", "raw_botanical_synonyms", "raw_source_plant_names"}:
        return "RAW_NAME_VARIANT"
    return "ENGLISH_VERNACULAR" if language.lower().startswith("english") else "REGIONAL_VERNACULAR"


def main() -> None:
    records = [
        json.loads(line)
        for line in INPUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    exact_candidates: dict[str, set[str]] = {query: set() for query in QUERIES}
    by_id = {record["plant_id"]: record for record in records}

    for query in QUERIES:
        for record in records:
            if field_matches(record, query):
                exact_candidates[query].add(record["plant_id"])

    print("CANONICAL NAME MATCH INVESTIGATION")
    print("==================================")
    print(f"Input: {INPUT_PATH}")
    print()

    summary_rows: list[tuple[str, str, str, str, str, str]] = []
    for query in QUERIES:
        print(f"QUERY: {query}")
        candidate_ids = sorted(exact_candidates[query])
        if not candidate_ids:
            print("  Exact normalized candidates: none")
        for plant_id in candidate_ids:
            record = by_id[plant_id]
            print(f"  Candidate plant_id: {plant_id}")
            print(f"  plant_name: {record.get('plant_name')}")
            print(f"  botanical_name: {record.get('botanical_name')}")
            print(f"  common_name: {json.dumps(record.get('common_name'), ensure_ascii=False)}")
            print(f"  botanical_synonyms: {json.dumps(record.get('botanical_synonyms'), ensure_ascii=False)}")
            exact_matches = field_matches(record, query)
            print("  Exact matches:")
            for field, stored_name in exact_matches:
                vernacular_languages = [
                    language
                    for language, value, _ in vernacular_matches(
                        record.get("vernacular_names"), query
                    )
                    if value == stored_name
                ]
                languages = vernacular_languages if field == "vernacular_names" else []
                print(
                    f"    field={field}; stored_value={stored_name}; "
                    f"languages={languages or ['not applicable']}"
                )
                if field == "vernacular_names":
                    print("    complete vernacular entries for matched name:")
                    for language, value, _ in vernacular_matches(
                        record.get("vernacular_names"), query
                    ):
                        if value == stored_name:
                            print(f"      {language}: {value}")
                    for language in languages:
                        summary_rows.append(
                            (
                                query,
                                record["botanical_name"],
                                field,
                                language,
                                stored_name,
                                strength(field, language),
                            )
                        )
                else:
                    summary_rows.append(
                        (
                            query,
                            record["botanical_name"],
                            field,
                            "—",
                            stored_name,
                            strength(field, ""),
                        )
                    )
            print()

        if query in {"Margosa", "Melia azadirachta"}:
            print(f"  Containing occurrences for {query!r}:")
            found = False
            for record in records:
                occurrences = containing_occurrences(record, query)
                if occurrences:
                    found = True
                    print(f"    {record['plant_id']} ({record.get('botanical_name')}):")
                    for field, language, stored_name in occurrences:
                        print(
                            f"      field={field}; language={language or 'not applicable'}; "
                            f"stored_value={stored_name}"
                        )
            if not found:
                print("    none")
            print()

    print("SUMMARY TABLE")
    print("-------------")
    print("| Query | Candidate plant | Matched field | Language | Exact stored value | Strength category |")
    print("|---|---|---|---|---|---|")
    for row in summary_rows:
        print("| " + " | ".join(row) + " |")


if __name__ == "__main__":
    main()
