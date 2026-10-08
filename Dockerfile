# data tier: postgres runs these files in name order the first time it starts with an empty database
FROM postgres:18 AS db
COPY db/schema.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY db/seed.sql /docker-entrypoint-initdb.d/02-seed.sql

# logic tier (gRPC server): not set up yet
FROM python:3.14-slim AS logic

# presentation tier (gRPC client): not set up yet
FROM python:3.14-slim AS web
