# Name Classify API

[![Live Demo](https://img.shields.io/badge/Live%20Demo-View%20API-blue?logo=fastapi)](https://name-classify-api.fastapicloud.dev)

A FastAPI backend service that classifies a person's likely profile from a name using external public APIs, then stores and serves the result from a PostgreSQL database.

---

** [Live Demo](https://name-classify-api.fastapicloud.dev)**

---

## Features

- Create a profile from a name using:
  - [Genderize](https://api.genderize.io)
  - [Agify](https://api.agify.io)
  - [Nationalize](https://api.nationalize.io)
- Save enriched profile data in PostgreSQL
- Fetch one profile by ID
- Fetch all profiles with filters
- Delete profile by ID
- Standardized JSON response format

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- HTTPX

## Project Structure

```text
.
|-- app.py
|-- database.py
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
|-- utils/
|   |-- custom_content.py
|   |-- generate_id.py
|   `-- get_age_group.py
`-- requirements.txt
```

## How It Works

1. `POST /api/profiles` receives a name.
2. The API validates the name format.
3. If the name already exists in the database (case-insensitive), the existing record is returned.
4. If not, the service concurrently calls Genderize, Agify, and Nationalize.
5. It computes:
   - `age_group` from age (`child`, `teenager`, `adult`, `senior`)
   - most likely country from Nationalize probabilities
6. The profile is stored and returned in a normalized response.

## Prerequisites

- Python 3.10+
- PostgreSQL database
- `pip`

## Setup

1. Clone the repository:

   ```bash
   git clone <your-repo-url>
   cd name-classify-stage-1
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   Windows (PowerShell):

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create an environment file:

   Create a `.env` file in the project root with:

   ```env
   ENV=development
   LOCAL_DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>
   PROD_DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>
   ```

   Notes:
   - If `ENV=development`, `LOCAL_DATABASE_URL` is used.
   - Any other `ENV` value uses `PROD_DATABASE_URL`.

5. Run the API:

   ```bash
   uvicorn app:app --reload
   ```

6. Open docs:
   - Swagger UI: `http://127.0.0.1:8000/docs`
   - ReDoc: `http://127.0.0.1:8000/redoc`

## API Endpoints

### Health/Welcome

- `GET /`
  - Response:
    ```json
    { "message": "Welcome to Name Classify API" }
    ```

### Create Profile

- `POST /api/profiles`
- Request body:

  ```json
  {
    "name": "Bolaji"
  }
  ```

- Success response:
  - Status: `200 OK`
  - Body shape:

  ```json
  {
    "status": "success",
    "data": {
      "id": "019...",
      "name": "Bolaji",
      "gender": "male",
      "gender_probability": 0.98,
      "sample_size": 1234,
      "age": 27,
      "age_group": "adult",
      "country_id": "NG",
      "country_probability": 0.65,
      "created_at": "2026-04-16T10:30:00Z"
    }
  }
  ```

- Common error statuses:
  - `400` for missing/empty name
  - `422` for invalid name format
  - `502` for upstream API failure/invalid external data

### Get Profile by ID

- `GET /api/profiles/{id}`
- Success response:
  - Status: `200 OK`
  - Includes full profile in `data`
- Error response:
  - `404` if profile is not found

### Get All Profiles (with filters)

- `GET /api/profiles`
- Optional query params:
  - `gender` (string)
  - `country_id` (string)
  - `age_group` (`child` | `teenager` | `adult` | `senior`)
- Success response:
  - Status: `200 OK`
  - Returns:
    - `count`: number of records returned
    - `data`: list of simplified profile objects

### Delete Profile

- `DELETE /api/profiles/{id}`
- Success response:
  - Status: `204 No Content`
- Error response:
  - `404` if profile is not found

## Response Format

The API uses a unified response envelope:

```json
{
  "status": "success",
  "message": "optional",
  "count": 0,
  "data": {}
}
```

- `message`, `count`, and `data` are included only when relevant.

## Data Model

Stored `Profile` fields:

- `id` (UUIDv7 string)
- `name`
- `gender`
- `gender_probability`
- `sample_size`
- `age`
- `age_group`
- `country_id`
- `country_probability`
- `created_at` (UTC timestamp)

## Notes

- CORS currently allows all origins (`*`).
- Tables are created at startup via `Base.metadata.create_all(engine)`.
- A global exception handler returns:
  - `500` with message: `"Upstream or server failure"`

## Author

Built by MadukaJP.
