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

COPY logic logic
COPY backend-server.py .

CMD ["python", "backend-server.py"]
