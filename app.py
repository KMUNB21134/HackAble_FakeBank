# Like said in README, do not go here if ur are doing for comp.
import flask
import hashlib
import jwt
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta

app = flask.Flask(__name__)
app.secret_key = 'not-a-real-secret'  # fine for a local vuln demo, not for prod

DB_PATH = os.path.join(os.path.dirname(__file__), 'fakebank.db')

# Deliberately unlinked and not leaked anywhere (not even robots.txt) -
# reaching it means guessing or otherwise discovering the exact URL.
SCOREBOARD_PATH = '/scoreboard93217'

# --- INTENTIONALLY VULNERABLE ---
# Simulates a real user logging in periodically. Since the app only ever
# serves plain HTTP, every one of these login POSTs (including the real
# password) travels the network in cleartext - anyone capturing packets
# on the wire while this fires can read it straight off, no cracking
# needed. The password is strong on purpose so brute-forcing/wordlists
# will not get you there - only watching the wire will.
BOT_USERNAME = 'TheMainAdmin@fakebank.com'
BOT_PASSWORD = 'Xk9$mQ2vLp8!'
BOT_LOGIN_INTERVAL = 20  # seconds


def _bot_login_once():
    data = urllib.parse.urlencode({
        'username': BOT_USERNAME,
        'password': BOT_PASSWORD,
    }).encode()
    try:
        urllib.request.urlopen('http://127.0.0.1:5005/login', data=data, timeout=5)
    except OSError:
        pass


def start_credential_bot():
    def loop():
        while True:
            time.sleep(BOT_LOGIN_INTERVAL)
            _bot_login_once()

    threading.Thread(target=loop, daemon=True).start()

# Only obtainable by actually executing code via the debugger console (see
# write_rce_flag() below) - this is the one challenge app.py cannot detect
# server-side, since werkzeug's debugger intercepts __debugger__ requests
# before Flask ever routes them.
RCE_FLAG = 'FLAG{d3bug_c0nsole_is_a_full_shell}'
RCE_FLAG_PATH = os.path.join(os.path.dirname(__file__), '.rce_flag')

CHALLENGES = [
    {
        'id': 'management_permission',
        'title': 'Get Permission First',
        'difficulty': 1,
        'hint': 'This bank has a way to ask its own staff for permission before you start testing. Look around the login page.',
    },
    {
        'id': 'robots_leak',
        'title': 'Read robots.txt',
        'difficulty': 1,
        'hint': 'Check what this server publishes about itself by default, before you even log in.',
    },
    {
        'id': 'sqli_login_bypass',
        'title': 'SQL Injection Login Bypass',
        'difficulty': 2,
        'hint': "The login form does not sanitize what you type before it ends up in a database query. See what unexpected characters can do.",
    },
    {
        'id': 'weak_hashing',
        'title': 'Crack a Password Hash',
        'difficulty': 2,
        'hint': "Passwords aren't stored as safely as they should be. The login form isn't the only form on this site that takes a username as input - if you can get your hands on a hash somewhere, offline cracking tools make quick work of the weak ones.",
    },
    {
        'id': 'stored_xss',
        'title': 'Stored XSS via Username',
        'difficulty': 2,
        'hint': 'Something you type during registration is shown again later - pay attention to exactly how.',
    },
    {
        'id': 'fake_gift_card',
        'title': 'Compute the Daily Gift Card Code',
        'difficulty': 2,
        'hint': "The transfer page offers a \"secret\" gift code. Secrets that are the same for every visitor, every day, usually are not very secret.",
    },
    {
        'id': 'hidden_backdoor',
        'title': 'Find the Hardcoded Backdoor',
        'difficulty': 2,
        'hint': 'Not every route on this site needs a password to reach. Some are not supposed to be found at all.',
    },
    {
        'id': 'cleartext_creds',
        'title': 'Sniff Credentials Off the Wire',
        'difficulty': 3,
        'hint': 'This app never uses HTTPS, so a login POST travels the network in plain text. Something on this server logs in with real credentials on its own every so often - if you are watching the network when it happens, you will see exactly what it typed.',
    },
    {
        'id': 'rce_console',
        'title': 'Remote Code Execution via Debug Console',
        'difficulty': 5,
        'hint': "This app doesn't hide its mistakes well. If you can make it crash instead of fail gracefully, look closely at what it shows you next. The PIN guarding the console looks random but is not - it is computed from a handful of predictable facts about the machine running it, not generated fresh each time, which is worth knowing if you ever face this without a terminal open on the server yourself. Once you are executing code on the server, nothing stops you from also opening fakebank.db directly and rewriting or deleting rows in the transactions table - there is no audit-log protection here at all, and every transfer is logged with the real IP address it came from.",
        'flag': RCE_FLAG,
    },
    {
        'id': 'view_all_cards',
        'title': 'Reach the Hidden Card-Viewing Feature',
        'difficulty': 3,
        'hint': "The dashboard has a button nobody can see, for a feature only one specific account is allowed to use. Inspect the page. Then figure out how you have already learned to become someone you are not.",
    },
    {
        'id': 'api_token_forgery',
        'title': 'Forge an API Token',
        'difficulty': 4,
        'hint': "There is a small automation API for scripts and monitoring tools, separate from the normal login. It issues a signed token instead of a cookie. Tokens carry their own claim about which algorithm secured them - what happens if you are the one who gets to make that claim? And if the app trusts one particular value to sign things, where else in this project might that same value be sitting in plain sight?",
    },
]


