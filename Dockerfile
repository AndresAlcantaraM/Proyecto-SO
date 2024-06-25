FROM postgres:12.11
COPY database.sql /docker-entrypoint-initdb.d/1.database.sql
