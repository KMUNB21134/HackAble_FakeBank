import flask
import hashlib
import os
import sqlite3
from datetime import datetime

app = flask.Flask(__name__)
app.secret_key = 'not-a-real-secret'  # fine for a local vuln demo, not for prod

DB_PATH = os.path.join(os.path.dirname(__file__), 'fakebank.db')


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
    # Seed a couple of accounts so injection has something to find/bypass.
    existing = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if existing == 0:
        conn.executemany(
            'INSERT INTO users (username, password, balance) VALUES (?, ?, ?)',
            [
                ('admin', md5_hash('password123'), 1337133.70),
                ('alice', md5_hash('letmein'), 4200.00),
                ('bob', md5_hash('hunter2'), 950.25),
            ],
        )
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return flask.render_template('index.html')


@app.route('/robots.txt')
def robots():
    return flask.send_from_directory(app.static_folder, 'robots.txt')


@app.route('/login', methods=['POST'])
def login():
    username = flask.request.form.get('username', '')
    password = flask.request.form.get('password', '')

    # --- INTENTIONALLY VULNERABLE ---
    # Raw string interpolation into SQL instead of parameterized query.
    # e.g. username = admin' -- to bypass password, or ' OR '1'='1 to
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
    conn.close()

    return flask.render_template('dashboard.html', user=user)


@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


# --- INTENTIONALLY VULNERABLE ---
# Hidden/hardcoded backdoor route: anyone who finds this URL is logged in
# as admin with zero credentials, no auth check at all.
@app.route('/admin_panel101')
def admin_panel():
    flask.session['username'] = 'admin'
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
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        return flask.render_template('dashboard.html', user=user, transfer=True)

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
    conn.commit()

    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    return flask.render_template('dashboard.html', user=user, transfer=True)

    

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')
