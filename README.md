**Do not read if you are in a competition, as this would contain all the answers.**







# FakeBank.com (vunl)

A deliberately vulnerable Flask + SQLite "bank" login app, built for security
testing practice, training, and CTF-style exercises. **Do not deploy this
anywhere public or reuse any of its patterns in a real application.**

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/python app.py
```

The app starts on `http://0.0.0.0:5005/` and creates `fakebank.db`
(SQLite) on first run, seeded with a few accounts.

## Seeded accounts

| Username                       | Password      |
|--------------------------------|---------------|
| `internAdmin@fakebank.com`     | `password123` |
| `robot@fakebank.com`           | `beepboop123` |
| `crackme@fakebank.com`         | `letmein`     |

## Features

- **Dashboard spending graph** — the dashboard shows a small line graph of
  your last 7 outgoing transfers (date + amount), built from a
  `transactions` table logged on every real transfer.
- **Hidden challenge scoreboard** — `/scoreboard93217` (deliberately unlinked
  from the UI, like Juice Shop's own Score Board) tracks which of the 10
  challenges below you've actually completed, per browser session. Most
  are detected automatically the moment the exploit condition is met
  server-side; the Werkzeug RCE challenge instead requires pasting in a
  flag that's only readable by executing code on the server (e.g. reading
  `.rce_flag` from inside the debugger console) — the one exploit this
  app genuinely cannot observe itself, since the debugger intercepts
  requests before Flask ever routes them. The page is not linked or
  leaked anywhere — reaching it means knowing or guessing the exact URL,
  the first time. Once a session has visited it once, the login page
  grows a hidden shortcut back to it (same invisible-link trick as
  `/view-all-cards`, tracked via `session['found_scoreboard']`), so you
  do not have to remember or re-discover the URL on later visits.
  Whenever a new vulnerability is added to this app, a matching
  scoreboard challenge should be added alongside it.
- **"Chat with Management & IT"** — a button on the login page (`/chat`)
  for the easiest challenge on the scoreboard: asking permission before
  you start testing. It always replies "You are allowed to." regardless
  of what you ask, and sending any message marks the challenge solved -
  a nod to getting real authorization before pentesting anything for
  real.
- **"Check recipient exists"** — a button on the transfer page that looks
  up a username before you send it money. A normal, plausible banking
  feature that happens to be the real solve path for the "Crack a
  Password Hash" scoreboard challenge (see `/check-recipient` below).

## Known vulnerabilities (intentional)

- **SQL injection (`/login`)** — the login query is built with raw string
  interpolation instead of parameterized SQL. Try `internAdmin@fakebank.com'--`
  as the username with any password, or `' OR '1'='1`.
- **SQL injection (`/check-recipient`)** — the "Check recipient exists"
  button on the transfer page hits this endpoint, which builds its query
  the same unsafe way as `/login` but echoes the matched column straight
  back in the response. Unlike `/login` (which only tells you true/false),
  this one is a direct UNION-based dump: `?username=x' UNION SELECT
  password FROM users WHERE username='crackme@fakebank.com'-- ` returns
  that account's raw password hash, ready to crack offline.
- **Weak, guessable passwords** — top-of-wordlist passwords
  (`password123`, `letmein`, etc.), with no complexity or length
  requirements on `/register` either.
- **No brute-force protection** — `/login` has no rate limiting, lockout,
  or CAPTCHA, so it's crackable with tools like Hydra.
- **Hardcoded backdoor route (`/admin_panel1234510`)** — visiting it logs
  anyone in as `internAdmin@fakebank.com` with zero credentials and no auth
  check.
- **`robots.txt` leaks the backdoor** — `Disallow: /admin_panel1234510` in
  `static/robots.txt` hands the "hidden" path to anyone who reads it.
- **Debug mode enabled (Werkzeug console RCE)** — `app.run(debug=True,
  ...)` doesn't just leak tracebacks on unhandled errors; each frame in
  the traceback page is a live, interactive Python shell running
  server-side, protected only by a PIN printed to the server's own
  console log. Reach it (any uncaught exception) and it's full remote
  code execution, not just information disclosure.
- **No audit-log protection** — the `transactions` table isn't
  append-only, signed, or backed up anywhere; it's just rows in the same
  SQLite file as everything else. Anyone who reaches the Werkzeug RCE
  above can run `sqlite3.connect('fakebank.db').execute('DELETE FROM
  transactions')` (or delete a single row) and erase the evidence of a
  transfer — including one they just made themselves. No dedicated
  feature or extra vulnerability needed; it's a direct consequence of
  the RCE challenge already having full read/write access to the
  database file.
- **Weak password hashing** — passwords are stored as unsalted MD5 hashes,
  crackable with tools like John the Ripper or hashcat.
- **Fake gift card code (`/transfer`)** — entering a valid "gift card
  number" shows "Transfer successful!" but silently does nothing; no
  balance is debited or credited. The code is just `md5(today's date)` —
  the same for everyone, all day, and computable offline without ever
  signing up for the newsletter. (The scam is the point.)
- **No recipient validation (`/transfer`)** — money can be sent to any
  username, real or not; a transfer to a nonexistent user still debits
  the sender and the funds simply vanish.
- **Stored XSS (`/dashboard`)** — the welcome message renders the
  logged-in user's username with Jinja's `| safe` filter, disabling
  auto-escaping. Register an account with a username like
  `<img src=x onerror=alert(1)>` (avoid `'` — it'll break the vulnerable
  `/login` query above) and it executes on `/dashboard` every time that
  account logs in.
- **Hidden admin feature, secured only by client-side obscurity
  (`/view-all-cards`)** — the dashboard always includes a link to this
  page for every logged-in user, hidden purely with a screen-reader-only
  CSS class (`.invisible-admin-link`), not by only rendering it for the
  right account. Anyone can find it via view-source, DevTools, or just
  tabbing through the page. The route itself does check
  `session['username'] == 'TheMainAdmin@fakebank.com'` correctly, so
  finding the link only gets you the URL — you still need to become that
  account, which the existing `/login` SQL injection already lets you do
  with no real password. Once in, it dumps every seeded account's hashed
  credit card number from the `credit_cards` table (test PANs, hashed
  with the same weak unsalted MD5 as passwords).
- **Cleartext HTTP, no TLS** — the app only runs `app.run(host='0.0.0.0',
  ...)` with no HTTPS. Every request, including the raw `/login` POST
  body, travels unencrypted. Anyone with network visibility (same
  LAN/Wi-Fi, ARP spoofing, a compromised router) can read credentials
  straight off the wire with a packet capture tool like Wireshark or
  `tcpdump` — no cracking required, the password is sent in plaintext
  before the server ever hashes it. A background thread
  (`start_credential_bot()`) logs the `TheMainAdmin@fakebank.com` account
  in over plain HTTP every 20 seconds using a strong, never-displayed
  password, purely so there's always real cleartext traffic to capture —
  the "Sniff Credentials Off the Wire" scoreboard challenge. Its
  password isn't listed here on purpose; capture it. It also holds the
  largest balance in the bank, matching its name.

## Disclaimer

This project exists purely to demonstrate common web vulnerabilities in a
safe, local, throwaway environment. Only use it against your own local
instance, or in an environment you're explicitly authorized to test. Is not to be made public except by creator.
