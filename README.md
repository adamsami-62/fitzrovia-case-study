# Fitzrovia Rental Comp Scraper

Automated competitive rental intelligence for eleven Toronto midtown buildings. Scrapes pricing and promotions, stores it, and shows it through a dashboard with drill-down, PDF export, and a small AI chat.

Submitted for the AI & Software Development intern case study at Fitzrovia Asset Management.

## What it does

Pulls live data from each of the 11 competitor buildings, normalizes it into a shared schema, runs the raw incentive text through Claude to structure it, and serves everything through a FastAPI backend and a Next.js frontend. Admin users can trigger a fresh scrape from the UI, anyone logged in can export the consolidated view as a PDF or ask the data questions in plain English.

## Current coverage

| # | Building | Scraper key | Pattern | Units | Incentive |
|---|---|---|---|---|---|
| 1 | Parker | `parker` | RentSync embedded JSON | 32 | Yes |
| 2 | Story of Midtown (73 Broadway) | `story_of_midtown_73` | RentSync Navigator widget | 1\* | Yes |
| 3 | Story of Midtown (75 Broadway) | `story_of_midtown_75` | RentSync Navigator widget | 1\* | Yes |
| 4 | The Selby | `the_selby` | Tricon Vue widget | 19 | Yes |
| 5 | eCentral | `ecentral` | RentCafe + jQuery | 8 | Yes |
| 6 | The Montgomery | `the_montgomery` | Cloudflare blocked | 0 | No |
| 7 | The Whitney | `the_whitney` | WordPress + Elementor | 17 | No |
| 8 | The Hampton | `the_hampton` | Arcanos + Lift framework | 13 | Yes |
| 9 | E18HTEEN | `e18hteen` | Rentsync Gateway REST | 8 | Yes |
| 10 | Corner on Broadway | `corner_on_broadway` | Vue + external JS file | 13 | Yes |
| 11 | Akoya Living | `akoya_living` | Rentsync Gateway REST | 7 | Yes |

Total: 119 units, 9 incentives captured, 1 documented failure.

\* Story of Midtown is paginated by floor. The current scraper only reads the default-visible floor per building. See known limitations.

## How each scraper works

Every scraper inherits from a pattern base class and returns the same `ScrapeResult` dataclass regardless of how it got the data. The runner fires them in parallel with `asyncio.gather` and hands results to a single persistence layer.

- **Parker.** Fetches the floorplans page and pulls a JSON blob out of a hidden `<div id="units_details_data">`. Incentive comes from the home page modal in a second request.
- **Story of Midtown (73 and 75).** Playwright waits for a `<floorplan-navigator>` web component to hydrate the DOM, then walks the rendered unit cards. Two buildings share one site with tab switching.
- **The Selby.** Tricon's Vue widget only renders the list on click. The scraper dismisses the OneTrust cookie banner, clicks the List View tab, loops Load More until the button disappears, then parses rows.
- **eCentral.** The availability dates load asynchronously via a securecafe AJAX call, so the scraper waits five seconds after the page loads before reading.
- **The Montgomery.** Blocked by Cloudflare's challenge page. See below.
- **The Whitney.** Server-rendered WordPress. The scraper walks anchor tags with `data-link` attributes, checks that the parent row is visible, and reads paragraphs positionally.
- **The Hampton.** Arcanos uses the Lift framework, which hoists form modals out of the suite blocks after hydration but leaves the `modal-suite-N` ID behind. The scraper recovers the suite ID from that pattern. Unit types come from floorplan PDF filenames, with hardcoded overrides for the five units that don't have a PDF. Incentive comes from a second site, thehampton.ca.
- **E18HTEEN.** No browser automation. A single HTTP GET to `website-gateway.rentsync.com` returns JSON with every unit. Incentive regex-matched from `#rdPromotionBanner` on myrental.ca.
- **Corner on Broadway.** Also no browser. Fetches `/js/suites.js`, strips JS line comments so the commented-out floorplans don't break JSON parsing, loads the `suitData` array. Second fetch for the promo banner.
- **Akoya Living.** Same gateway base as E18HTEEN, but the homepage runs three concurrent promos in a slider. The scraper concatenates all of them so the parser can split them into separate structured promos.

### Why Montgomery fails

The Montgomery's site sits behind Cloudflare's JS challenge tier. Both headless Playwright and Playwright with stealth get served the "Just a moment..." challenge page instead of real content.

Two ways to fix it:

1. Scrape from an alternative listing site that carries the same data (Rentals.ca or similar aggregators). The Rentals.ca base scraper is already built in the codebase for this purpose.
2. Use an AI-powered scraping approach where a Playwright browser is driven by a vision model that can recognize the content once the page has loaded, bypassing the challenge through real browser behavior.

