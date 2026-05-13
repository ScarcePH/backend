# Repository Guidelines

## Project Structure & Module Organization

This repository is a Flask backend for the ScarcePH Messenger bot and commerce API. The main entry point is `app.py`, which registers bot and API blueprints. API routes live in `api/`, with shared helpers in `api/helpers/`. Messenger workflow code is under `bot/`, organized into `handlers/`, `services/`, `core/`, `state/`, and `utils/`. Database models are in `db/models/`, data-access functions are in `db/repository/`, and SQLAlchemy/Flask-Migrate setup is in `db/database.py`. Alembic migrations live in `migrations/versions/`. Background tasks are in `task/`, image utilities in `services/image/`, and static assets in `static/`.

## Build, Test, and Development Commands

- `python3 -m venv venv`: create the local virtual environment.
- `source venv/bin/activate`: activate the environment before installing or running.
- `pip install -r requirements.txt`: install backend dependencies.
- `python app.py`: run the backend locally.
- `flask db migrate -m "describe change"`: generate an Alembic migration after model changes.
- `flask db upgrade`: apply pending migrations to the configured database.
- `docker-compose up --build`: build and run the service stack when using Docker.

## Coding Style & Naming Conventions

Use Python with 4-space indentation and snake_case names for modules, functions, variables, and migration messages. Keep Flask blueprints grouped by feature in `api/` and bot conversation steps in focused modules under `bot/handlers/`. Prefer `db/repository/` functions for database access instead of embedding complex queries in route handlers. Keep configuration in `config.py` and environment variables.

## Testing Guidelines

No test suite is currently present. When adding tests, place them under `tests/` and name files `test_<feature>.py`. Cover API routes, repository behavior, bot state transitions, and migration-sensitive model changes. Document any required test database or service variables in the PR.

## Commit & Pull Request Guidelines

Recent commits use short, scoped subjects such as `[FIX] model import` and `[BOT]: add chat context 1-2 convo`. Follow that style with an uppercase bracketed scope and an imperative summary, for example `[API]: validate cart item quantity`. Pull requests should include a description, linked issue or task, migration notes, environment variable changes, and sample request/response payloads for API changes.

## Security & Configuration Tips

Load secrets through environment variables or `.env`; never commit tokens, JWT secrets, database URLs, OpenAI keys, Messenger credentials, Redis credentials, or cloud storage keys. Keep CORS origins in `app.py` limited to trusted frontends.


## Agent Roles & Workflow

Default workflow for non-trivial changes:

1. Orchestrator
   - Understand the request.
   - Inspect both frontend and backend when the task may affect both.
   - Create a short plan before editing.
   - Split work into implementation, review, and testing phases.

2. Implementer
   - Make the smallest correct code change.
   - Follow existing project structure and conventions.
   - Do not refactor unrelated code.
   - Do not add new dependencies unless explicitly approved.

3. Reviewer
   - Review the git diff after implementation.
   - Check for bugs, security issues, edge cases, broken API contracts, inconsistent patterns, and unnecessary complexity.
   - Return findings as Critical, Important, and Nice-to-have.
   - Do not make changes during review unless asked.

4. Tester
   - Run the smallest relevant verification commands.
   - Frontend: run `npm run lint` and `npm run build`.
   - Backend: run existing targeted commands if available; if no tests exist, perform import/syntax checks and explain what could not be verified.
   - Report exact command results.

Definition of done:
- Code is implemented.
- Reviewer has checked the diff.
- Tester has run relevant verification.
- Remaining risks are clearly listed.
