"""Report source coverage and grouping quality for the normalized plant dataset."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


XPLANT_RE = re.compile(r"/xplant_id/([^/?#]+)", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]


def xplant_id(url: str) -> str | None:
    match = XPLANT_RE.search(url.strip())
    return match.group(1).lower() if match else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, default=ROOT / "links" / "links.csv")
    parser.add_argument(
        "--details", type=Path, default=ROOT / "parser" / "plant_details.json"
    )
    parser.add_argument("--plants", type=Path, default=Path(__file__).with_name("plants.jsonl"))
    args = parser.parse_args()

    with args.links.open(encoding="utf-8-sig", newline="") as handle:
        source_records = list(csv.DictReader(handle))
    detail_records = json.loads(args.details.read_text(encoding="utf-8-sig"))
    linked_urls = {
        (record.get("Detail URL") or "").strip()
        for record in source_records
        if (record.get("Detail URL") or "").strip()
    }
    detail_only_count = sum(
        1
        for record in detail_records
        if (record.get("URL") or "").strip() not in linked_urls
    )
    groups: dict[str, list[int]] = defaultdict(list)
    missing_xplant: list[int] = []
    missing_urls = 0
    for index, record in enumerate(source_records, start=1):
        url = (record.get("Detail URL") or "").strip()
        if not url:
            missing_urls += 1
        identity = xplant_id(url) if url else None
        if identity:
            groups[identity].append(index)
        else:
            missing_xplant.append(index)

    plants = [
        json.loads(line)
        for line in args.plants.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    botanical_names = Counter(
        plant.get("botanical_name", "").strip()
        for plant in plants
        if plant.get("botanical_name", "").strip()
    )
    duplicate_botanical_names = {
        name: count for name, count in sorted(botanical_names.items()) if count > 1
    }
    conflicting_source_plant_names = {
        plant.get("source_xplant_id", plant.get("plant_id", "")): plant.get(
            "raw_source_plant_names", []
        )
        for plant in plants
        if len(plant.get("raw_source_plant_names", [])) > 1
    }
    duplicate_xplants = {identity: indexes for identity, indexes in sorted(groups.items()) if len(indexes) > 1}
    missing_botanical = [
        plant.get("source_xplant_id", plant.get("plant_id", ""))
        for plant in plants
        if not plant.get("botanical_name", "").strip()
    ]

    print(f"total source records: {len(source_records) + detail_only_count}")
    print(f"  links.csv source records: {len(source_records)}")
    print(f"  unlinked plant_details.json records: {detail_only_count}")
    print(f"unique xplant_ids: {len(groups)}")
    print(f"duplicate xplant_ids: {len(duplicate_xplants)}")
    print(f"missing xplant_ids: {len(missing_xplant)}")
    print(f"missing botanical names: {len(missing_botanical)}")
    print(f"missing URLs: {missing_urls}")
    print(f"duplicate botanical names: {len(duplicate_botanical_names)}")
    print(
        "conflicting source Plant Name values: "
        f"{len(conflicting_source_plant_names)}"
    )
    print("records grouped under each xplant_id:")
    for plant in plants:
        identifiers = plant.get("source_record_ids", [])
        print(
            f"  {plant.get('source_xplant_id', '')}: "
            f"{len(identifiers)} ({', '.join(identifiers)})"
        )
    if duplicate_botanical_names:
        print("duplicate botanical-name values:")
        for name, count in duplicate_botanical_names.items():
            print(f"  {name}: {count}")
    if conflicting_source_plant_names:
        print("conflicting source Plant Name values by xplant_id:")
        for identity, names in conflicting_source_plant_names.items():
            print(f"  {identity}: {'; '.join(names)}")


if __name__ == "__main__":
    main()
