# data tier: postgres runs these files in name order the first time it starts with an empty database
FROM postgres:18 AS db
COPY db/schema.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY db/seed.sql /docker-entrypoint-initdb.d/02-seed.sql

# Logic tier: gRPC server
FROM python:3.14-slim AS logic
WORKDIR /festhub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY logic/services.py logic/repository.py ./
COPY backend-server.py ./backend_server.py
COPY festhub_pb2.py festhub_pb2_grpc.py ./

EXPOSE 50051
CMD ["python", "backend_server.py"]

# Presentation tier: Flask web app
FROM python:3.14-slim AS web
WORKDIR /festhub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY website.py ./
COPY templates/ ./templates/
COPY festhub_pb2.py festhub_pb2_grpc.py ./

EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "website:app", "run", "--host=0.0.0.0", "--port=5000"]
