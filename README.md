# Architecture Decisions

A simple, self-hosted web application for managing Architecture Decision Records (ADRs) based on the [arc42 Section 9](https://docs.arc42.org/section-9/) format.

## Features

- Create, view, update, and delete architecture decisions
- Track complete update history for each decision
- Search and filter decisions by status
- Clean, responsive web interface
- SQLite database for easy self-hosting
- RESTful API for programmatic access

## ADR Format

Each Architecture Decision Record follows the Michael Nygard format:

- **Title**: Short noun phrase describing the decision
- **Status**: `proposed`, `accepted`, `deprecated`, or `superseded`
- **Context**: Describes the forces at play (technological, political, social, project local)
- **Decision**: The response to the forces, stated in active voice (e.g., "We will...")
- **Consequences**: Resulting context after applying the decision (positive, negative, neutral)

## Installation

### Option 1: Docker (Recommended)

The easiest way to run the application:

```bash
# Clone the repository
git clone <repository-url>
cd architecture-decisions

# Run with Docker Compose
docker compose up -d

# Or build and run with Docker directly
docker build -t architecture-decisions .
docker run -d -p 5000:5000 -v adr-data:/data architecture-decisions
```

Open your browser and navigate to `http://localhost:5000`

To stop the container:
```bash
docker compose down
```

### Option 2: Python

Requirements:
- Python 3.8+
- pip

Setup:

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd architecture-decisions
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to `http://localhost:5000`

## Configuration

The application can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:///architecture_decisions.db` |
| `SECRET_KEY` | Flask secret key | `dev-secret-key-change-in-production` |

Example:
```bash
export DATABASE_URL="sqlite:///path/to/your/database.db"
export SECRET_KEY="your-secure-secret-key"
python app.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/decisions` | List all decisions |
| `POST` | `/api/decisions` | Create a new decision |
| `GET` | `/api/decisions/<id>` | Get a decision with history |
| `PUT` | `/api/decisions/<id>` | Update a decision |
| `DELETE` | `/api/decisions/<id>` | Delete a decision |
| `GET` | `/api/decisions/<id>/history` | Get decision history |

### Example API Usage

Create a new decision:
```bash
curl -X POST http://localhost:5000/api/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Use PostgreSQL for persistent storage",
    "status": "proposed",
    "context": "We need a reliable database for storing user data...",
    "decision": "We will use PostgreSQL as our primary database.",
    "consequences": "Positive: ACID compliance, rich features. Negative: Additional operational overhead."
  }'
```

## Project Structure

```
architecture-decisions/
├── app.py              # Flask application and routes
├── models.py           # SQLAlchemy database models
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── README.md           # This file
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── index.html      # Decision list page
│   └── decision.html   # Decision view/edit page
└── static/             # Static assets
    ├── css/
    │   └── style.css   # Custom styles
    └── js/
        └── app.js      # JavaScript utilities
```

## License

MIT License
