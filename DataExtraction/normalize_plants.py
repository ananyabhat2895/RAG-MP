"""Build the canonical plant-level JSONL dataset from extracted plant sources.

Plant identity is derived only from the xplant_id in a plant detail URL.
The links CSV is used as the source-record inventory because the detail parser
deduplicates URLs and therefore cannot represent repeated source records.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
LINKS_PATH = ROOT / "links" / "links.csv"
DETAILS_PATH = ROOT / "parser" / "plant_details.json"
OUTPUT_PATH = ROOT / "normalized" / "plants.jsonl"

XPLANT_RE = re.compile(r"/xplant_id/([^/?#]+)", re.IGNORECASE)
BOTANICAL_RE = re.compile(
    r"^([A-Z][a-z-]+\s+(?:[a-z][a-z-]+|Sp\.?|spp\.?))(?:\s+(.*))?$"
)


def clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\ufeff", "").split())


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean(value)
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def source_xplant_id(url: str) -> str | None:
    match = XPLANT_RE.search(clean(url))
    return match.group(1).strip().lower() if match else None


def plant_id(xplant_id: str) -> str:
    # Keep the source identity visible while hashing it to a fixed, stable ID.
    digest = hashlib.sha256(xplant_id.encode("utf-8")).hexdigest()[:16]
    return f"plant_{digest}"


def split_botanical_name(raw_value: Any) -> tuple[str, str]:
    raw = clean(raw_value)
    if not raw:
        return "", ""
    raw = re.split(r"\s+Full Botanical citation\s*-\s*", raw, maxsplit=1)[0]
    raw = re.sub(r"\s+\bX$", "", raw).strip()
    match = BOTANICAL_RE.match(raw)
    if not match:
        return raw, ""
    name = clean(match.group(1))
    authority = re.sub(r"\s+\bX$", "", clean(match.group(2))).strip()
    return name, authority


def normalized_vernacular(detail: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, Any]]:
    canonical: dict[str, list[str]] = OrderedDict()
    raw_values: dict[str, Any] = OrderedDict()
    for key in ("Vernacular Names", "Vernacular names"):
        if key not in detail or detail[key] in ("", None, {}):
            continue
        value = detail[key]
        raw_values[key] = value
        if isinstance(value, dict):
            for language, names in value.items():
                parsed = [part.strip(" -") for part in clean(names).split(",") if part.strip(" -")]
                canonical.setdefault(clean(language), [])
                canonical[clean(language)].extend(parsed)
        else:
            canonical.setdefault("_source_summary", []).append(clean(value))
    for language, names in canonical.items():
        canonical[language] = unique_strings(names)
    return dict(canonical), dict(raw_values)


def detail_values(details: list[dict[str, Any]]) -> dict[str, Any]:
    details = [detail for detail in details if detail]
    raw_botanical_names = unique_strings(detail.get("Botanical Name") for detail in details)
    botanical_name, botanical_authority = split_botanical_name(
        raw_botanical_names[0] if raw_botanical_names else ""
    )
    families = unique_strings(detail.get("Family") for detail in details)

    synonyms: list[str] = []
    raw_synonyms: list[Any] = []
    vernacular: dict[str, list[str]] = OrderedDict()
    raw_vernacular: list[dict[str, Any]] = []
    bibliography: list[dict[str, str]] = []
    distribution: list[dict[str, str]] = []
    images: list[str] = []
    systems: list[str] = []
    for detail in details:
        for key, value in detail.items():
            if key.startswith("Botanical Synonyms"):
                raw_synonyms.extend(as_list(value))
                synonyms.extend(as_list(value))
        current_vernacular, raw_values = normalized_vernacular(detail)
        if raw_values:
            raw_vernacular.append(raw_values)
        for language, names in current_vernacular.items():
            vernacular.setdefault(language, [])
            vernacular[language].extend(names)
        bibliography.extend(
            item for item in as_list(detail.get("Bibliography")) if isinstance(item, dict)
        )
        distribution.extend(
            item for item in as_list(detail.get("Distribution")) if isinstance(item, dict)
        )
        images.extend(as_list(detail.get("Images")))
        system_text = clean(detail.get("System(s) of Indian Medicine"))
        system_text = re.split(r"\s+Vernacular names\s*-", system_text, maxsplit=1)[0]
        systems.extend(part.strip() for part in system_text.split(","))

    def unique_dicts(values: list[dict[str, Any]]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for value in values:
            item = {clean(k): clean(v) for k, v in value.items()}
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if marker not in seen:
                result.append(item)
                seen.add(marker)
        return result

    for language in vernacular:
        vernacular[language] = unique_strings(vernacular[language])

    return {
        "plant_name": botanical_name,
        "botanical_name": botanical_name,
        "botanical_authority": botanical_authority,
        "family": families[0] if families else "",
        "botanical_synonyms": unique_strings(synonyms),
        "vernacular_names": dict(vernacular),
        "systems_of_medicine": unique_strings(systems),
        "bibliography": unique_dicts(bibliography),
        "distribution": unique_dicts(distribution),
        "image_urls": sorted(set(clean(value) for value in images if clean(value))),
        "raw_botanical_names": raw_botanical_names,
        "raw_botanical_synonyms": raw_synonyms,
        "raw_vernacular_names": raw_vernacular,
        "raw_fields": {
            "family": unique_strings(detail.get("Family") for detail in details),
            "full_botanical_citations": unique_strings(
                detail.get("Full Botanical citation") for detail in details
            ),
        },
        "source_detail_record_count": len(details),
        "source_detail_fields_present": sorted(set().union(*(detail.keys() for detail in details)))
        if details
        else [],
    }


def load_inputs() -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    with LINKS_PATH.open(encoding="utf-8-sig", newline="") as handle:
        source_records = [
            {clean(key): clean(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    details = json.loads(DETAILS_PATH.read_text(encoding="utf-8-sig"))
    details_by_url = {
        clean(detail.get("URL")): detail for detail in details if detail.get("URL")
    }
    return source_records, details_by_url


def normalize() -> list[dict[str, Any]]:
    source_records, details_by_url = load_inputs()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    linked_urls: set[str] = set()
    for index, source in enumerate(source_records, start=1):
        url = clean(source.get("Detail URL"))
        xplant_id = source_xplant_id(url)
        if not xplant_id:
            continue
        linked_urls.add(url)
        grouped[xplant_id].append(
            {
                "source_record_id": f"links-{index:04d}",
                "source_url": url,
                "source_plant_name": source.get("Plant Name", ""),
                "source_status": source.get("Status", ""),
                "raw_source_record": source,
                "detail": details_by_url.get(url, {}),
            }
        )

    # The parser may have retained multiple detail URLs for one xplant_id even
    # when links.csv only points at one of them. Keep those detail records too.
    for index, (url, detail) in enumerate(sorted(details_by_url.items()), start=1):
        if url in linked_urls:
            continue
        identity = source_xplant_id(url)
        if identity:
            grouped[identity].append(
                {
                    "source_record_id": f"detail-{index:04d}",
                    "source_url": url,
                    "source_plant_name": "",
                    "source_status": "Parsed detail record",
                    "raw_source_record": {"URL": url, "source": "plant_details.json"},
                    "detail": detail,
                }
            )

    plants: list[dict[str, Any]] = []
    for xplant_id in sorted(grouped):
        records = grouped[xplant_id]
        details_by_detail_url = {
            record["source_url"]: record["detail"]
            for record in records
            if record["detail"]
        }
        details = list(details_by_detail_url.values())
        values = detail_values(details)
        raw_source_plant_names = unique_strings(
            record["source_plant_name"] for record in records
        )
        source_urls = unique_strings(record["source_url"] for record in records)
        source_record_ids = [record["source_record_id"] for record in records]
        notes: list[str] = []
        if len(records) > 1:
            notes.append(f"{len(records)} source records share this xplant_id")
        if len(raw_source_plant_names) > 1:
            notes.append(
                "Conflicting source Plant Name values: "
                + "; ".join(raw_source_plant_names)
            )
        if not details:
            notes.append("No parsed plant detail record matched the source URL")
        if not values["botanical_name"]:
            notes.append("Botanical name is missing or could not be parsed")
        plants.append(
            {
                "plant_id": plant_id(xplant_id),
                "source_xplant_id": xplant_id,
                **{key: values[key] for key in (
                    "botanical_name", "botanical_authority", "family",
                    "botanical_synonyms", "vernacular_names", "systems_of_medicine",
                    "bibliography", "distribution", "image_urls",
                )},
                "plant_name": raw_source_plant_names[0] if raw_source_plant_names else "",
                "source_urls": source_urls,
                "source_record_ids": source_record_ids,
                "normalization_status": "normalized",
                "notes": notes,
                "raw_source_plant_names": raw_source_plant_names,
                "raw_botanical_names": values["raw_botanical_names"],
                "raw_botanical_synonyms": values["raw_botanical_synonyms"],
                "raw_vernacular_names": values["raw_vernacular_names"],
                "raw_fields": values["raw_fields"],
                "source_records": [
                    {key: value for key, value in record.items() if key != "detail"}
                    for record in records
                ],
                "source_detail_record_count": values["source_detail_record_count"],
                "source_detail_fields_present": values["source_detail_fields_present"],
            }
        )
    return plants


def main() -> None:
    plants = normalize()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for plant in plants:
            handle.write(json.dumps(plant, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Wrote {len(plants)} canonical plants to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
