# Name Classify API

[![Live API](https://img.shields.io/badge/Live%20API-Online-blue?logo=fastapi)](https://name-classify-api.fastapicloud.dev/)
[![Docs](https://img.shields.io/badge/Swagger-Docs-green)](https://name-classify-api.fastapicloud.dev/docs)

`Name Classify API` is now the backend for **Insighta Labs+**, a secure profile intelligence platform. It accepts a person's name, calls public prediction APIs, stores normalized profiles in PostgreSQL, and exposes authenticated APIs shared by the CLI and web portal.

## Live Links

- Base URL: [https://name-classify-api.fastapicloud.dev/](https://name-classify-api.fastapicloud.dev/)
- Swagger Docs: [https://name-classify-api.fastapicloud.dev/docs](https://name-classify-api.fastapicloud.dev/docs)
- ReDoc: [https://name-classify-api.fastapicloud.dev/redoc](https://name-classify-api.fastapicloud.dev/redoc)
- Web Portal: [https://insighta-labs-portal.netlify.app](https://insighta-labs-portal.netlify.app)

## Features

- GitHub OAuth login with PKCE for browser sessions
- CLI OAuth token exchange endpoint for local callback flows
- JWT access tokens with 3-minute expiry
- Rotating refresh tokens with 5-minute expiry and server-side revocation
- HTTP-only web cookies plus CSRF protection for cookie-authenticated mutations
- Role-based access control with `admin` and `analyst` roles
- Per-user rate limiting for authenticated API traffic
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

## System Architecture

Insighta Labs+ is split into three repositories:

- **Backend**: FastAPI, PostgreSQL, Redis, SQLAlchemy, GitHub OAuth, JWT sessions, RBAC, profile APIs.
- **CLI**: Typer/Rich command line app installed as `insighta`; stores local tokens in `~/.insighta/credentials.json`.
- **Web portal**: TanStack Start/React portal that uses the same backend APIs through HTTP-only cookies.

The backend is the single source of truth. The CLI sends bearer tokens, while the web portal sends HTTP-only cookies. Both interfaces use the same `/api/*` endpoints, the same role checks, and the same profile data.

## Authentication Flow

### Web

1. User clicks **Continue with GitHub**.
2. `GET /auth/github` creates a `state`, `code_verifier`, and PKCE `code_challenge`.
3. GitHub redirects back to `GET /auth/github/callback`.
4. The backend validates the one-time state from Redis.
5. The backend exchanges `code + code_verifier` with GitHub.
6. The backend creates or updates the user and sets:
   - `access_token` as an HTTP-only cookie, 3-minute expiry
   - `refresh_token` as an HTTP-only cookie, 5-minute expiry
   - `csrf_token` as a readable double-submit CSRF cookie

### CLI

1. CLI generates its own `state`, `code_verifier`, and PKCE `code_challenge`.
2. CLI starts a temporary local callback server.
3. GitHub redirects to the local callback URL with `code` and `state`.
4. CLI validates the returned `state`.
5. CLI sends `code`, `code_verifier`, and `redirect_uri` to `POST /auth/github/cli/callback`.
6. The backend exchanges the code with GitHub and returns an access/refresh token pair.

## Token Handling

- Access tokens expire after 3 minutes.
- Refresh tokens expire after 5 minutes.
- Refresh tokens are stored server-side as SHA-256 hashes.
- `POST /auth/refresh` revokes the old refresh token immediately and issues a new pair.
- `POST /auth/logout` revokes the active refresh token.
- Web refresh/logout requests use cookies and must include `X-CSRF-Token`.
- CLI refresh/logout requests send the refresh token in the request body and do not require CSRF.

## Role Enforcement

Users are stored in the `users` table with `role`, `is_active`, and GitHub identity fields.

- `analyst`: read-only access to list, detail, search, and export.
- `admin`: full access, including profile creation and deletion.
- Disabled users (`is_active=false`) receive `403 Forbidden` on authenticated requests.

Authorization is centralized in FastAPI dependencies:

- `get_current_user` validates bearer tokens or web cookies.
- `require_admin` builds on `get_current_user` for write/admin endpoints.

## Required API Headers

All `/api/*` requests must include:

```http
X-API-Version: 1
```

Missing version headers return:

```json
{
  "status": "error",
  "message": "API version header required"
}
```

Cookie-authenticated unsafe requests also require:

```http
X-CSRF-Token: <csrf_token cookie value>
```

## Auth Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/auth/github` | Start browser GitHub OAuth with PKCE |
| `GET` | `/auth/github/callback` | Handle browser OAuth callback and set cookies |
| `POST` | `/auth/github/cli/callback` | Exchange CLI `code + code_verifier` for tokens |
| `POST` | `/auth/refresh` | Rotate refresh token and issue a new token pair |
| `POST` | `/auth/logout` | Revoke refresh token and clear web cookies |
| `GET` | `/auth/me` | Return the authenticated user |

## CLI Usage

After installing the CLI globally:

```bash
insighta login
insighta whoami
insighta profiles list --gender male --country NG --age-group adult
insighta profiles list --min-age 25 --max-age 40 --sort-by age --order desc
insighta profiles get <id>
insighta profiles search "young males from nigeria"
insighta profiles create --name "Harriet Tubman"
insighta profiles export --format csv --country NG
insighta logout
```

The CLI stores credentials at `~/.insighta/credentials.json`, sends bearer tokens to the backend, refreshes once on `401`, and asks the user to log in again when the refresh token is expired or revoked.

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
