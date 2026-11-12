# One container = API + website. Used by Render (free). Build: React -> static files, then Python serves both.
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json ./
RUN pip install --no-cache-dir --system -r backend/requirements.txt
COPY frontend/ ./
RUN pip install --no-cache-dir -r backend/requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --system -r backend/requirements.txt

COPY backend/ backend/
COPY --from=web /web/dist frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
