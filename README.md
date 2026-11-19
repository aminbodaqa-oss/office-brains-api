# Office Brains API — foundation v0.1

Independent Python backend foundation for the virtual office project.

## What is included

- FastAPI service with health and status endpoints.
- Initial directory of 13 specialist employees.
- SQLite storage for employee memories.
- API-key protection for memory creation.
- No external AI API and no fake/simulated AI answers.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m app.main
```

Open `http://127.0.0.1:8000/docs`.

## Bot-Hosting startup command

Use this only if the panel accepts a shell startup command:

```bash
python -m app.main
```

Install dependencies from `requirements.txt`.

## Endpoints

- `GET /health`
- `GET /api/status`
- `GET /api/employees`
- `GET /api/employees/{employee_id}`
- `GET /api/employees/{employee_id}/memories`
- `POST /api/employees/{employee_id}/memories` (requires `X-API-Key`)

Set `OFFICE_API_KEY` in the hosting environment before using the memory-write endpoint.

## Important hosting note

The free Bot-Hosting plan shown in the user's panel has very limited memory. This project intentionally does not install a local language model. The current milestone is the API, employee directory, and persistent-memory interface. Confirm that the host provides persistent disk before relying on SQLite data across redeployments.
