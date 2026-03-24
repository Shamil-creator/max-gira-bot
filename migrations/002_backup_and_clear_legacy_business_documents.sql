BEGIN;

CREATE TABLE IF NOT EXISTS business_documents_legacy_backup AS
SELECT *
FROM business_documents
WHERE FALSE;

INSERT INTO business_documents_legacy_backup
SELECT *
FROM business_documents;

TRUNCATE TABLE business_documents;

COMMIT;
