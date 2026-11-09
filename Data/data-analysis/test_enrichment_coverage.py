"""Inspect therapeutic-use coverage in the enriched plant dataset only."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data-analysis" / "output" / "enriched_plants.jsonl"
TARGETS = (
    "Azadirachta indica",
    "Ocimum tenuiflorum",
    "Withania somnifera",
    "Curcuma longa",
    "Zingiber officinale",
    "Emblica officinalis",
)

# These are lexical labels for analysis only. They do not add or reinterpret
# source terminology.
CONDITION_TERMS = (
    "diabetes", "diabetic", "malaria", "cancer", "asthma", "arthritis",
    "rheumatism", "leprosy", "cholera", "typhoid", "dysentery", "hepatitis",
    "jaundice", "gastritis", "ulcer", "inflammation", "infection", "fever",
    "worms", "worm", "helminth", "tumor", "tumour", "eczema", "psoriasis",
)
SYMPTOM_TERMS = (
    "pain", "cough", "dyspnea", "diarrhea", "diarrhoea", "vomiting",
    "nausea", "headache", "itching", "bleeding", "hemorrhage", "swelling",
    "constipation", "weakness", "thirst", "wound",
)
BODY_TERMS = (
    "liver", "kidney", "heart", "blood", "skin", "eye", "ear", "dental",
    "tooth", "respiratory", "digestive", "stomach", "uterus", "urinary",
    "reproductive", "nerve", "brain",
)
ACTION_TERMS = (
    "analges", "anthelmint", "antibacterial", "antimicrobial", "antifungal",
    "antiviral", "anti-inflammatory", "antioxid", "expectorant", "laxative",
    "diuretic", "astringent", "rejuvenation", "tonic", "sedative",
    "carminative", "appetizer", "immun", "refrigerant", "stimulant",
)


def classify_use(value: str) -> str:
    text = value.lower()
    if any(term in text for term in CONDITION_TERMS):
        return "CONDITION/DISEASE"
    if any(term in text for term in SYMPTOM_TERMS):
        return "SYMPTOM/COMPLAINT"
    if any(term in text for term in BODY_TERMS):
        return "BODY/SYSTEM RELATED"
    if any(term in text for term in ACTION_TERMS):
        return "GENERAL THERAPEUTIC ACTION"
    return "OTHER/UNCLEAR"


def load_records() -> list[dict[str, Any]]:
    records = {}
    records = []
    with INPUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                records.append(record)
    return records


def coverage_label(total: int) -> str:
    if total == 0:
        return "NONE"
    if total >= 20:
        return "STRONG"
    if total >= 5:
        return "MODERATE"
    return "WEAK"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    records = load_records()
    records_by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        records_by_name.setdefault(record["botanical_name"], record)
    summary = []
    print("ENRICHMENT DATA COVERAGE TEST")
    print("=============================")
    print(f"Input: {INPUT_PATH}")
    print(f"Canonical records loaded: {len(records)}")
    print()

    for botanical_name in TARGETS:
        record = records_by_name.get(botanical_name)
        if record is None:
            print(f"Plant: {botanical_name}")
            print("STATUS: NOT FOUND")
            print()
            continue

        imppat = record.get("imppat")
        uses = imppat.get("therapeutic_uses", []) if isinstance(imppat, dict) else []
        groups: dict[str, list[str]] = defaultdict(list)
        for association in uses:
            part = association.get("plant_part")
            part_label = part if part not in (None, "") else "Not specified"
            groups[part_label].append(str(association.get("use", "")))

        specified = sum(
            1 for association in uses
            if association.get("plant_part") not in (None, "")
        )
        distinct_uses = len({str(association.get("use", "")) for association in uses})
        coverage = coverage_label(len(uses))

        print(f"Plant: {botanical_name}")
        print(f"  botanical_name: {record.get('botanical_name')}")
        print(f"  plant_name: {record.get('plant_name')}")
        print(f"  family: {record.get('family')}")
        print(f"  IMPPAT enrichment object exists: {'YES' if isinstance(imppat, dict) else 'NO'}")
        print("  Complete therapeutic_uses list:")
        if not uses:
            print("    (none)")
        for association in uses:
            print(f"    Plant part: {association.get('plant_part')}")
            print(f"    Therapeutic use: {association.get('use')}")

        print("  Grouped by plant part:")
        for part, values in groups.items():
            print(f"    {part}:")
            for value in values:
                print(f"      - {value}")

        categories: dict[str, list[str]] = defaultdict(list)
        for association in uses:
            use = str(association.get("use", ""))
            categories[classify_use(use)].append(use)
        print("  Use-category analysis:")
        for category in (
            "CONDITION/DISEASE",
            "SYMPTOM/COMPLAINT",
            "BODY/SYSTEM RELATED",
            "GENERAL THERAPEUTIC ACTION",
            "OTHER/UNCLEAR",
        ):
            print(f"    {category}:")
            for use in categories.get(category, []):
                print(f"      - {use}")
            if not categories.get(category):
                print("      (none)")

        print(f"  Total therapeutic associations: {len(uses)}")
        print(f"  Distinct therapeutic-use strings: {distinct_uses}")
        print(f"  Number of plant parts: {len(groups)}")
        print(f"  Associations with specified plant part: {specified}")
        print(f"  Associations with null/not-specified plant part: {len(uses) - specified}")
        print(f"  DATA COVERAGE: {coverage}")
        print()
        summary.append(
            (
                botanical_name,
                "YES" if isinstance(imppat, dict) else "NO",
                len(uses),
                distinct_uses,
                len(groups),
                coverage,
            )
        )

    print("SUMMARY TABLE")
    print("-------------")
    print("| Plant | IMPPAT data? | Therapeutic associations | Distinct uses | Plant parts | Coverage |")
    print("|---|---|---:|---:|---:|---|")
    for row in summary:
        print("| " + " | ".join(str(value) for value in row) + " |")

    print()
    print("DATASET-ONLY QUESTIONS")
    print("----------------------")
    print("A. Medicinal/therapeutic use information: YES, stored as exact IMPPAT therapeutic-use strings.")
    print("B. Uses connected to plant parts: YES, each association stores plant_part and use.")
    print("C. Problems/conditions traditionally associated with a plant: PARTIALLY, where the source use strings explicitly name them.")
    print("D. Explicit benefits statements: NO dedicated benefits field; benefits are only indirectly represented by therapeutic-use terminology.")
    print("E. Preparation/application instructions: NOT PRESENT in the inspected therapeutic-use structure.")
    print("F. Dosage information: NOT PRESENT in the inspected therapeutic-use structure.")
    print("G. Safety/contraindication information: NOT PRESENT in the inspected therapeutic-use structure.")
    print("H. Clinical/evidence information: NOT PRESENT in the inspected therapeutic-use structure.")
    print("I. Sufficiency: USEFUL BUT INCOMPLETE; therapeutic uses and plant parts are present, with clear gaps for preparation, dosage, safety, and evidence.")


if __name__ == "__main__":
    main()
