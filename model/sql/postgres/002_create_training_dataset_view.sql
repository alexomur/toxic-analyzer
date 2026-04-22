CREATE OR REPLACE VIEW {{SCHEMA}}.training_examples_for_training AS
SELECT
    CONCAT('canonical:', id::text) AS record_key,
    'canonical'::text AS record_origin,
    source,
    raw_text,
    normalized_text,
    label
FROM {{SCHEMA}}.canonical_training_texts
WHERE label_status = 'labeled'

UNION ALL

SELECT
    CONCAT('candidate:', id::text) AS record_key,
    'candidate'::text AS record_origin,
    source,
    raw_text,
    normalized_text,
    approved_label AS label
FROM {{SCHEMA}}.training_candidates
WHERE candidate_status = 'approved'
  AND approved_label IS NOT NULL;
