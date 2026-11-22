"""Учётные записи пользователей Smart Campus TURAN: регистрация, вход, сессии, профиль.

Пароли хранятся только в виде хеша PBKDF2-HMAC-SHA256 с индивидуальной солью.
Сессия — случайный токен в cookie с флагом HttpOnly.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from storage import connect

ROLES = {
    'teacher': 'Преподаватель',
    'student': 'Студент',
    'employee': 'Работник университета',
    'other': 'Другое',
}
# Какое дополнительное поле спрашиваем у каждой роли
ROLE_DETAIL = {
    'teacher': 'Кафедра или дисциплина',
    'student': 'Учебная группа',
    'employee': 'Подразделение и должность',
    'other': 'Кем вы являетесь',
}
# Роли, которым разрешено изменять данные (добавлять студентов, назначать консультации)
EDITOR_ROLES = {'teacher', 'employee'}

SESSION_DAYS = 7
PBKDF2_ITERATIONS = 120_000
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class AuthError(ValueError):
    """Ошибка проверки данных, текст показывается пользователю."""


def init_auth(db_path: str | Path) -> None:
    with connect(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                about TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        """)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split('$')
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                     bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _text(body: dict, key: str) -> str:
    value = body.get(key, '')
    if not isinstance(value, str):
        raise AuthError('Неверный формат данных')
    return value.strip()


def _check_name(name: str) -> str:
    if not 2 <= len(name) <= 80:
        raise AuthError('Укажите ФИО (от 2 до 80 символов)')
    return name


def _check_detail(role: str, detail: str) -> str:
    if role in ('student', 'other') and len(detail) < 2:
        raise AuthError(f'Заполните поле «{ROLE_DETAIL[role]}»')
    if len(detail) > 100:
        raise AuthError(f'Поле «{ROLE_DETAIL[role]}» — не более 100 символов')
    return detail


def _check_password(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise AuthError('Пароль должен содержать от 8 до 128 символов')
    if not re.search(r'[A-Za-zА-Яа-яЁё]', password) or not re.search(r'\d', password):
        raise AuthError('Пароль должен содержать хотя бы одну букву и одну цифру')
    return password


def public_user(row) -> dict:
    return {
        'id': row['id'], 'full_name': row['full_name'], 'email': row['email'],
        'role': row['role'], 'role_label': ROLES.get(row['role'], row['role']),
        'detail': row['detail'], 'detail_label': ROLE_DETAIL.get(row['role'], ''),
        'about': row['about'], 'created_at': row['created_at'],
        'can_edit': row['role'] in EDITOR_ROLES,
    }


def register(db_path: str | Path, body: dict) -> dict:
    name = _check_name(_text(body, 'full_name'))
    email = _text(body, 'email').lower()
    if not EMAIL_RE.match(email) or len(email) > 120:
        raise AuthError('Введите корректный email, например name@turan-edu.kz')
    role = _text(body, 'role')
    if role not in ROLES:
        raise AuthError('Выберите, кем вы являетесь')
    detail = _check_detail(role, _text(body, 'detail'))
    password = body.get('password', '')
    if not isinstance(password, str):
        raise AuthError('Неверный формат пароля')
    _check_password(password)
    now = datetime.now().isoformat(timespec='seconds')
    with connect(db_path) as db:
        if db.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
            raise AuthError('Пользователь с таким email уже зарегистрирован. Войдите в систему.')
        cur = db.execute(
            'INSERT INTO users(full_name, email, role, detail, about, password_hash, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, email, role, detail, '', hash_password(password), now))
        row = db.execute('SELECT * FROM users WHERE id = ?', (cur.lastrowid,)).fetchone()
        return public_user(row)


def login(db_path: str | Path, body: dict) -> dict:
    email = _text(body, 'email').lower()
    password = body.get('password', '')
    if not email or not isinstance(password, str) or not password:
        raise AuthError('Введите email и пароль')
    with connect(db_path) as db:
        row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row is None or not verify_password(password, row['password_hash']):
            raise AuthError('Неверный email или пароль')
        return public_user(row)


def create_session(db_path: str | Path, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec='seconds')
    with connect(db_path) as db:
        db.execute('DELETE FROM sessions WHERE expires_at < ?', (datetime.now().isoformat(timespec='seconds'),))
        db.execute('INSERT INTO sessions(token, user_id, expires_at) VALUES (?, ?, ?)', (token, user_id, expires))
    return token


def user_by_token(db_path: str | Path, token: str | None) -> dict | None:
    if not token or len(token) > 100:
        return None
    with connect(db_path) as db:
        row = db.execute(
            'SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id '
            'WHERE s.token = ? AND s.expires_at > ?',
            (token, datetime.now().isoformat(timespec='seconds'))).fetchone()
        return public_user(row) if row else None


def logout(db_path: str | Path, token: str | None) -> None:
    if token:
        with connect(db_path) as db:
            db.execute('DELETE FROM sessions WHERE token = ?', (token,))


def update_profile(db_path: str | Path, user_id: int, body: dict) -> dict:
    with connect(db_path) as db:
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            raise AuthError('Пользователь не найден')
        name = _check_name(_text(body, 'full_name'))
        detail = _check_detail(row['role'], _text(body, 'detail'))
        about = _text(body, 'about')
        if len(about) > 500:
            raise AuthError('Поле «О себе» — не более 500 символов')
        db.execute('UPDATE users SET full_name = ?, detail = ?, about = ? WHERE id = ?',
                   (name, detail, about, user_id))
        return public_user(db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone())


def change_password(db_path: str | Path, user_id: int, body: dict) -> None:
    old = body.get('old_password', '')
    new = body.get('new_password', '')
    if not isinstance(old, str) or not isinstance(new, str):
        raise AuthError('Неверный формат пароля')
    _check_password(new)
    with connect(db_path) as db:
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None or not verify_password(old, row['password_hash']):
            raise AuthError('Текущий пароль введён неверно')
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hash_password(new), user_id))
