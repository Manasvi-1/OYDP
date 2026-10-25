-- Destructive: only reverse on a disposable development/test database.
BEGIN;
DROP SCHEMA oydp CASCADE;
COMMIT;
