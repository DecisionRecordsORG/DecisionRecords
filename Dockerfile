# Stage 1: Build Angular frontend
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build Angular app for production
RUN npm run build -- --configuration=production

# Stage 2: Python backend with Angular frontend
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY *.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Copy Angular build from frontend-builder
COPY --from=frontend-builder /app/frontend/dist/frontend/browser ./frontend/dist/frontend/browser

# Create directory for database
RUN mkdir -p /data

# Set environment variables
ENV FLASK_APP=app.py
ENV DATABASE_URL=sqlite:////data/architecture_decisions.db

# Expose port
EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
