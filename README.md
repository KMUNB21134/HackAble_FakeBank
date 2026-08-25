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

| Username             | Password      |
|-----------------------|---------------|
| `admin`               | `password123` 
| `robot@fakebank.com`  | `beepboop123` |

## Features

- **Dashboard spending graph** — the dashboard shows a small bar chart of
  your last 7 outgoing transfers (date + amount), built from a
  `transactions` table logged on every real transfer.

## Known vulnerabilities (intentional)

- **SQL injection (`/login`)** — the login query is built with raw string
  interpolation instead of parameterized SQL. Try `admin'--` as the
  username with any password, or `' OR '1'='1`.
- **Weak, guessable passwords** — top-of-wordlist passwords
  (`password123`, `letmein`, etc.), with no complexity or length
  requirements on `/register` either.
- **No brute-force protection** — `/login` has no rate limiting, lockout,
  or CAPTCHA, so it's crackable with tools like Hydra.
- **Hardcoded backdoor route (`/admin_panel1234510`)** — visiting it logs
  anyone in as `admin` with zero credentials and no auth check.
- **`robots.txt` leaks the backdoor** — `Disallow: /admin_panel1234510` in
  `static/robots.txt` hands the "hidden" path to anyone who reads it.
- **Debug mode enabled** (`app.run(debug=True, ...)`) — exposes the
  Werkzeug interactive debugger/traceback on unhandled errors.
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
- **Cleartext HTTP, no TLS** — the app only runs `app.run(host='0.0.0.0',
  ...)` with no HTTPS. Every request, including the raw `/login` POST
  body, travels unencrypted. Anyone with network visibility (same
  LAN/Wi-Fi, ARP spoofing, a compromised router) can read credentials
  straight off the wire with a packet capture tool like Wireshark or
  `tcpdump` — no cracking required, the password is sent in plaintext
  before the server ever hashes it.

## Disclaimer

This project exists purely to demonstrate common web vulnerabilities in a
safe, local, throwaway environment. Only use it against your own local
instance, or in an environment you're explicitly authorized to test. Is not to be made public except by creator.
