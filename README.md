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
- Supports advanced filtering by `gender`, `age_group`, `country_id`, `min_age`, `max_age`, `min_gender_probability`, and `min_country_probability`
- Supports sorting and pagination
- Supports rule-based natural language search
- Uses UUID v7 IDs and UTC ISO 8601 timestamps
- Returns a consistent JSON response structure

## Query Engine

### `GET /api/profiles`

Supported query parameters:

- `gender`
- `age_group`
- `country_id`
- `min_age`
- `max_age`
- `min_gender_probability`
- `min_country_probability`
- `sort_by=age|created_at|gender_probability`
- `order=asc|desc`
- `page` with default `1`
- `limit` with default `10` and maximum `50`

Example:

```text
/api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10
```

Response format:

```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "data": []
}
```

### `GET /api/profiles/search`

Converts plain-English queries into filters using rule-based parsing only.

How the parser works:

- The query is normalized to lowercase and tokenized with regex-based matching.
- The parser extracts filter groups for `gender`, `age_group`, `age_range`, `country`, and `name`.
- Filters from different groups are combined with `AND`.
- Multiple names are combined with `OR`.
- Duplicate matches are removed while preserving the original order.

Rules:

- Gender keywords map like this:
  - `male`, `males`, `man`, `men`, `boy`, `boys` -> `gender=male`
  - `female`, `females`, `woman`, `women`, `girl`, `girls` -> `gender=female`
- Age group keywords map like this:
  - `child`, `children`, `kid`, `kids`, `toddler`, `toddlers` -> `age_group=child`
  - `teen`, `teens`, `teenager`, `teenagers`, `teenage`, `adolescent`, `adolescents` -> `age_group=teenager`
  - `adult`, `adults` -> `age_group=adult`
  - `senior`, `seniors`, `elder`, `elders`, `elderly` -> `age_group=senior`
- Age phrases map like this:
  - `young adult` -> `age 20-35`
  - `young` -> `age 16-24`
  - `middle-aged` -> `age 36-55`
  - `old` -> `age 56-80`
  - `elderly` -> `age 81-100`
  - `between X and Y` -> `min_age=X`, `max_age=Y`
  - `above X`, `older than X`, `over X`, `at least X`, `more than X` -> `min_age=X`
  - `under X`, `younger than X`, `less than X`, `below X`, `up to X` -> `max_age=X`
  - a standalone number like `30` -> `age=30`
- Country keywords are matched through `pycountry` plus aliases such as `usa`, `u.s.`, `united states`, `united states of america`, and `uk`.
- A standalone alphabetic name query like `john` or `johnson` is treated as a name search when it does not collide with a country, gender, or age term.
- Delimiter-separated name lists like `john and anna`, `john, anna`, or `john / anna` are also treated as name searches.
- Name detection also works when the query includes patterns like `named`, `called`, `name is`, or `names`.
- Queries that cannot be interpreted return `{ "status": "error", "message": "Unable to interpret query" }`.

Examples:

- `young males` -> `gender=male`, `min_age=16`, `max_age=24`
- `females above 30` -> `gender=female`, `min_age=30`
- `people from angola` -> `country_id=AO`
- `adult males from kenya` -> `gender=male`, `age_group=adult`, `country_id=KE`
- `male and female teenagers above 17` -> `gender=male|female`, `age_group=teenager`, `min_age=17`

Response format:

```json
{
  "status": "success",
  "page": 1,
  "limit": 10,
  "total": 2026,
  "data": []
}
```

## Limitations

- The parser is rule-based, so it does not understand free-form intent the way a full NLP model would.
- It does not handle negation such as `not male`, `except adults`, or `without country`.
- It does not support nested boolean logic like `male or female but not senior`.
- It does not infer relative or informal age wording beyond the patterns in the code, such as `in their twenties`, `late thirties`, or `around 40`.
- Standalone numbers are treated as ages, so a number inside an unrelated sentence can be misread as an age filter.
- Country matching is strongest for full country names and the documented aliases, and misspellings outside the fuzzy-match threshold may be missed.
- Name extraction works best for single-name queries, delimiter-separated lists, and explicit phrases like `named John` or `called Anna`; arbitrary names buried inside a longer sentence are not always detected.
- When multiple supported filters appear together, the API combines them into a stricter search, which may return no results if the query is too specific.

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
|-- scripts/
|   `-- seed_profiles.py
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
    "age": 46,
    "age_group": "adult",
    "country_id": "NG",
    "country_name": "Nigeria",
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
- `age_group`
- `country_id`
- `min_age`
- `max_age`
- `min_gender_probability`
- `min_country_probability`
- `sort_by`
- `order`
- `page`
- `limit`

Example:

```text
/api/profiles?gender=male&country_id=NG
```

- Status: `200 OK`

### `GET /api/profiles/search`

Searches profiles using natural language.

Example:

```text
/api/profiles/search?q=male and female teenagers above 17 from Nigeri and USA named John and Anna
```

- Status: `200 OK`
- Supports `page` and `limit`

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

- `400 Bad Request` -> missing or empty parameter
- `400 Bad Request` -> invalid query parameters
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
- `age`
- `age_group`
- `country_id`
- `country_name`
- `country_probability`
- `created_at`

## Seeding

- Seed data is loaded from `data/seed_profiles.json`
- Run the seed script with `python scripts/seed_profiles.py`
- The script adds the repository root to `sys.path` before importing `database`, `models`, and `utils`, so the imports work even though the file lives in `scripts/`
- Re-running the seed script skips duplicate names case-insensitively
- Seeded profiles use normalized names, country codes, and UTC timestamps

## Notes

- IDs are generated as UUID v7 values
- Timestamps are returned in UTC ISO 8601 format
- CORS is enabled for all origins
- Tables are created automatically on application startup

## Author

Built by `MadukaJP`.
