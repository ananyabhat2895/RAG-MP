# Verified medicinal-use coverage report

Generated from the raw files on 2026-10-12. No RAG, chunk, embedding, or vector-database files were read or changed.

## Current data

| Measure | Count |
|---|---:|
| Canonical plant records | 951 |
| Enriched plant records | 951 |
| IMPPAT plant catalogue rows | 4154 |
| IMPPAT plants with at least one therapeutic-use row | 4109 |
| IMPPAT therapeutic-use rows | 94261 |
| Distinct IMPPAT plant/use pairs | 63737 |
| Distinct IMPPAT plant/part/use triples | 94261 |
| Distinct therapeutic-use labels | 1298 |
| Distinct nonblank plant-part labels | 30 |
| IMPPAT rows with blank plant part | 22989 |
| Canonical/enriched plants with embedded therapeutic uses | 701 |
| Canonical/enriched plants without embedded therapeutic uses | 250 |

The 250 plants without embedded therapeutic-use records are listed in `plants_missing_therapeutic_use.csv`. The embedded records contain 52,598 associations, 12,695 of which have no plant part. IMPPAT uses controlled-looking labels but they are reported traditional/database associations, not proof of clinical efficacy.

## Matching

A deterministic name pass over accepted botanical-name fields and retained synonym/source-name fields produced 705 single-ID matches, including 703 with therapeutic data and 2 without it. It found 20 records with multiple IMPPAT IDs and 226 with no deterministic name match. These results are detailed in `name_match_validation.csv`; uncertain matches were not merged.

## Interpretation for target questions

Cough is represented as an IMPPAT therapeutic-use label where present, but plant-part completeness is variable. Neem can be answered only from its existing record(s) and should retain the database wording and provenance. For plants in the 250-record missing set, the current dataset cannot support a medicinal-use answer without a separately verified source.