Either adds cost and complexity the rest of the pipeline doesn't need, which is why the scraper currently returns a failed status with a documented reason rather than silently missing. The dashboard flags it as unscrapable.

## File structure

```
fitzrovia-case-study/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, CORS, startup seeding
│   │   ├── config.py              # pydantic-settings loaded from .env
│   │   ├── database.py            # SQLAlchemy engine and session
│   │   ├── models.py              # Building, Unit, ScrapeRun, ScrapeSnapshot, User
│   │   ├── auth.py                # JWT and bcrypt primitives
│   │   ├── init_db.py             # Table creation and seed data
│   │   ├── api/
│   │   │   ├── auth_routes.py     # POST /auth/login
│   │   │   ├── dashboard_routes.py# GET /dashboard, GET /buildings/{id}
│   │   │   ├── scrape_routes.py   # POST /scrape/trigger (admin only)
│   │   │   ├── export_routes.py   # GET /export/pdf
│   │   │   ├── chat_routes.py     # POST /chat/ask
│   │   │   └── schemas.py
│   │   ├── ai/incentive_parser.py # Raw incentive text to structured JSON
│   │   ├── pdf/                   # WeasyPrint renderer and Jinja template
│   │   └── scrapers/              # Base classes and 11 building scrapers
│   ├── scripts/test_all_scrapers.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── login/page.tsx
│   │   ├── dashboard/page.tsx
│   │   └── buildings/[id]/page.tsx
│   ├── components/                # Shell, tables, filters, chat bubble
│   ├── lib/                       # API client, auth helpers, types
│   └── package.json
├── render.yaml
└── .env.example
```

## Running locally

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
playwright install --with-deps chromium
cp .env.example .env    # fill in credentials
python3 -m backend.app.init_db
uvicorn backend.app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`, sign in with the admin credentials from `.env`, and hit "Scrape now" to populate data.

## Security

The login is a real auth system, not a placeholder.

Passwords are hashed with bcrypt (via passlib) using a per-user random salt and cost factor 12. The plain text password never hits the database, logs, or any response. Verification is constant-time so timing attacks can't leak partial matches.

Successful login issues a JWT signed with HS256 against a random `JWT_SECRET` generated at install time. Tokens expire after 60 minutes with no sliding refresh. The user's role (admin or viewer) lives in the token claim so the admin-only scrape endpoint can enforce access without a database hit.

Role access:

| Endpoint | Viewer | Admin |
|---|---|---|
| `/auth/login` | yes | yes |
| `/dashboard`, `/buildings/{id}` | yes | yes |
| `/chat/ask` | yes | yes |
| `/export/pdf` | yes | yes |
| `/scrape/trigger` | no (403) | yes |

Things a real production version would add that this doesn't: rate limiting on login, account lockout after repeated failures, refresh tokens so stolen tokens can be revoked, and secrets stored in a manager rather than an `.env` file.

## Chat feature

The dashboard has a floating chat bubble in the bottom right. Ask it questions like "how many 1 bedrooms are available" or "which building has the best incentive" and it answers grounded in the latest scrape. Runs on Claude Haiku 4.5 with the current dashboard data injected into the prompt on every question.

## Incentive parser

Raw incentive strings go through Claude to produce structured JSON with months free, cash bonus, deadline, free perks, and conditions. Vague language like "up to 2 months" sets `months_free: 2` with `months_free_is_estimate: true` so the ceiling is preserved without overstating. When the API fails, the parser returns a fallback dict rather than raising, and the persistence layer leaves the incentive hash stale so the next scrape retries automatically.

## Known limitations

- **Montgomery blocked by Cloudflare.** Options for fixing are listed above.
- **Story of Midtown captures one floor per building.** Would need to iterate the floor navigator. An alternative site (hazelviewproperties.com/residential/story-of-midtown) exposes the same listings in a simpler format and could be scraped in full with less complexity.
- **SQLite on Render's free tier is ephemeral.** Every deploy or cold start rebuilds an empty database. Buildings and users reseed on boot but unit data is empty until someone triggers a scrape. A paid Postgres tier fixes it.
- **No scheduled scrapes yet.** Runs happen on manual trigger. A cron or a background task would handle daily refreshes.
- **`ScrapeSnapshot` rows are being written but not yet visualized.** Historical trend charts would be the next UI addition.

## Tech stack

FastAPI, SQLAlchemy 2.0, Pydantic v2, Playwright, httpx, passlib/bcrypt, python-jose, WeasyPrint, Jinja2, anthropic SDK on the backend. Next.js 14 app router, React 18, TypeScript, and Tailwind CSS on the frontend.

Deployment target: Vercel for the frontend, Render for the backend.