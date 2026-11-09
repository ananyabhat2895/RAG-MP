# Candidate dataset evaluation

## IMPPAT therapeutic-use tables - integrate as the current baseline
- Files: `external-data/impatt_plants.tsv` and `external-data/impatt_therapeutic_uses.tsv`.
- Identity: stable IMPPAT plant identifier plus botanical name and synonym field.
- Coverage: 4154 plant rows; 4109 have use rows; 94261 raw use rows.
- Specificity: therapeutic-use label plus optional plant part; 22989 use rows omit part.
- Provenance: source identifiers and original wording are retained in enriched records, but the TSV itself does not provide per-association bibliographic references.
- Recommendation: retain as the canonical structured-use source; deduplicate only by plant ID/part/use while preserving raw rows.

## IMPPAT formulation files - not present
No downloaded formulation/formula file was found outside excluded RAG paths. Formulations are also out of scope for this phase.

## SEPASAL - not present
No SEPASAL file, manifest, or downloaded table exists in the repository. Coverage, columns, identity keys, licensing, and incremental associations therefore cannot be verified from local data. Do not claim SEPASAL improves coverage until an authorized copy is obtained and audited.

## External claims pilot / PMC literature - useful only as a review queue
- `data-analysis/external-claims-pilot/expanded/approved_claims.jsonl` contains 489 approved claim records covering 169 plants.
- Evidence types include traditional-use reports, in-vitro, animal, systematic-review, observational, and clinical records; it is not a normalized therapeutic-use table.
- 128 claims specify a plant part; 361 do not. All approved claims have a source URL and CC BY license in the current manifest.
- The nine part-bearing traditional-use-labelled claims include experimental findings and contextual statements; they must not be converted into a generic medicinal-use label without human review. They are exported verbatim to `proposed_review_candidates.csv` with an empty normalized-use field.
- Recommendation: do not merge automatically. It may later supplement IMPPAT as evidence-level literature, keeping claim text, evidence type, limitations, license, and source identifiers separate from plant-level therapeutic associations.

## BSI medicinal-plant database - not downloaded
The local access report records individual records but no official bulk/API endpoint, explicit reuse terms, or permitted automated bulk retrieval. No scale extraction was performed. Treat as a possible future source pending permission and licensing review.
