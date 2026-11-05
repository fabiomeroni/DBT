"""
The author's password, the key that signs login cookies, and login throttling.

Nothing secret is ever written in the code or in the repository. It lives in the folder `instance/`
(ignored by git, never served by the site):

    instance/author.json   {"passwordHash": "...", "secretKey": "..."}

The password is stored only as a hash. It can be given to the server in three ways, in this order of precedence:

    1. instance/author.json      set with   python app.py --set-password
                                 or from the dictionary's Settings (Author password)
    2. the environment variable  AUTHOR_PASSWORD   (kept outside the project, e.g. in the server's service file)

If neither exists, nobody can log in as the author until one is set.
"""
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time

from werkzeug.security import check_password_hash, generate_password_hash

INSTANCE_DIR = 'instance'
_FILE = os.path.join(INSTANCE_DIR, 'author.json')
MIN_LENGTH = 8
# Passwords that were once published (or are plainly guessable) are never accepted, wherever they come from.
# Only their SHA-256 fingerprints are kept here, so that the list does not itself publish them again.
_REFUSED_FINGERPRINTS = {
    '057ba03d6c44104863dc7361fe4578965d1887360f90a0895882e58a6248fc86',
    '0b14d501a594442a01c6859541bcb3e8164d183d32937b851835442f69d5c94e',
    '15e2b0d3c33891ebb0f1ef609ec419420c20e320ce94c65fbc8c3312448eb225',
    '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    '62ce9291160a44286462f05e7a22a96131d4b3585b8cc8694d99d632bee9494a',
    'a17444550e2c127b02ea1c197bcffa422c21713040f53d5c2ca7925419bccf7f',
    'ef797c8118f02dfb649607dd5d3f8c7623048c9c063d532cc95c5ed7a898a64f',
    'f6cfe289bbfa10e1fa917b9d1a8ef547f3373e0b8e23b16446500d7c157bb0ed',
}


def _is_refused(pw):
    return hashlib.sha256(str(pw).lower().encode('utf-8')).hexdigest() in _REFUSED_FINGERPRINTS


def _read():
    try:
        with open(_FILE, encoding='utf-8') as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _write(data):
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    try:
        os.chmod(INSTANCE_DIR, 0o700)
    except OSError:
        pass
    tmp = _FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, _FILE)


def secret_key():
    """The key that signs login cookies: SECRET_KEY if the environment gives one, otherwise a random key
    generated on first start and kept in instance/author.json."""
    env = os.environ.get('SECRET_KEY')
    if env:
        return env
    data = _read()
    if not data.get('secretKey'):
        data['secretKey'] = secrets.token_hex(32)
        _write(data)
    return data['secretKey']


def _env_password():
    pw = os.environ.get('AUTHOR_PASSWORD') or ''
    return '' if _is_refused(pw) else pw


def password_source():
    """'file', 'environment' or None."""
    if _read().get('passwordHash'):
        return 'file'
    return 'environment' if _env_password() else None


def password_configured():
    return password_source() is not None


def check_password(candidate):
    candidate = str(candidate or '')
    h = _read().get('passwordHash')
    if h:
        return check_password_hash(h, candidate)
    env = _env_password()
    return bool(env) and hmac.compare_digest(env.encode('utf-8'), candidate.encode('utf-8'))


def validate_new_password(pw):
    """None if acceptable, otherwise the reason in a sentence."""
    pw = str(pw or '')
    if len(pw) < MIN_LENGTH:
        return f'The password needs at least {MIN_LENGTH} characters.'
    if _is_refused(pw):
        return 'That password is too common (or was published). Choose another.'
    return None


def set_password(pw):
    data = _read()
    data['passwordHash'] = generate_password_hash(pw)
    _write(data)


class LoginLimiter:
    """After max_fail wrong passwords from one address within `window` seconds, that address is refused for `lock` seconds."""

    def __init__(self, max_fail=5, window=600, lock=600):
        self.max_fail, self.window, self.lock = max_fail, window, lock
        self._fails, self._locked, self._mutex = {}, {}, threading.Lock()

    def blocked_for(self, key):
        with self._mutex:
            until = self._locked.get(key, 0)
            return max(0, int(until - time.time())) if until > time.time() else 0

    def fail(self, key):
        now = time.time()
        with self._mutex:
            recent = [t for t in self._fails.get(key, []) if now - t < self.window] + [now]
            self._fails[key] = recent
            if len(recent) >= self.max_fail:
                self._locked[key] = now + self.lock
                self._fails[key] = []

    def reset(self, key):
        with self._mutex:
            self._fails.pop(key, None)
            self._locked.pop(key, None)


def cli_set_password():
    """python app.py --set-password : ask (hidden) for the new password twice and store its hash. When the input
    is not a terminal (a script), the two passwords are read from standard input, one per line."""
    if sys.stdin.isatty():
        first = getpass.getpass('New author password: ')
        again = getpass.getpass('Repeat it: ')
    else:
        lines = sys.stdin.read().splitlines()
        first = lines[0] if lines else ''
        again = lines[1] if len(lines) > 1 else first
    if first != again:
        print('The two passwords differ. Nothing was changed.')
        sys.exit(1)
    problem = validate_new_password(first)
    if problem:
        print(problem + ' Nothing was changed.')
        sys.exit(1)
    set_password(first)
    print(f'Author password saved, as a hash, in {_FILE}. It is not stored anywhere else.')
