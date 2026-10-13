"""Test deterministic resolution of user plant names against canonical records.

This is a read-only experiment. It does not use embeddings, fuzzy matching,
network access, an LLM, or any application/vector-database code.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "DataExtraction" / "normalized" / "plants.jsonl"

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

TEST_INPUTS = (
    "Neem",
    "neem",
    "Margosa",
    "Nim",
    "Azadirachta indica",
    "Melia azadirachta",
    "Tulsi",
    "Ashwagandha",
    "Turmeric",
    "Ginger",
    "Amla",
    "Aloe vera",
)


def normalize_name(value: Any) -> str:
    """Normalize case, whitespace, and obvious punctuation formatting only."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.translate(PUNCTUATION_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\s*([,.;:()[\]{}])\s*", r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def scalar_values(value: Any) -> Iterable[str]:
    """Yield scalar values from supported list/dict name structures."""
    if isinstance(value, dict):
        for nested_value in value.values():
            yield from scalar_values(nested_value)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from scalar_values(item)
    elif value is not None:
        text = str(value).strip()
        if text:
            yield text


def load_records() -> list[dict[str, Any]]:
    records = []
    with INPUT_PATH.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{INPUT_PATH}:{line_number} is not a JSON object.")
            records.append(record)
    return records


def build_name_index(
    records: list[dict[str, Any]],
) -> dict[str, list[tuple[str, str, str]]]:
    """Map each normalized name to unique plant/field/stored-name matches."""
    index: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for record in records:
        plant_id = str(record.get("plant_id", ""))
        for field in NAME_FIELDS:
            for stored_name in scalar_values(record.get(field)):
                normalized = normalize_name(stored_name)
                if not normalized:
                    continue
                match = (plant_id, field, stored_name)
                if match not in index[normalized]:
                    index[normalized].append(match)
    return dict(index)


def print_resolution(query: str, index: dict[str, list[tuple[str, str, str]]], records_by_id: dict[str, dict[str, Any]]) -> bool:
    matches = index.get(normalize_name(query), [])
    plant_ids = {plant_id for plant_id, _, _ in matches}
    print(f"Input: {query}")
    if not matches:
        print("Status: UNRESOLVED")
        print()
        return False
    if len(plant_ids) > 1:
        print("Status: AMBIGUOUS")
        for plant_id, field, stored_name in matches:
            record = records_by_id[plant_id]
            print(
                "  - "
                f"plant_id={plant_id}; "
                f"plant_name={record.get('plant_name')}; "
                f"botanical_name={record.get('botanical_name')}; "
                f"matched_field={field}; "
                f"matched_stored_name={stored_name}"
            )
        print()
        return False

    plant_id = next(iter(plant_ids))
    plant_matches = [match for match in matches if match[0] == plant_id]
    _, field, stored_name = plant_matches[0]
    record = records_by_id[plant_id]
    print("Status: RESOLVED")
    print(f"  matched plant_id: {plant_id}")
    print(f"  plant_name: {record.get('plant_name')}")
    print(f"  botanical_name: {record.get('botanical_name')}")
    print(f"  matched field: {field}")
    print(f"  matched stored name: {stored_name}")
    print()
    return True


def main() -> None:
    records = load_records()
    index = build_name_index(records)
    records_by_id = {str(record["plant_id"]): record for record in records}

    print("NAME RESOLUTION TEST")
    print("===================")
    print(f"Input: {INPUT_PATH}")
    print()

    resolved = sum(
        print_resolution(query, index, records_by_id)
        for query in TEST_INPUTS
    )
    unique_names = len(index)
    unambiguous_names = sum(
        1 for matches in index.values()
        if len({plant_id for plant_id, _, _ in matches}) == 1
    )
    ambiguous_names = unique_names - unambiguous_names

    print("SUMMARY")
    print("=======")
    print(f"Total canonical plants: {len(records)}")
    print(f"Total unique normalized names: {unique_names}")
    print(f"Names mapping to exactly one plant: {unambiguous_names}")
    print(f"Ambiguous names: {ambiguous_names}")
    print(f"Test queries successfully resolved: {resolved}")
    print(f"Test queries unresolved or ambiguous: {len(TEST_INPUTS) - resolved}")


if __name__ == "__main__":
    main()
