FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /data

# Set environment variables
ENV FLASK_APP=app.py
ENV DATABASE_URL=sqlite:////data/architecture_decisions.db

# Expose port
EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
