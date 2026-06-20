# 已迁移至 docker/Dockerfile.backend
# 请使用: docker compose up --build
# 或: docker build -f docker/Dockerfile.backend -t kaoyan-backend .

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY data/ data/

RUN mkdir -p uploads/wrong_questions uploads/chat chroma_db

ENV PYTHONPATH=/app/backend
ENV PROJECT_ROOT=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
