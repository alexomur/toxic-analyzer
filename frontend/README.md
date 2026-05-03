# Toxic Analyzer Frontend

SPA frontend for Toxic Analyzer MVP.

## Stack

- React 19
- TypeScript
- Vite
- React Router
- TanStack Query
- Tailwind CSS
- shadcn-style UI primitives
- Recharts

## Product Routes

- `/` - single-text check with verdict, probability, and explanation
- `/batch` - authenticated dataset check with manual/file intake, analytics, and results table
- `/vote` - authenticated random-text labeling workflow
- `/login` - login form
- `/register` - registration form
- `/texts/:textId` - authenticated text details

## Local Run

For a clean local bootstrap from `frontend/`, use one command:

```powershell
npm run start:setup
```

After dependencies are already installed, frontend development starts with one command:

```powershell
npm start
```

Equivalent command:

```powershell
npm run dev
```

Dependencies install:

```powershell
npm install
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:5068` by default, so local cookie-session auth works without cross-origin browser setup.

Committed defaults live in [`.env.development`](C:/Users/Alexomur/Desktop/projects/toxic-analyzer/frontend/.env.development), so no manual env file is required for standard local development.

If the backend runs elsewhere, configure:

```powershell
VITE_DEV_BACKEND_TARGET=http://localhost:5068
VITE_API_BASE_URL=
```

For a separately hosted frontend build, set `VITE_API_BASE_URL` to the backend origin and ensure backend `Frontend:AllowedOrigins` is configured.

## Docker Compose

The repository root compose stack now includes the frontend:

```powershell
docker compose up --build
```

Local endpoints in compose:

- frontend: `http://127.0.0.1:3000`
- backend API: `http://127.0.0.1:8080`

In compose, the frontend is served by Nginx and proxies `/api`, `/health`, `/openapi`, and `/swagger` to the backend container. This keeps browser auth same-origin from the UI perspective and avoids extra CORS setup for the default stack.

## Checks

```powershell
npm run typecheck
npm run lint
npm run build
```

## Structure

- `src/app` - app shell, providers, routing
- `src/features/auth` - session restore, login, register, logout, protected routing
- `src/features/toxicity` - typed backend API contracts and mutations
- `src/features/batch` - batch analytics helpers and derived dashboard logic
- `src/pages` - route-level product screens
- `src/shared/api` - fetch client, CSRF handling, API errors
- `src/shared/ui` - reusable primitives and product-facing UI blocks
- `src/shared/lib` - formatting, chunking, score helpers

## UI Notes

- The frontend uses one dark-surface visual language across pages instead of large decorative hero sections.
- Primary screens are action-first: the main input or working content should be visible in the first viewport.
- `IBM Plex Sans` is the main UI font for mixed Russian/English copy; `JetBrains Mono` is reserved for identifiers and technical values.
- Teal communicates primary actions and active state; orange is reserved for warning and toxicity emphasis.
- Empty states should stay compact and informative rather than dominate the page.

## Backend Assumptions

- Browser auth uses backend-managed HttpOnly cookies.
- Session-authenticated write requests require `X-CSRF-Token`.
- Single-text analysis always uses `reportLevel=full`.
- Batch requests are limited to 100 items; the frontend chunks larger datasets automatically.
- Text details come from `GET /api/v1/toxicity/texts/{textId}` and require authentication.
- The frontend never talks directly to `model/`.
