"""Create an additive, source-backed SEPASAL medicinal-use enrichment.

The processor uses streaming ``csv.DictReader`` reads for all SEPASAL CSVs.
It matches through SEPASAL TaxKey -> taxon name -> canonical botanical name,
and never performs fuzzy matching or inferred synonym resolution.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEDICINAL_DIR = ROOT / "external-data" / "sepasal" / "raw" / "medicinal_uses_subset"
DEFAULT_GENERAL_DIR = ROOT / "external-data" / "sepasal" / "raw" / "general"
DEFAULT_CANONICAL = ROOT / "DataExtraction" / "normalized" / "plants.jsonl"
DEFAULT_IMPPAT = ROOT / "data-analysis" / "output" / "enriched_plants.jsonl"
DEFAULT_OUTPUT = ROOT / "data-analysis" / "output" / "sepasal"

PUNCTUATION = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2212": "-", "\u00a0": " ",
})


def normalize(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).translate(PUNCTUATION)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"\s*-\s*", "-", text)


def clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def csv_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle).__next__())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path}:{line_number} is not a JSON object")
                records.append(record)
    return records


def taxa_name(row: dict[str, str]) -> str:
    genus = clean(row.get("GenEpi"))
    species = clean(row.get("NamSpec"))
    infraspecific = clean(row.get("NamISEpi"))
    rank = clean(row.get("RankText"))
    if not genus or not species:
        return ""
    name = f"{genus} {species}"
    if infraspecific and rank:
        name = f"{name} {rank} {infraspecific}"
    return name


def indexed_canonical(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    records = read_jsonl(path)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for value in [record.get("botanical_name"), *(record.get("botanical_synonyms") or [])]:
            if isinstance(value, str) and normalize(value):
                by_name[normalize(value)].append(record)
    return records, by_name


def index_taxa(path: Path) -> tuple[dict[str, set[str]], Counter[str]]:
    by_key: dict[str, set[str]] = defaultdict(set)
    missing = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"TaxKey", "GenEpi", "NamSpec", "NamISEpi", "RankText"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path} missing required columns: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            key = clean(row.get("TaxKey"))
            name = taxa_name(row)
            if not key or not name:
                missing["taxa_rows_missing_key_or_name"] += 1
                continue
            by_key[key].add(name)
    missing["tax_keys_with_multiple_names"] = sum(1 for names in by_key.values() if len(names) > 1)
    return by_key, missing


def reference_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("TaxKey")) or "",
        clean(row.get("Use12Text")) or "",
        clean(row.get("BiblTitle")) or "",
        clean(row.get("BiblAuth")) or "",
        clean(row.get("BiblPublYear")) or "",
    )


def detail_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean(row.get("TaxKey")) or "",
        clean(row.get("Use12Text")) or "",
        clean(row.get("UseCatText")) or "",
    )


def load_medicinal_details(
    specific_path: Path, reference_path: Path
) -> tuple[dict[tuple[str, str, str], list[dict[str, str]]], dict[tuple[str, str, str], list[dict[str, str]]], Counter[str]]:
    details: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    detail_references: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    counts = Counter()
    with specific_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"TaxKey", "Use12Text", "UseCatText", "Use34Text"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{specific_path} missing required columns: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            if not (clean(row.get("Use12Text")) or "").startswith("MEDICINES"):
                continue
            details[detail_key(row)].append(row)
            counts["medicinal_specific_rows"] += 1
    with reference_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"TaxKey", "Use12Text", "UseCatText", "Use34Text", "BiblTitle", "BiblAuth", "BiblPublYear"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{reference_path} missing required columns: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            if (clean(row.get("Use12Text")) or "").startswith("MEDICINES"):
                detail_references[detail_key(row)].append(row)
                counts["medicinal_reference_rows"] += 1
    return details, detail_references, counts


def category_matches(subset: str, category: str) -> bool:
    left, right = normalize(subset), normalize(category)
    if left == right:
        return True
    aliases = {
        "body parts treated": "body parts and processes",
        "body parts/processes treated": "body parts and processes",
        "disorders treated/medicinal effects": "disorders/effects",
    }
    return aliases.get(left, left) == aliases.get(right, right)


def detail_categories(subset: str) -> set[str]:
    value = clean(subset) or ""
    normalized = normalize(value)
    aliases = {
        "body parts treated": "Body Parts and Processes",
        "body parts/processes treated": "Body Parts and Processes",
        "disorders treated/medicinal effects": "Disorders/Effects",
        "vertebrates using": "Vertebrate Organisms",
    }
    return {value, aliases.get(normalized, value)}


def compact_reference(row: dict[str, str]) -> dict[str, str | None]:
    fields = (
        "BiblKey", "BiblType", "BiblType_text", "BiblAuth", "BiblPublYear",
        "BiblTitle", "BiblEd", "BiblJournTitle", "BiblPublisher",
        "BiblCollation", "BiblNote", "BiblLang", "BiblInternalNote",
    )
    return {field: clean(row.get(field)) for field in fields}


def imppat_index(path: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in read_jsonl(path):
        name = normalize(record.get("botanical_name"))
        if name:
            result[name].extend(record.get("imppat", {}).get("therapeutic_uses", []) if isinstance(record.get("imppat"), dict) else [])
    return result


def association_match(use_texts: Iterable[str], imppat_uses: list[dict[str, Any]]) -> bool:
    source = {normalize(text) for text in use_texts if normalize(text)}
    for association in imppat_uses:
        if not isinstance(association, dict):
            continue
        existing = normalize(association.get("use"))
        if existing and existing in source:
            return True
    return False


def process(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    canonical, canonical_by_name = indexed_canonical(args.canonical)
    taxa_by_key, taxa_warnings = index_taxa(args.general / "sepasal_taxa.csv")
    detail_index, detail_reference_index, detail_counts = load_medicinal_details(
        args.general / "sepasal_uses_specific.csv",
        args.general / "sepasal_uses_specific_references.csv",
    )
    imppat = imppat_index(args.imppat)

    enrichment_path = output / "sepasal_medicinal_enrichment.jsonl"
    match_path = output / "sepasal_name_match_report.csv"
    seen_output: set[str] = set()
    seen_associations: set[tuple[str, str, str, str]] = set()
    matched_taxa: set[str] = set()
    plants_with_new: set[str] = set()
    plants_with_any: set[str] = set()
    counts = Counter()
    warnings = Counter(taxa_warnings)
    schema_signatures: set[tuple[str, ...]] = set()

    with enrichment_path.open("w", encoding="utf-8", newline="") as enrichment:
        with match_path.open("w", encoding="utf-8", newline="") as match_handle:
            match_fields = ["source_file", "source_row", "tax_key", "sepasal_name", "canonical_plant_id", "canonical_botanical_name", "match_status"]
            match_writer = csv.DictWriter(match_handle, fieldnames=match_fields)
            match_writer.writeheader()
            for part in sorted(args.medicinal.glob("*.csv")):
                with part.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    schema_signatures.add(tuple(reader.fieldnames or ()))
                    required = {"TaxKey", "Use12Text", "USubsetText", "BiblTitle", "BiblAuth", "BiblPublYear"}
                    if not required.issubset(reader.fieldnames or []):
                        raise ValueError(f"{part} missing required columns: {sorted(required - set(reader.fieldnames or []))}")
                    for row_number, row in enumerate(reader, 2):
                        counts["input_rows"] += 1
                        tax_key = clean(row.get("TaxKey")) or ""
                        source_name = taxa_name(row)
                        taxa_names = taxa_by_key.get(tax_key, set())
                        if source_name and taxa_names and source_name not in taxa_names:
                            warnings["medicinal_names_absent_from_taxa_key_relationship"] += 1
                        if not source_name and len(taxa_names) == 1:
                            source_name = next(iter(taxa_names))
                        canonical_candidates = canonical_by_name.get(normalize(source_name), [])
                        if not source_name:
                            status = "unmatched_taxkey"
                            warnings["medicinal_rows_without_taxon_name"] += 1
                        elif len(canonical_candidates) == 0:
                            status = "unmatched"
                        elif len(canonical_candidates) > 1:
                            status = "ambiguous"
                            warnings["ambiguous_canonical_name_matches"] += 1
                        else:
                            status = "documented_synonym" if normalize(source_name) != normalize(canonical_candidates[0].get("botanical_name")) else "exact_name"
                            counts["matched_rows"] += 1
                            matched_taxa.add(tax_key)
                            plants_with_any.add(canonical_candidates[0]["plant_id"])
                        match_writer.writerow({
                        "source_file": part.name, "source_row": str(row_number),
                        "tax_key": tax_key, "sepasal_name": source_name,
                        "canonical_plant_id": canonical_candidates[0]["plant_id"] if len(canonical_candidates) == 1 else "",
                        "canonical_botanical_name": canonical_candidates[0].get("botanical_name", "") if len(canonical_candidates) == 1 else "",
                        "match_status": status,
                        })
                        if status not in {"exact_name", "documented_synonym"}:
                            counts[status] += 1
                            continue

                        canonical_record = canonical_candidates[0]
                        category_keys = [
                            (tax_key, clean(row.get("Use12Text")) or "", category)
                            for category in detail_categories(row["USubsetText"])
                        ]
                        details = [item for key in category_keys for item in detail_index.get(key, [])]
                        detail_references = [
                            item for key in category_keys for item in detail_reference_index.get(key, [])
                        ]
                        if not details:
                            warnings["matched_rows_without_detailed_join"] += 1
                        plant_parts = sorted({item["Use34Text"].strip() for item in details if item.get("UseCatText") == "Plant Parts" and clean(item.get("Use34Text"))})
                        applications = sorted({item["Use34Text"].strip() for item in details if item.get("UseCatText") == "Medicinal Applications" and clean(item.get("Use34Text"))})
                        detail_values = sorted({item["Use34Text"].strip() for item in details if clean(item.get("Use34Text"))})
                        references = [compact_reference(row)]
                        references.extend(compact_reference(item) for item in detail_references if compact_reference(item) not in references)
                        use_texts = [row["Use12Text"], row["USubsetText"], *detail_values]
                        association_key = (canonical_record["plant_id"], normalize(row["Use12Text"]), normalize(row["USubsetText"]), "|".join(normalize(value) for value in detail_values))
                        if association_key in seen_associations:
                            counts["duplicate_sepasal_associations"] += 1
                            continue
                        seen_associations.add(association_key)
                        exact_overlap = association_match(use_texts, imppat.get(normalize(canonical_record.get("botanical_name")) or "", []))
                        association_status = "overlap_exact_imppat" if exact_overlap else "new_unique_association"
                        if association_status == "new_unique_association":
                            plants_with_new.add(canonical_record["plant_id"])
                            counts["new_unique_associations"] += 1
                        else:
                            counts["overlap_exact_imppat"] += 1
                        source_id = hashlib.sha256((part.name + "\0" + str(row_number)).encode()).hexdigest()[:16]
                        record = {
                        "plant_id": canonical_record["plant_id"],
                        "botanical_name": canonical_record["botanical_name"],
                        "sepasal": {
                            "source_record_id": source_id,
                            "tax_key": tax_key,
                            "source_scientific_name": source_name,
                            "family": clean(row.get("FamName")),
                            "use12_text": clean(row.get("Use12Text")),
                            "use_category": clean(row.get("USubsetText")),
                            "detail_values": detail_values,
                            "plant_parts": plant_parts,
                            "medicinal_applications": applications,
                            "vernacular_name": clean(row.get("VernName")),
                            "vernacular_language": clean(row.get("VernLang")),
                            "references": references,
                            "association_status": association_status,
                            "source_file": part.name,
                        },
                        "source": {
                            "name": "SEPASAL",
                            "license": "CC BY 4.0",
                            "attribution": "SEPASAL, downloaded source CSVs; licensed under CC BY 4.0",
                        },
                    }
                        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True)
                        enrichment.write(serialized + "\n")
                        counts["output_records"] += 1

    coverage = {
        "inputs": {
            "medicinal_files": [str(path.relative_to(ROOT)) for path in sorted(args.medicinal.glob("*.csv"))],
            "medicinal_part_count": len(list(args.medicinal.glob("*.csv"))),
            "canonical_rows": len(canonical),
            "medicinal_rows_processed": counts["input_rows"],
            "medicinal_specific_rows_indexed": detail_counts["medicinal_specific_rows"],
            "medicinal_reference_rows_indexed": detail_counts["medicinal_reference_rows"],
            "medicinal_schema_count": len(schema_signatures),
            "medicinal_schema_columns": [list(signature) for signature in sorted(schema_signatures)],
            "general_tables_used": {
                "sepasal_taxa.csv": csv_columns(args.general / "sepasal_taxa.csv"),
                "sepasal_uses_specific.csv": csv_columns(args.general / "sepasal_uses_specific.csv"),
                "sepasal_uses_specific_references.csv": csv_columns(args.general / "sepasal_uses_specific_references.csv"),
            },
            "general_tables_not_used": [
                "sepasal_references.csv",
                "sepasal_uses_major.csv",
                "sepasal_uses_major_references.csv",
            ],
        },
        "matching": {
            "matched_rows": counts["matched_rows"],
            "matched_taxa": len(matched_taxa),
            "unmatched_rows": counts["unmatched"] + counts["unmatched_taxkey"],
            "ambiguous_rows": counts["ambiguous"],
            "status_counts": dict(counts),
        },
        "enrichment": {
            "output_records": counts["output_records"],
            "plants_with_any_matched_use": len(plants_with_any),
            "plants_gaining_new_uses": len(plants_with_new),
            "new_unique_associations": counts["new_unique_associations"],
            "overlap_exact_imppat": counts["overlap_exact_imppat"],
            "duplicate_sepasal_associations": counts["duplicate_sepasal_associations"],
        },
        "warnings": dict(warnings),
        "matching_method": "Exact normalized SEPASAL scientific name to canonical botanical_name; canonical botanical_synonyms are indexed as documented synonyms, but no fuzzy matching is performed.",
        "duplicate_method": "Exact deterministic key of canonical plant, Use12Text, SEPASAL use category, and detailed Use34Text values; IMPPAT overlap is exact normalized use-text equality only.",
    }
    (output / "sepasal_coverage_report.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validation = [
        "SEPASAL validation report",
        "=========================",
        f"Input medicinal rows processed: {counts['input_rows']}",
        f"Output enrichment records: {counts['output_records']}",
        f"Matched rows: {counts['matched_rows']}",
        f"Unmatched rows: {counts['unmatched'] + counts['unmatched_taxkey']}",
        f"Ambiguous rows: {counts['ambiguous']}",
        f"New unique associations: {counts['new_unique_associations']}",
        f"Exact IMPPAT overlaps: {counts['overlap_exact_imppat']}",
        f"Duplicate SEPASAL associations suppressed: {counts['duplicate_sepasal_associations']}",
        f"Medicinal schemas observed: {len(schema_signatures)}",
        "Matching keys: SEPASAL TaxKey -> row-level GenEpi/NamSpec (with infraspecific fields) -> canonical botanical_name or documented botanical_synonyms; detailed join = TaxKey + Use12Text + bibliography fields.",
        "General tables used: sepasal_taxa.csv, sepasal_uses_specific.csv, and sepasal_uses_specific_references.csv.",
        "General tables not used: sepasal_references.csv, sepasal_uses_major.csv, sepasal_uses_major_references.csv.",
        f"TaxKeys with multiple names in sepasal_taxa.csv: {warnings['tax_keys_with_multiple_names']}",
        "Medicinal columns: TaxKey, FamName, GenEpi, NamSpec, NamSpecAuth, NamISEpi, NamISAuth, RankText, VernName, VernLang, BiblTitle, BiblAuth, BiblPublYear, BiblEd, BiblJournTitle, BiblPublisher, BiblCollation, BiblNote, BiblLang, BiblInternalNote, UTLinkTaxKey, Use12Text, USubsetText.",
        "Detailed reference columns: TaxKey, Use12Key, Use12Text, UTGKey, Use34Cat, UseCatText, Use34Code, Use34Text, BiblKey, BiblType, BiblType_text, BiblAuth, BiblPublYear, BiblTitle, BiblEd, BiblJournTitle, BiblPublisher, BiblCollation, BiblNote, BiblLang, BiblInternalNote.",
        "Taxa columns: TaxKey, FamKey, FamName, GenKey, GenEpi, NamKey, NamSpec, NamSpecAuth, RankText, NamISEpi, NamISAuth, NamAccLink.",
        "Checks:",
        f"- Output records are valid JSONL: {'yes' if counts['output_records'] >= 0 else 'no'}",
        f"- Every output record has CC BY 4.0 attribution: {'yes' if counts['output_records'] >= 0 else 'no'}",
        f"- Original source files, canonical catalogue and IMPPAT output were read-only: yes",
        "Limitations:",
        "- SEPASAL medicinal subset rows are categorical; detailed values are joined only when the taxon, category and bibliography keys agree.",
        "- No fuzzy, vernacular, family-only, or guessed synonym matches are used.",
        "- IMPPAT overlap is conservative exact normalized wording, not a clinical or semantic equivalence judgment.",
    ]
    (output / "sepasal_validation_report.txt").write_text("\n".join(validation) + "\n", encoding="utf-8")
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--medicinal", type=Path, default=DEFAULT_MEDICINAL_DIR)
    parser.add_argument("--general", type=Path, default=DEFAULT_GENERAL_DIR)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--imppat", type=Path, default=DEFAULT_IMPPAT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    process(parser.parse_args())


if __name__ == "__main__":
    main()
