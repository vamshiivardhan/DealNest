# DealNest

DealNest is an online grocery price-intelligence platform. The backend uses FastAPI, PostgreSQL, and SQLAlchemy. Sample price snapshots are provided for the comparison script; the frontend is planned in React.

## Repository layout

```text
backend/
  app/           FastAPI application, database setup, ORM models, pricing logic
  scripts/       Data and price comparison scripts
  alembic/       PostgreSQL schema migrations
  requirements.txt
data/            Safe sample price snapshots
frontend/        React application (planned)
```

## Backend setup

From the repository root, create a virtual environment and install dependencies:

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate  # Windows: backend\\.venv\\Scripts\\activate
pip install -r backend/requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL` to your PostgreSQL connection string. Start the API from the repository root:

```bash
uvicorn app.main:app --reload --app-dir backend
```

The health endpoint is at `http://127.0.0.1:8000/health` and API docs are at `http://127.0.0.1:8000/docs`.

Apply the schema migrations from `backend/` after confirming `DATABASE_URL` points to the intended database:

```bash
cd backend
alembic upgrade head
```

Compare the included morning and evening sample prices from the repository root:

```bash
python backend/scripts/compare_prices.py
```
