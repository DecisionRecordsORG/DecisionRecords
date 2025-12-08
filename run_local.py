#!/usr/bin/env python3
"""Run the Flask app locally for development."""
import os

# Set environment variables for local development
os.environ['DATABASE_URL'] = 'postgresql://adruser:SecurePass123@adr-postgres-eu.postgres.database.azure.com:5432/postgres?sslmode=require'
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'

# Import and run the app
from app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
