#!/bin/sh
set -eu

# psql loads the password from an environment variable and quotes it as a SQL literal.
SDSS_STORAGE_APP_PASSWORD="$(cat /run/secrets/postgres_app_password)"
export SDSS_STORAGE_APP_PASSWORD
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -X --set=ON_ERROR_STOP=1 <<'SQL'
\getenv app_password SDSS_STORAGE_APP_PASSWORD
CREATE ROLE sdss_storage_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOREPLICATION NOBYPASSRLS NOCREATEROLE NOCREATEDB;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
\i /storage-schema/schema.sql
GRANT USAGE ON SCHEMA sdss_storage TO sdss_storage_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA sdss_storage TO sdss_storage_app;
SQL
unset SDSS_STORAGE_APP_PASSWORD
