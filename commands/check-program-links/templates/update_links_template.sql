-- Update broken learn_more_link URLs with replacement links
-- This updates the translation records that store the actual URLs

-- Colorado programs
UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/snap'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_snap');

UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/colorado-works-tanf'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_tanf');

UPDATE translations_translation_translation
SET text = 'https://www.healthfirstcolorado.com/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'co_medicaid');

UPDATE translations_translation_translation
SET text = 'https://www.rtd-denver.com/fares-passes/pass-programs/live'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'rtdlive');

UPDATE translations_translation_translation
SET text = 'https://cdec.colorado.gov/for-families/colorado-child-care-assistance-program-for-families-cccap'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'cccap');

UPDATE translations_translation_translation
SET text = 'https://hcpf.colorado.gov/child-health-plan-plus'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'chp');

UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/leap'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'leap');

UPDATE translations_translation_translation
SET text = 'https://cdhs.colorado.gov/adult-financial-programs'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'andcs');

UPDATE translations_translation_translation
SET text = 'https://cdec.colorado.gov/for-families/head-start-early-head-start'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'chs');

UPDATE translations_translation_translation
SET text = 'https://tax.colorado.gov/income-tax-topics-earned-income-tax-credit'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'coeitc' LIMIT 1);

UPDATE translations_translation_translation
SET text = 'https://tax.colorado.gov/colorado-child-tax-credit'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'coctc' LIMIT 1);

UPDATE translations_translation_translation
SET text = 'https://impactcharitable.org/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'bca');

UPDATE translations_translation_translation
SET text = 'https://www.denvergov.org/Government/Agencies-Departments-Offices/Agencies-Departments-Offices-Directory/Recycle-Compost-Trash'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'dtr');

UPDATE translations_translation_translation
SET text = 'https://bouldercounty.gov/families/financial/nurturing-futures/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'nf');

-- National School Lunch Program (multiple states)
UPDATE translations_translation_translation
SET text = 'https://www.fns.usda.gov/nslp'
WHERE master_id IN (
    SELECT learn_more_link_id FROM programs_program
    WHERE name_abbreviated = 'nslp'
);

-- Federal tax credit
UPDATE translations_translation_translation
SET text = 'https://www.irs.gov/credits-deductions/individuals/child-tax-credit'
WHERE master_id IN (
    SELECT learn_more_link_id FROM programs_program
    WHERE name_abbreviated = 'ctc'
    AND white_label_id = (SELECT id FROM screener_whitelabel WHERE code = 'nc')
);

-- North Carolina
UPDATE translations_translation_translation
SET text = 'https://www.ncdhhs.gov/divisions/social-services/work-first-family-assistance'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'nc_tanf');

-- Illinois
UPDATE translations_translation_translation
SET text = 'https://www.illinois.gov/hfs/MedicalPrograms/Pages/default.aspx'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'il_family_care');

UPDATE translations_translation_translation
SET text = 'https://www.illinois.gov/hfs/MedicalPrograms/AllKids/Pages/default.aspx'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'il_all_kids');

UPDATE translations_translation_translation
SET text = 'https://www.getcoveredillinois.gov/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'il_aca');

UPDATE translations_translation_translation
SET text = 'https://www2.illinois.gov/aging/programs/pages/benefitsaccess.aspx'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'il_bap');

UPDATE translations_translation_translation
SET text = 'https://www.rtachicago.org/riders/free-and-reduced-fare-programs'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'il_transit_reduced_fare');

-- Massachusetts
UPDATE translations_translation_translation
SET text = 'https://www.mahealthconnector.org/'
WHERE master_id = (SELECT learn_more_link_id FROM programs_program WHERE name_abbreviated = 'ma_aca');

-- Show summary of updates
SELECT
    p.name_abbreviated,
    wl.name as white_label,
    tt.text as updated_link
FROM programs_program p
JOIN screener_whitelabel wl ON p.white_label_id = wl.id
JOIN translations_translation t ON p.learn_more_link_id = t.id
JOIN translations_translation_translation tt ON t.id = tt.master_id
WHERE p.name_abbreviated IN (
    'co_snap', 'co_tanf', 'co_medicaid', 'rtdlive', 'cccap', 'chp', 'leap', 'andcs',
    'chs', 'coeitc', 'coctc', 'bca', 'dtr', 'nf', 'nslp', 'ctc', 'nc_tanf',
    'il_family_care', 'il_all_kids', 'il_aca', 'il_bap', 'il_transit_reduced_fare', 'ma_aca'
)
ORDER BY wl.name, p.name_abbreviated;
