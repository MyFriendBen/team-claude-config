-- Export programs - CSV output via psql
-- Run with: psql "your_connection_url" -f export_programs_simple.sql -o output.csv --csv
-- Filters for en-us language code only

SELECT
    p.id AS program_id,
    tt_name.text AS program_name,
    tt_learn.text AS learn_more_link,
    p.name_abbreviated,
    wl.code AS white_label_code,
    wl.name AS white_label_name,
    tt_name.language_code AS name_language,
    p.active
FROM programs_program p
INNER JOIN screener_whitelabel wl ON p.white_label_id = wl.id
INNER JOIN translations_translation t_name ON p.name_id = t_name.id
INNER JOIN translations_translation_translation tt_name ON t_name.id = tt_name.master_id
    AND tt_name.language_code = 'en-us'
INNER JOIN translations_translation t_learn ON p.learn_more_link_id = t_learn.id
INNER JOIN translations_translation_translation tt_learn ON t_learn.id = tt_learn.master_id
    AND tt_learn.language_code = 'en-us'
ORDER BY p.id;
