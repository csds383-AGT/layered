FROM python:3.14-slim
WORKDIR /festhub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY festhub.proto .
RUN python -m grpc_tools.protoc \
    -I . \
    --python_out=. \
    --grpc_python_out=. \
    festhub.proto

COPY website.py .
COPY templates templates

CMD ["python", "-m", "flask", "--app", "website:app", "run", "--host=0.0.0.0", "--port=5000"]