def md5_hash(raw_password):
    # --- INTENTIONALLY WEAK ---
    # Unsalted MD5 is fast to brute-force and crackable with John the
    # Ripper / hashcat, especially against a plain wordlist.
    return hashlib.md5(raw_password.encode()).hexdigest()


def daily_gift_code():
    # --- INTENTIONALLY WEAK ---
    # "Secret" gift code is just an MD5 hash of today's date - the same
    # for everyone, all day, and trivially computable offline by anyone
    # who knows (or guesses) the server's date. No need to actually sign
    # up for the spam newsletter.
    return hashlib.md5(datetime.now().strftime('%Y-%m-%d').encode()).hexdigest()


def get_db():
    # timeout= gives concurrent writers a chance to retry instead of
    # failing immediately; WAL lets readers and writers avoid blocking
    # each other, which matters now that the server handles requests
    # concurrently (threaded=True) and some routes open more than one
    # connection per request.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 1000.0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TEXT NOT NULL,
            ip_address TEXT
        )
    ''')
    try:
        # Migration for pre-existing local databases created before this
        # column existed - CREATE TABLE IF NOT EXISTS above does not add
        # columns to a table that already exists.
        conn.execute('ALTER TABLE transactions ADD COLUMN ip_address TEXT')
    except sqlite3.OperationalError:
        pass
    conn.execute('''
        CREATE TABLE IF NOT EXISTS solves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT NOT NULL,
            challenge_id TEXT NOT NULL,
            solved_at TEXT NOT NULL,
            UNIQUE(visitor_id, challenge_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            card_hash TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS issued_tokens (
            jti TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            issued_at TEXT NOT NULL
        )
    ''')
    # Seed a couple of accounts so injection has something to find/bypass.
    existing = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if existing == 0:
        conn.executemany(
            'INSERT INTO users (username, password, balance) VALUES (?, ?, ?)',
            [
                ('internAdmin@fakebank.com', md5_hash('password123'), 1337133.70),
                ('robot@fakebank.com', md5_hash('beepboop123'), 4200.00),
                # Weak, wordlist-top password on purpose - cracking this
                # offline (John/hashcat) and logging in with it is the
                # "weak_hashing" challenge.
                ('crackme@fakebank.com', md5_hash('letmein'), 13.37),
                # Strong password on purpose - the credential_bot logs this
                # one in periodically over plain HTTP, so the only realistic
                # way to obtain it is packet capture, not cracking. Highest
                # balance in the bank, matching the account name.
                (BOT_USERNAME, md5_hash(BOT_PASSWORD), 25000000.00),
            ],
        )

    existing_cards = conn.execute('SELECT COUNT(*) AS c FROM credit_cards').fetchone()['c']
    if existing_cards == 0:
        # Well-known public test card numbers (Visa/Mastercard/Amex/Discover
        # test PANs), not real cards - hashed with the same weak, unsalted
        # MD5 as passwords, since this app never gets anything right twice.
        conn.executemany(
            'INSERT INTO credit_cards (owner, card_hash) VALUES (?, ?)',
            [
                ('internAdmin@fakebank.com', md5_hash('4111111111111111')),
                ('robot@fakebank.com', md5_hash('5555555555554444')),
                ('crackme@fakebank.com', md5_hash('378282246310005')),
                (BOT_USERNAME, md5_hash('6011111111111117')),
            ],
        )
    conn.commit()
    conn.close()


def write_rce_flag():
    # Not served by any route - only readable by actually executing code,
    # e.g. from inside the Werkzeug debugger console.
    with open(RCE_FLAG_PATH, 'w') as f:
        f.write(RCE_FLAG + '\n')


def get_visitor_id():
    if 'visitor_id' not in flask.session:
        flask.session['visitor_id'] = secrets.token_hex(8)
    return flask.session['visitor_id']


def mark_solved(challenge_id):
    conn = get_db()
    conn.execute(
        'INSERT OR IGNORE INTO solves (visitor_id, challenge_id, solved_at) VALUES (?, ?, ?)',
        (get_visitor_id(), challenge_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


@app.route('/')
def index():
    found_scoreboard = flask.session.get('found_scoreboard', False)
    return flask.render_template(
        'index.html', found_scoreboard=found_scoreboard, scoreboard_path=SCOREBOARD_PATH
    )


MAX_CHAT_HISTORY = 12  # entries (6 exchanges) - keeps the session cookie small


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    history = flask.session.get('chat_history', [])

    if flask.request.method == 'POST':
        message = flask.request.form.get('message', '').strip()[:300]
        if message:
            history = history + [
                {'from': 'you', 'text': message},
                {'from': 'management', 'text': 'You are allowed to.'},
            ]
            history = history[-MAX_CHAT_HISTORY:]
            flask.session['chat_history'] = history
            mark_solved('management_permission')

    return flask.render_template('chat.html', history=history)


@app.route('/robots.txt')
def robots():
    mark_solved('robots_leak')
    return flask.send_from_directory(app.static_folder, 'robots.txt')


@app.route('/login', methods=['POST'])
def login():
    username = flask.request.form.get('username', '')
    password = flask.request.form.get('password', '')

    # --- INTENTIONALLY VULNERABLE ---
    # Raw string interpolation into SQL instead of parameterized query.
    # e.g. username = internAdmin@fakebank.com' -- to bypass password, or ' OR '1'='1 to
    # log in as the first user / dump results depending on how it's used.
    query = "SELECT * FROM users WHERE username = '{}' AND password = '{}'".format(
        username, md5_hash(password)
    )

    conn = get_db()
    try:
        cursor = conn.execute(query)
        user = cursor.fetchone()
    except sqlite3.Error:
        # Still fully vulnerable to injection (query above is unsanitized) -
        # just no longer leaking the raw DB error text to the page.
        conn.close()
        return flask.render_template('index.html', error='Invalid username or password.')
    conn.close()

    if user:
        flask.session['username'] = user['username']
        if md5_hash(password) != user['password']:
            # Matched a row without actually knowing its real password -
            # only possible via the injection above.
            mark_solved('sqli_login_bypass')
        elif user['username'] == 'crackme@fakebank.com':
            # Real password match on the crackme account means they
            # actually cracked the hash offline.
            mark_solved('weak_hashing')
        elif user['username'] == BOT_USERNAME:
            # Real password match on this account, whose strong password
            # is never shown anywhere, means it was captured off the wire
            # while credential_bot logged it in.
            mark_solved('cleartext_creds')
        return flask.redirect(flask.url_for('dashboard'))

    return flask.render_template('index.html', error='Invalid username or password.')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if flask.request.method == 'GET':
        return flask.render_template('register.html')

    username = flask.request.form.get('username', '')
    password = flask.request.form.get('password', '')

    if not username or not password:
        return flask.render_template('register.html', error='Username and password required.')

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, password) VALUES (?, ?)',
            (username, md5_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return flask.render_template('register.html', error='Username already taken.')
    finally:
        conn.close()

    return flask.redirect(flask.url_for('index'))


@app.route('/dashboard')
def dashboard():
    username = flask.session.get('username')
    if not username:
        return flask.redirect(flask.url_for('index'))

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    rows = conn.execute(
        'SELECT timestamp, amount FROM transactions WHERE sender = ? ORDER BY id DESC LIMIT 7',
        (username,),
    ).fetchall()
    conn.close()

    if re.search(r'[<>]|onerror\s*=|<script', user['username'], re.IGNORECASE):
        mark_solved('stored_xss')

    # Oldest -> newest for a left-to-right chart, each point scaled against
    # the largest amount in the window.
    spending = list(reversed(rows))
    max_amount = max((row['amount'] for row in spending), default=0)
    chart = [
        {
            'date': row['timestamp'][:10],
            'amount': row['amount'],
            'pct': round((row['amount'] / max_amount) * 100) if max_amount else 0,
        }
        for row in spending
    ]

    # Points for an SVG line graph, laid out on a 300x100 viewBox.
    n = len(chart)
    for i, point in enumerate(chart):
        point['x'] = round((i / (n - 1)) * 300, 1) if n > 1 else 150
        point['y'] = round(100 - point['pct'], 1)
    chart_points = ' '.join('{},{}'.format(p['x'], p['y']) for p in chart)

    transfer = flask.request.args.get('transfer') == '1'
    return flask.render_template(
        'dashboard.html', user=user, chart=chart, chart_points=chart_points, transfer=transfer
    )


# --- INTENTIONALLY VULNERABLE ---
# Gated correctly server-side (only BOT_USERNAME's session can view this),
# but the link to it is hidden purely with CSS on every dashboard page
# regardless of who is viewing - security through client-side obscurity.
# Reachable by (a) noticing the hidden button/URL via view-source or
# DevTools, and (b) already knowing how to become BOT_USERNAME without
# its real password, via the existing /login SQL injection.
@app.route('/view-all-cards')
def view_all_cards():
    username = flask.session.get('username')
    if username != BOT_USERNAME:
        return flask.redirect(flask.url_for('index'))

    conn = get_db()
    cards = conn.execute('SELECT owner, card_hash FROM credit_cards ORDER BY id').fetchall()
    conn.close()

    mark_solved('view_all_cards')
    return flask.render_template('cards.html', cards=cards)


API_TOKEN_LIFETIME = timedelta(hours=1)


@app.route('/api/login', methods=['POST'])
def api_login():
    # A token-based login for scripts/automation (a monitoring bot, a CI
    # job) instead of the normal cookie session. Credential check itself
    # is parameterized/safe - the vulnerability here is entirely in how
    # /api/balance later trusts a token, not in this route.
    data = flask.request.get_json(silent=True) or flask.request.form
    username = (data or {}).get('username', '')
    password = (data or {}).get('password', '')

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ? AND password = ?',
        (username, md5_hash(password)),
    ).fetchone()

    if not user:
        conn.close()
        return flask.jsonify(error='Invalid username or password.'), 401

    if user['username'] == BOT_USERNAME:
        # Real password match here means it was captured off the wire,
        # same as the cookie-based /login - this route is just another
        # way to use it, so it should mark the same challenge solved.
        mark_solved('cleartext_creds')

    now = datetime.utcnow()
    jti = str(uuid.uuid4())
    payload = {
        'username': user['username'],
        'jti': jti,
        'iat': now,
        'exp': now + API_TOKEN_LIFETIME,
    }
    token = jwt.encode(payload, app.secret_key, algorithm='HS256')

    conn.execute(
        'INSERT INTO issued_tokens (jti, username, issued_at) VALUES (?, ?, ?)',
        (jti, user['username'], now.isoformat()),
    )
    conn.commit()
    conn.close()

    return flask.jsonify(token=token)


@app.route('/api/balance')
def api_balance():
    auth = flask.request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return flask.jsonify(error='Missing bearer token.'), 401
    token = auth[len('Bearer '):]

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        return flask.jsonify(error='Malformed token.'), 401

    forged = False

    # --- INTENTIONALLY VULNERABLE ---
    # Trusts the algorithm the token itself claims instead of pinning to
    # one expected algorithm server-side. A token with alg "none" is
    # accepted with no signature check at all - /api/login never issues
    # one, so reaching this branch at all proves forgery.
    if header.get('alg', '').lower() == 'none':
        try:
            payload = jwt.decode(token, options={'verify_signature': False})
        except jwt.PyJWTError:
            return flask.jsonify(error='Malformed token.'), 401
        forged = True
    else:
        try:
            # --- INTENTIONALLY VULNERABLE ---
            # Signs with app.secret_key, the same hardcoded value used for
            # session cookies - and it's sitting in this project's public
            # GitHub source. Anyone who reads it can mint a fully,
            # correctly signed token for any username without ever
            # calling /api/login.
            payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        except jwt.PyJWTError:
            return flask.jsonify(error='Invalid or expired token.'), 401

        conn = get_db()
        issued = conn.execute(
            'SELECT username FROM issued_tokens WHERE jti = ?', (payload.get('jti'),)
        ).fetchone()
        conn.close()
        if not issued or issued['username'] != payload.get('username'):
            # Correctly signed, but not a token we ever actually issued -
            # only possible by knowing the signing secret independently.
            forged = True

    username = payload.get('username')
    conn = get_db()
    user = conn.execute('SELECT balance FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if not user:
        return flask.jsonify(error='Unknown user.'), 404

    if forged and username == BOT_USERNAME:
        mark_solved('api_token_forgery')

    return flask.jsonify(username=username, balance=user['balance'])


@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


# --- INTENTIONALLY VULNERABLE ---
# Hidden/hardcoded backdoor route: anyone who finds this URL is logged in
# as internAdmin with zero credentials, no auth check at all.
@app.route('/admin_panel1234510')
def admin_panel():
    mark_solved('hidden_backdoor')
    flask.session['username'] = 'internAdmin@fakebank.com'
    return flask.redirect(flask.url_for('dashboard'))

@app.route('/check-recipient')
def check_recipient():
    username = flask.request.args.get('username', '')

    # --- INTENTIONALLY VULNERABLE ---
    # Same raw-string-interpolation mistake as /login, on a completely
    # separate feature (a "does this payee exist" preview for the
    # transfer form). Unlike /login this one echoes the matched column
    # back directly, so a UNION SELECT here can read any column of any
    # row - including password hashes - without needing blind/boolean
    # extraction.
    query = "SELECT username FROM users WHERE username = '{}'".format(username)

    conn = get_db()
    try:
        row = conn.execute(query).fetchone()
    except sqlite3.Error:
        conn.close()
        return flask.jsonify(exists=False)
    conn.close()

    if row:
        return flask.jsonify(exists=True, match=row['username'])
    return flask.jsonify(exists=False)


@app.route('/transfer')
def transfer():

    username = flask.session.get('username')
    if not username:
        return flask.redirect(flask.url_for('index'))
    return flask.render_template('transfer.html')

@app.route('/transfer', methods=['POST'])
def transfer_post():
    username = flask.session.get('username')
    if not username:
        return flask.redirect(flask.url_for('index'))

    recipient = flask.request.form.get('recipient', '')
    amount_raw = flask.request.form.get('amount', '')
    gift_number = flask.request.form.get('gift_number', '')

    try:
        amount = float(amount_raw)
    except ValueError:
        return flask.render_template('transfer.html', error='Invalid amount.')

    if amount <= 0:
        return flask.render_template('transfer.html', error='Amount must be positive.')

    # A "valid" gift code short-circuits the whole transfer - no debit, no
    # credit, nothing actually moves. The gift card is a scam.
    using_gift_card = gift_number != '' and gift_number == daily_gift_code()

    conn = get_db()

    if using_gift_card:
        mark_solved('fake_gift_card')
        conn.close()
        return flask.redirect(flask.url_for('dashboard', transfer=1))

    sender = conn.execute(
        'SELECT balance FROM users WHERE username = ?', (username,)
    ).fetchone()
    if sender['balance'] < amount:
        conn.close()
        return flask.render_template('transfer.html', error='Insufficient balance.')
    conn.execute('UPDATE users SET balance = balance - ? WHERE username = ?', (amount, username))

    # Recipient doesn't need to exist - if the username isn't real, the
    # money just vanishes (0 rows updated) instead of being rejected.
    conn.execute('UPDATE users SET balance = balance + ? WHERE username = ?', (amount, recipient))
    conn.execute(
        'INSERT INTO transactions (sender, recipient, amount, timestamp, ip_address) '
        'VALUES (?, ?, ?, ?, ?)',
        (username, recipient, amount, datetime.now().isoformat(), flask.request.remote_addr),
    )
    conn.commit()
    conn.close()

    return flask.redirect(flask.url_for('dashboard', transfer=1))


# --- INTENTIONALLY UNLINKED ---
# Never referenced from any template - only reachable by URL, discoverable
# the same way as the admin backdoor (see robots.txt).
@app.route(SCOREBOARD_PATH, methods=['GET', 'POST'])
def scoreboard():
    # Once a session has found this page once, the login page grows a
    # (still hidden) shortcut back to it - no need to rediscover the URL
    # every visit.
    flask.session['found_scoreboard'] = True

    message = None
    if flask.request.method == 'POST':
        submitted = flask.request.form.get('flag', '').strip()
        if submitted == RCE_FLAG:
            mark_solved('rce_console')
            message = ('success', 'Flag accepted!')
        else:
            message = ('error', 'Incorrect flag.')

    conn = get_db()
    solved_rows = conn.execute(
        'SELECT challenge_id FROM solves WHERE visitor_id = ?', (get_visitor_id(),)
    ).fetchall()
    conn.close()
    solved_ids = {row['challenge_id'] for row in solved_rows}

    board = []
    for c in CHALLENGES:
        board.append({
            'id': c['id'],
            'title': c['title'],
            'difficulty': c['difficulty'],
            'hint': c['hint'],
            'solved': c['id'] in solved_ids,
        })
    solved_count = sum(1 for c in board if c['solved'])

    return flask.render_template(
        'scoreboard.html', board=board, solved_count=solved_count,
        total=len(board), message=message,
    )


if __name__ == '__main__':
    init_db()
    write_rce_flag()
    # WERKZEUG_RUN_MAIN is only set in the actual serving process, not the
    # reloader's watcher process - without this check debug mode would
    # start two bots.
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_credential_bot()
    app.run(debug=True, host='0.0.0.0', port=5005, threaded=True)
