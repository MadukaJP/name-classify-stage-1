# Name Classify API

[![Live API](https://img.shields.io/badge/Live%20API-Online-blue?logo=fastapi)](https://name-classify-api.fastapicloud.dev/)
[![Docs](https://img.shields.io/badge/Swagger-Docs-green)](https://name-classify-api.fastapicloud.dev/docs)

`Name Classify API` is a FastAPI service that accepts a person's name, calls three public prediction APIs, applies classification logic, stores the result in PostgreSQL, and exposes endpoints to retrieve, filter, and delete saved profiles.

## Live Links

- Base URL: [https://name-classify-api.fastapicloud.dev/](https://name-classify-api.fastapicloud.dev/)
- Swagger Docs: [https://name-classify-api.fastapicloud.dev/docs](https://name-classify-api.fastapicloud.dev/docs)
- ReDoc: [https://name-classify-api.fastapicloud.dev/redoc](https://name-classify-api.fastapicloud.dev/redoc)

## Features

- Creates a classified profile from a submitted name
- Calls `Genderize`, `Agify`, and `Nationalize` concurrently
- Stores data persistently in PostgreSQL
- Prevents duplicate records for the same name
- Supports profile lookup by ID
- Supports filtering by `gender`, `country_id`, and `age_group`
- Uses UUID v7 IDs and UTC ISO 8601 timestamps
- Returns a consistent JSON response structure

## External APIs Used

- [Genderize](https://api.genderize.io)
- [Agify](https://api.agify.io)
- [Nationalize](https://api.nationalize.io)

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- HTTPX
- Uvicorn

## Project Structure

```text
.
|-- app.py
|-- database.py
|-- requirements.txt
|-- models/
|   |-- base.py
|   `-- profile.py
|-- routes/
|   `-- profile.py
|-- services/
|   `-- external_apis.py
|-- pydantic_schemas/
|   |-- profile_create.py
|   |-- profile_out.py
|   `-- profiles_out.py
`-- utils/
    |-- custom_content.py
    |-- generate_id.py
    `-- get_age_group.py
```

## How It Works

1. A client sends a name to `POST /api/profiles`.
2. The API trims and validates the name.
3. It checks the database for an existing record using a case-insensitive name lookup.
4. If no record exists, it fetches data from the three external APIs in parallel.
5. It derives:
   - `age_group` from the returned age
   - `country_id` from the highest-probability country in Nationalize
6. The API stores the profile and returns it.
7. If the profile already exists, the existing record is returned instead of creating a duplicate.

## Classification Rules

- `0-12` -> `child`
- `13-19` -> `teenager`
- `20-59` -> `adult`
- `60+` -> `senior`

For nationality, the API selects the country with the highest probability from the Nationalize response.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- PostgreSQL
- `pip`

### Installation

1. Clone the repository:

```bash
git clone <your-repo-url>
cd name-classify-stage-1
```

2. Create a virtual environment:

```bash
python -m venv venv
```

3. Activate it:

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
ENV=development
LOCAL_DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>
PROD_DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>
```

Behavior:

- `ENV=development` uses `LOCAL_DATABASE_URL`
- any other value uses `PROD_DATABASE_URL`

### Run Locally

```bash
uvicorn app:app --reload
```

Local docs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## API Endpoints

### `GET /`

Returns a simple welcome response.

```json
{
  "message": "Welcome to Name Classify API"
}
```

### `POST /api/profiles`

Creates a new profile from a submitted name.

Request body:

```json
{
  "name": "ella"
}
```

New profile response:

- Status: `201 Created`

```json
{
  "status": "success",
  "data": {
    "id": "019...",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "sample_size": 1234,
    "age": 46,
    "age_group": "adult",
    "country_id": "NG",
    "country_probability": 0.85,
    "created_at": "2026-04-01T12:00:00Z"
  }
}
```

Duplicate profile response:

- Status: `200 OK`

```json
{
  "status": "success",
  "message": "Profile already exists",
  "data": {
    "id": "019...",
    "name": "ella"
  }
}
```

### `GET /api/profiles/{id}`

Returns a single saved profile by ID.

- Status: `200 OK`

### `GET /api/profiles`

Returns all profiles, optionally filtered by query parameters.

Supported query parameters:

- `gender`
- `country_id`
- `age_group`

Example:

```text
/api/profiles?gender=male&country_id=NG
```

- Status: `200 OK`

### `DELETE /api/profiles/{id}`

Deletes a saved profile.

- Status: `204 No Content`

## Response Format

Successful responses follow this shape:

```json
{
  "status": "success",
  "data": {}
}
```

Additional fields such as `message` and `count` are included when needed.

Error responses follow this shape:

```json
{
  "status": "error",
  "message": "Profile not found"
}
```

## Error Handling

Possible error responses include:

- `400 Bad Request` -> missing or empty name
- `422 Unprocessable Entity` -> invalid name format
- `404 Not Found` -> profile not found
- `502 Bad Gateway` -> external API returned invalid data
- `500 Internal Server Error` -> unexpected server failure

External API edge cases handled:

- `Genderize` returns `gender: null` or `count: 0`
- `Agify` returns `age: null`
- `Nationalize` returns no country data

## Data Model

Each stored profile contains:

- `id`
- `name`
- `gender`
- `gender_probability`
- `sample_size`
- `age`
- `age_group`
- `country_id`
- `country_probability`
- `created_at`

## Notes

- IDs are generated as UUID v7 values
- Timestamps are returned in UTC ISO 8601 format
- CORS is enabled for all origins
- Tables are created automatically on application startup

## Author

Built by `MadukaJP`.
