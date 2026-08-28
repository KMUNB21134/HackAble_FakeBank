# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

FakeBank.com_vunl is an **intentionally vulnerable** Flask + SQLite "bank" app, modeled after OWASP Juice Shop, built for security testing practice, CTF-style training, and education. Every bug is deliberate. When working here:

- Do not "fix" a vulnerability unless explicitly asked to — the entire point of the codebase is that these bugs exist.
- New security-relevant code should follow the existing convention of an explicit `# --- INTENTIONALLY VULNERABLE ---` or `# --- INTENTIONALLY WEAK ---` comment block explaining *why* the code is broken. This is a deliberate exception to writing few comments — for this repo, marking intentional vulnerabilities inline is expected.
- `README.md` is the full spoiler/answer key (`Do not read if you are in a competition`). `Hackers.md` gives light nudges only ("where to look, not what you'll find"). `Answers.md` is a complete step-by-step walkthrough with exact payloads. **Whenever a vulnerability or scoreboard challenge is added or changed, update all three docs to match**, plus the `CHALLENGES` list hint in `app.py`.

## Commands

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh                    # bare-metal run (starts app.py + new_api.py); Ctrl+C cleans up fakebank.db/.rce_flag
```

There is no test suite, linter, or build step. Verification for any change is manual: start the server and hit routes directly with `curl` (or a browser for template/JS changes), including re-testing the exploit paths a change might affect, not just the happy path.

Docker (preferred for anything touching the RCE challenge, since it's genuine arbitrary code execution as the host user otherwise):

```bash
./colima.sh          # macOS, no Docker Desktop needed (installs Colima via Homebrew)
./docker-linux.sh    # Linux/Raspberry Pi OS (installs Docker via apt)
```

Both default to `127.0.0.1`-only; pass `--lan` to publish on the real network interface. See README's "Running in Docker" section for what NOT to do (host volume mounts, publishing beyond localhost) since those undo the container's isolation from the real filesystem.

## Architecture

**Single-file backend, with one deliberate exception.** All routes, DB access, and business logic live in `app.py`. There's no blueprint/package structure — it's one file by design, given the project's scope. `new_api.py` is the one exception: a second, genuinely separate automation API (FastAPI, its own OS process via `uvicorn`, bound to `127.0.0.1:8000` only) fronted by a proxy route in `app.py` (`/<username>/new/api/<path:subpath>`). It's a real second process, not another Flask blueprint, specifically so the network boundary between "gateway" and "backend service" is real and discoverable (e.g. via the proxied `/openapi.json`), not simulated in-process. Its hardest capability (`/admin/dump`) is gated by a genuine `fastapi.security.APIKeyHeader` misuse — a non-constant-time key comparison, opening a timing side-channel — as a second, distinct auth-vulnerability class from the old JWT API's `alg:none`/secret-reuse bugs.

**SQLite via the stdlib `sqlite3` module**, no ORM. `get_db()` opens a fresh connection per call (WAL journal mode + a busy timeout, needed because the server runs `threaded=True` and some routes open more than one connection per request). `init_db()` creates tables and seeds accounts idempotently on every startup — safe to call repeatedly.

**The scoreboard/challenge system is the architectural spine of the vulnerable parts.** `CHALLENGES` (a list of dicts: id, title, difficulty, hint) defines every trackable exploit. `mark_solved(challenge_id)` is called inline from whichever route detects that its specific exploit condition was met (e.g. a real password match on a specific account, a UNION-injected row, a forged token) — solved state is per-browser-session via a `visitor_id` in the Flask session, stored in the `solves` table. The `/scoreboard93217` route (deliberately unlinked anywhere, only discoverable by guessing the URL or reading the source) renders progress against this list. One challenge (`rce_console`) can't be auto-detected server-side at all, because the Werkzeug debugger intercepts `__debugger__=yes` requests before Flask's own routing ever sees them — that one requires POSTing a flag string to the scoreboard instead, and the flag is written to a file (`.rce_flag`) only readable via actual code execution in the debugger console.

**Most "features" are real, working functionality that happens to be the vulnerability**, not vulnerabilities bolted onto a fake feature — e.g. the "Check recipient exists" button on the transfer page is a plausible, useful pre-transfer check that also happens to be a second SQL injection point distinct from `/login`'s; the gift-card code is a real promo mechanic that's also unlimited-use free money; `/api/login` + `/api/balance` are a genuine token-based API alternative to cookie auth that's also forgeable two different ways; `new_api.py`'s `/admin/dump` is gated by a real FastAPI auth dependency (`APIKeyHeader`) that looks properly protected (missing header → a genuine `401`/`403` from FastAPI itself) but leaks its key through response timing. When adding new vulnerable surface, follow this pattern rather than adding an obviously-fake "vuln demo" endpoint.

**Deliberately unlinked routes** (the scoreboard, the hardcoded admin backdoor at `/admin_panel1234510`, the hidden card-viewing feature) are discoverable only by reading `static/robots.txt`, inspecting page source/DevTools for CSS-hidden links (`.invisible-admin-link` in `static/style.css`), or reading the public GitHub source — never linked from the rendered UI. `new_api.py`'s routes follow the same spirit but with a framework-native twist: they're never linked either, but FastAPI's own auto-generated `/openapi.json` (proxied straight through by `app.py`, same as any other subpath) reveals the endpoint list and the `X-Admin-Key` header name to anyone who thinks to ask for it — a realistic discovery path, not a contrived hint.

**`app.secret_key` is a single point of failure used two different ways**: it signs both the Flask session cookie and (via `pyjwt`) the `/api/login` JWTs. It's hardcoded and intentionally exposed in this public repo, so a hint or new challenge exploiting one signing mechanism should generally consider whether it also implies the other is compromised. `new_api.py`'s `ADMIN_KEY` is a deliberately separate secret (random per process start, in-memory only) — it does not extend this single-point-of-failure story, since the point of that challenge is a comparison-timing bug, not a leaked/reused key.

**The credential-sniffing challenge runs as a background thread** (`start_credential_bot()`, started only when `WERKZEUG_RUN_MAIN=true` to avoid double-starting under the debug reloader) that POSTs real credentials to the app's own `/login` over plain HTTP every 20 seconds, purely to generate cleartext traffic for a packet-capture exercise.
