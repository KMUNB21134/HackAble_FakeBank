# Like said in README, do not go here if ur are doing for comp.
#
# A second, genuinely separate automation API - its own OS process, its own
# framework, its own auth mechanism. Started by run.sh / the Docker
# entrypoint alongside app.py, bound to 127.0.0.1:8000 only. It is never
# reachable directly - the only way in is app.py's proxy route at
# /<username>/new/api/<...>, which forwards straight through to whatever
# this returns. See CLAUDE.md for why this exists as a second process
# instead of another Flask blueprint.
import hashlib
import os
import secrets
import sqlite3
import time

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

DB_PATH = os.path.join(os.path.dirname(__file__), 'fakebank.db')

app = FastAPI(title='FakeBank Automation API v2')


def md5_hash(raw_password):
    # Same weak, unsalted hashing app.py uses everywhere else - this file
    # only reads the users/credit_cards tables app.py already created and
    # seeded, so it has to match.
    return hashlib.md5(raw_password.encode()).hexdigest()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


# --- /login and /balance: a real, correctly-implemented token API. ---
# Random 192-bit opaque tokens, looked up server-side - not forgeable, not
# the point of this file. They exist so this is a genuine second way to log
# in and check a balance (same as the old JWT API), so the one deliberate
# bug below is the sole way into anything admin-only, not just one of
# several sloppy mechanisms.
active_tokens = {}  # token -> username, in-memory only, cleared on restart

bearer_scheme = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post('/login')
def login(body: LoginRequest):
    conn = get_db()
    user = conn.execute(
        'SELECT username FROM users WHERE username = ? AND password = ?',
        (body.username, md5_hash(body.password)),
    ).fetchone()
    conn.close()

    if not user:
        raise HTTPException(401, 'Invalid username or password.')

    token = secrets.token_hex(24)
    active_tokens[token] = user['username']
    return {'token': token}


def verify_bearer(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    username = active_tokens.get(creds.credentials)
    if not username:
        raise HTTPException(401, 'Invalid or expired token.')
    return username


@app.get('/balance')
def balance(username: str = Depends(verify_bearer)):
    conn = get_db()
    user = conn.execute('SELECT balance FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return {'username': username, 'balance': user['balance']}


# --- /admin/dump: the actual challenge. ---
# Gated by a single static admin key instead of a per-user token, checked
# with fastapi.security.APIKeyHeader - a real FastAPI auth class, so a
# request missing the header gets a genuine 403 straight from FastAPI
# itself, same as any properly secured endpoint would give.
ADMIN_KEY = secrets.token_hex(8)  # 16 hex chars, generated fresh per process
# start - in-memory only, never logged or written to disk, not in source.
# Long enough that guessing it outright isn't realistic; short enough that
# recovering it via the timing side-channel below is tractable.

admin_key_header = APIKeyHeader(name='X-Admin-Key')


def _leaky_compare(guess: str, real: str) -> bool:
    # --- INTENTIONALLY VULNERABLE ---
    # A hand-rolled, character-by-character comparison instead of
    # secrets.compare_digest - the exact anti-pattern FastAPI's own docs
    # warn about for HTTPBasic/APIKeyHeader credentials. It stops at the
    # first mismatched character, same as Python's own `==` on strings
    # would. On real hardware that kind of difference is normally on the
    # order of nanoseconds - too small to reliably measure over a network
    # dominated by TCP/scheduling jitter. The small delay per confirmed
    # character below stands in for that: same real bug (how much of the
    # guess was right leaks through response time), amplified enough to be
    # practically exploitable for a learning exercise instead of getting
    # lost in noise.
    if len(guess) != len(real):
        return False
    for a, b in zip(guess, real):
        if a != b:
            return False
        time.sleep(0.03)
    return True


def verify_admin_key(key: str = Security(admin_key_header)) -> str:
    if not _leaky_compare(key, ADMIN_KEY):
        raise HTTPException(403, 'Invalid admin key.')
    return key


@app.get('/admin/dump')
def admin_dump(_: str = Depends(verify_admin_key)):
    conn = get_db()
    users = [dict(row) for row in conn.execute('SELECT username, password FROM users').fetchall()]
    cards = [dict(row) for row in conn.execute('SELECT owner, card_hash FROM credit_cards').fetchall()]
    conn.close()
    return {'users': users, 'credit_cards': cards}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000)
