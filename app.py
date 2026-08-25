import flask
import hashlib
import os
import re
import secrets
import sqlite3
from datetime import datetime

app = flask.Flask(__name__)
app.secret_key = 'not-a-real-secret'  # fine for a local vuln demo, not for prod

DB_PATH = os.path.join(os.path.dirname(__file__), 'fakebank.db')

# Deliberately unlinked - only discoverable via the robots.txt leak, same as
# the admin backdoor.
SCOREBOARD_PATH = '/scoreboard93217'

# Only obtainable by actually executing code via the debugger console (see
# write_rce_flag() below) - this is the one challenge app.py cannot detect
# server-side, since werkzeug's debugger intercepts __debugger__ requests
# before Flask ever routes them.
RCE_FLAG = 'FLAG{d3bug_c0nsole_is_a_full_shell}'
RCE_FLAG_PATH = os.path.join(os.path.dirname(__file__), '.rce_flag')

CHALLENGES = [
    {
        'id': 'management_permission',
        'title': 'Get It in Writing',
        'difficulty': 1,
        'hint': 'Real pentests start with permission, not payloads. Ask nicely first.',
    },
    {
        'id': 'robots_leak',
        'title': 'Curious Crawler',
        'difficulty': 1,
        'hint': 'Servers publish files by default that most people never bother to check.',
    },
    {
        'id': 'sqli_login_bypass',
        'title': 'Login Without a Password',
        'difficulty': 2,
        'hint': 'The login form trusts what you type more than it should.',
    },
    {
        'id': 'weak_hashing',
        'title': 'Crack the Vault',
        'difficulty': 2,
        'hint': 'Not every hash needs the front door. Some can be reversed offline.',
    },
    {
        'id': 'stored_xss',
        'title': 'Make Yourself at Home',
        'difficulty': 2,
        'hint': 'Something you type during registration comes back to greet you later.',
    },
    {
        'id': 'fake_gift_card',
        'title': 'Too Good to Be True',
        'difficulty': 3,
        'hint': "A \"secret\" code that's the same for everyone all day isn't much of a secret.",
    },
    {
        'id': 'hidden_backdoor',
        'title': 'Skeleton Key',
        'difficulty': 3,
        'hint': 'Not every route needs a login form to be reachable.',
    },
    {
        'id': 'rce_console',
        'title': 'Whole Server, One Shell',
        'difficulty': 5,
        'hint': 'A crash can be a door, if whatever is behind it lets you run code.',
        'flag': RCE_FLAG,
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS solves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT NOT NULL,
            challenge_id TEXT NOT NULL,
            solved_at TEXT NOT NULL,
            UNIQUE(visitor_id, challenge_id)
        )
    ''')
    # Seed a couple of accounts so injection has something to find/bypass.
    existing = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if existing == 0:
        conn.executemany(
            'INSERT INTO users (username, password, balance) VALUES (?, ?, ?)',
            [
                ('admin@fakebank.com', md5_hash('password123'), 1337133.70),
                ('robot@fakebank.com', md5_hash('beepboop123'), 4200.00),
                # Weak, wordlist-top password on purpose - cracking this
                # offline (John/hashcat) and logging in with it is the
                # "weak_hashing" challenge.
                ('crackme@fakebank.com', md5_hash('letmein'), 13.37),
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
    return flask.render_template('index.html')


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    history = flask.session.get('chat_history', [])

    if flask.request.method == 'POST':
        message = flask.request.form.get('message', '').strip()
        if message:
            history = history + [
                {'from': 'you', 'text': message},
                {'from': 'management', 'text': 'You are allowed to.'},
            ]
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
    # e.g. username = admin@fakebank.com' -- to bypass password, or ' OR '1'='1 to
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

    if re.search(r'[<>]|onerror\s*=|<script', user['username'], re.IGNORECASE):
        mark_solved('stored_xss')

    rows = conn.execute(
        'SELECT timestamp, amount FROM transactions WHERE sender = ? ORDER BY id DESC LIMIT 7',
        (username,),
    ).fetchall()
    conn.close()

    # Oldest -> newest for a left-to-right chart, each bar scaled against
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


@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


# --- INTENTIONALLY VULNERABLE ---
# Hidden/hardcoded backdoor route: anyone who finds this URL is logged in
# as admin with zero credentials, no auth check at all.
@app.route('/admin_panel1234510')
def admin_panel():
    mark_solved('hidden_backdoor')
    flask.session['username'] = 'admin@fakebank.com'
    return flask.redirect(flask.url_for('dashboard'))

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
        'INSERT INTO transactions (sender, recipient, amount, timestamp) VALUES (?, ?, ?, ?)',
        (username, recipient, amount, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    return flask.redirect(flask.url_for('dashboard', transfer=1))


# --- INTENTIONALLY UNLINKED ---
# Never referenced from any template - only reachable by URL, discoverable
# the same way as the admin backdoor (see robots.txt).
@app.route(SCOREBOARD_PATH, methods=['GET', 'POST'])
def scoreboard():
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
    app.run(debug=True, host='0.0.0.0', port=5005)
