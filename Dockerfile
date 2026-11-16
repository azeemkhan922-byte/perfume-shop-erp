# Stage 1: Build Frontend (React / Vite)
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Backend (Python / FastAPI)
FROM python:3.12-slim
WORKDIR /app

# Backend dependencies (including psycopg for Supabase PostgreSQL)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir uvicorn[standard] fastapi -r backend/requirements.txt

# Copy backend files and built frontend static assets
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
