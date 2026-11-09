# Validation report

- Canonical IDs: 951 records and 951 unique IDs; enriched output has the same 951 records and unique IDs.
- IMPPAT plant IDs: 4154 rows and 4154 unique IDs.
- IMPPAT duplicate pressure: 94261 raw rows reduce to 63737 plant/use pairs because the same use can occur with multiple parts or blank/part-specific rows; 94261 plant/part/use triples remain.
- Missing fields: 22989 IMPPAT rows omit plant part; the TSV therapeutic-use rows have no per-row reference field.
- Name uncertainty: 20 canonical records map to multiple IMPPAT IDs; 226 have no deterministic match. Full rows are in `name_match_validation.csv`.
- Candidate claim provenance: 489 approved claims have source URLs and licenses; 361 omit plant part.
- No generated medicinal claims were added. No uncertain taxonomic match was merged. No formulation-level record was merged.

## Integration gate
Only exact/accepted-synonym botanical matches should be eligible for future additions. Preserve `original_use_text`, a separately reviewed `normalized_use_label`, `plant_part`, `source_dataset`, `source_record/reference`, `matching_method`, `matching_confidence`, and evidence type. Keep literature claims distinct from IMPPAT plant-level associations.
