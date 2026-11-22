"""Запуск: python server.py. HTTP-сервер на стандартной библиотеке Python.
Не требует Flask, доступен локально на http://127.0.0.1:8000.
"""
from __future__ import annotations
import json
import mimetypes
import os
import re
from pathlib import Path
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from statistics import mean
from functools import lru_cache
from typing import Any
from http.cookies import SimpleCookie

import auth

from ml_engine import ModelEngine, observations, recommendation
from dataset_adapter import DatasetFormatError, dataset_summary
from storage import (
    init_db,
    students as load_students,
    create_student,
    schedule as add_consultation,
    consultations as get_consultations,
)

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('CAMPUS_DB_PATH', str(ROOT / 'data' / 'campus.db')))
XAPI_PATH = Path(os.environ.get('CAMPUS_XAPI_PATH', str(ROOT / 'data' / 'xAPI-Edu-Data.csv')))
MODEL: ModelEngine | None = None


class SmartCampusHTTPServer(ThreadingHTTPServer):
    """Локальный сервер с очередью, достаточной для учебного нагрузочного теста."""
    request_queue_size = 64
    daemon_threads = False
    block_on_close = True


def bootstrap() -> None:
    global MODEL
    init_db(DB_PATH, XAPI_PATH)
    auth.init_auth(DB_PATH)
    if MODEL is None:
        try:
            MODEL = ModelEngine.train(str(XAPI_PATH) if XAPI_PATH.is_file() else None)
        except DatasetFormatError as exc:
            print('xAPI dataset rejected:', exc)
            MODEL = ModelEngine.train()
    _enriched_cached.cache_clear()
    # Прогрев вычислений до начала приёма запросов исключает конкурентный
    # холодный старт нескольких RandomForest/IsolationForest-предсказаний.
    _enriched_cached(str(DB_PATH))


@lru_cache(maxsize=8)
def _enriched_cached(db_path: str) -> list[dict[str, Any]]:
    """Демо-карточки не изменяются через API: кешируем тяжёлый вызов ML."""
    assert MODEL is not None
    rows = load_students(db_path)
    predictions = MODEL.predict_many(rows)
    return [{**student, **prediction} for student, prediction in zip(rows, predictions)]


def enriched() -> list[dict[str, Any]]:
    return _enriched_cached(str(DB_PATH))


def make_dashboard(rows: list[dict]) -> dict:
    by_risk = {kind: sum(s['risk'] == kind for s in rows) for kind in ('high', 'medium', 'normal')}
    rank = {'high': 0, 'medium': 1, 'normal': 2}
    needs = sorted((s for s in rows if s['risk'] != 'normal'), key=lambda s: (rank[s['risk']], s['engagement']))[:4]
    return {
        'count': len(rows), 'avg_attendance': round(mean(s['attendance'] for s in rows)),
        'avg_engagement': round(mean(s['engagement'] for s in rows)),
        'at_risk': by_risk['high'] + by_risk['medium'],
        'high_risk': by_risk['high'], 'by_risk': by_risk,
        'active_courses': len({s['student_group'] for s in rows}),
        'overdue_total': sum(s['overdue'] for s in rows),
        'on_time_total': sum(s['on_time_tasks'] for s in rows),
        'anomalies': sum(s['is_anomaly'] for s in rows),
        'attention': needs,
    }


def make_analytics(rows: list[dict]) -> dict:
    at_risk = [s for s in rows if s['risk'] != 'normal']
    conditions = (
        ('Низкая вовлечённость', lambda s: s['engagement'] < 70),
        ('Пропуски занятий', lambda s: s['attendance'] < 75),
        ('Просроченные задания', lambda s: s['overdue'] >= 2),
        ('Снижение LMS-активности', lambda s: s['lms_change'] <= -15),
    )
    counts = [(label, sum(fn(s) for s in at_risk)) for label, fn in conditions]
    denominator = sum(count for _, count in counts) or 1
    factors = [{'label': label, 'count': count, 'percent': round(100 * count / denominator)}
               for label, count in counts]
    rank = {'high': 0, 'medium': 1, 'normal': 2}
    alerts = sorted((s for s in at_risk), key=lambda s: (rank[s['risk']], s['engagement']))[:8]
    return {
        'distribution': make_dashboard(rows)['by_risk'],
        'factors': factors,
        'alerts': [dict(s, message=recommendation(s, s['risk'])) for s in alerts],
        'model': MODEL.quality if MODEL else {},
    }


def payload_for_student(student_id: int, rows: list[dict]) -> dict:
    student = next((s for s in rows if s['id'] == student_id), None)
    if student is None:
        raise LookupError('Студент не найден')
    group_avg = mean(s['engagement'] for s in rows)
    return {**student,
            'factors': observations(student, group_avg),
            'recommendation': recommendation(student, student['risk']),
            'group_engagement': round(group_avg),
            'consultations': get_consultations(DB_PATH, student_id)}


def api_response(path: str, query: dict, method: str, body: dict | None = None) -> tuple[int, Any]:
    if MODEL is None:
        bootstrap()
    rows = enriched()
    if method == 'GET' and path == '/api/health':
        return 200, {'status': 'ok', 'students': len(rows), 'db': 'SQLite', 'model': '2 метода ML'}
    if method == 'GET' and path == '/api/dashboard':
        return 200, make_dashboard(rows)
    if method == 'GET' and path == '/api/analytics':
        return 200, make_analytics(rows)
    if method == 'GET' and path == '/api/model':
        return 200, MODEL.quality
    if method == 'GET' and path == '/api/dataset':
        try:
            return 200, dataset_summary(XAPI_PATH)
        except DatasetFormatError as exc:
            return 422, {'error': str(exc), 'dataset': 'xAPI-Edu-Data'}
    if method == 'GET' and path == '/api/students':
        search = str(query.get('search', [''])[0]).casefold().strip()[:120]
        filt = str(query.get('risk', ['all'])[0])
        if filt not in ('all', 'at-risk', 'normal', 'high', 'medium'):
            return 400, {'error': 'Недопустимый фильтр'}
        matched = [s for s in rows if (not search or search in s['name'].casefold()
                   or search in s['student_group'].casefold()
                   or search in s.get('dataset_id', '').casefold())
                   and (filt == 'all' or (filt == 'at-risk' and s['risk'] != 'normal') or s['risk'] == filt)]
        return 200, {'items': matched, 'total': len(rows), 'shown': len(matched)}
    if method == 'POST' and path == '/api/students':
        if not isinstance(body, dict):
            return 400, {'error': 'Неверный формат JSON'}
        name = body.get('name', '')
        group = body.get('student_group', '')
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            return 400, {'error': 'ФИО должно содержать от 2 до 80 символов'}
        if not isinstance(group, str) or not 2 <= len(group.strip()) <= 50:
            return 400, {'error': 'Группа должна содержать от 2 до 50 символов'}

        labels = {'attendance': 'Посещаемость', 'engagement': 'Вовлечённость',
                  'grade': 'Средний балл', 'overdue': 'Просрочено заданий'}

        def number(field: str, minimum: float, maximum: float) -> float:
            label = labels.get(field, field)
            raw = body.get(field)
            if isinstance(raw, str):
                raw = raw.replace(',', '.').strip()
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Поле «{label}» должно быть числом') from exc
            if not minimum <= value <= maximum:
                raise ValueError(f'Поле «{label}» должно быть от {minimum:g} до {maximum:g}')
            return value

        try:
            attendance = number('attendance', 0, 100)
            engagement = number('engagement', 0, 100)
            grade = number('grade', 0, 4)
            overdue_value = number('overdue', 0, 50)
            if not overdue_value.is_integer():
                raise ValueError('Поле «Просрочено заданий» должно быть целым числом')
        except ValueError as exc:
            return 400, {'error': str(exc)}
        overdue = int(overdue_value)
        values = {
            'name': name.strip(),
            'student_group': group.strip(),
            'attendance': round(attendance, 1),
            'engagement': round(engagement, 1),
            'grade': round(grade, 2),
            'overdue': overdue,
            'lms_change': round(max(-50, min(50, engagement - 70)), 1),
            'on_time_tasks': max(0, 12 - overdue),
            'raisedhands': round(min(100, engagement * 0.82), 1),
            'visited_resources': round(min(100, engagement * 1.05), 1),
            'announcements_view': round(min(100, engagement * 0.68), 1),
            'discussion': round(min(100, engagement * 0.60), 1),
            'absence_score': 100.0 if attendance < 75 else 0.0,
        }
        ident = create_student(DB_PATH, values)
        _enriched_cached.cache_clear()
        created = next(s for s in enriched() if s['id'] == ident)
        return 201, {'id': ident, 'dataset_id': created['dataset_id'],
                     'message': 'Студент добавлен в SQLite', 'student': created}
    m = re.fullmatch(r'/api/students/(\d+)', path)
    if method == 'GET' and m:
        try:
            return 200, payload_for_student(int(m[1]), rows)
        except LookupError as e:
            return 404, {'error': str(e)}
    if method == 'GET' and path == '/api/consultations':
        return 200, {'items': get_consultations(DB_PATH)}
    if method == 'POST' and path == '/api/consultations':
        if not isinstance(body, dict):
            return 400, {'error': 'Неверный формат JSON'}
        try:
            student_id = int(body.get('student_id', 0))
        except (ValueError, TypeError):
            return 400, {'error': 'Некорректный ID студента'}
        raw_date = body.get('appointment_at', '')
        note = body.get('note', '')
        if not isinstance(raw_date, str) or len(raw_date) > 35 or not isinstance(note, str):
            return 400, {'error': 'Неверный формат полей'}
        note = note.strip()
        if len(note) < 5 or len(note) > 400:
            return 400, {'error': 'Причина консультации: от 5 до 400 символов'}
        try:
            dt = datetime.fromisoformat(raw_date)
        except ValueError:
            return 400, {'error': 'Введите корректную дату и время'}
        if dt <= datetime.now(dt.tzinfo):
            return 400, {'error': 'Дата консультации должна быть в будущем'}
        try:
            ident = add_consultation(DB_PATH, student_id, dt.isoformat(timespec='minutes'), note)
            return 201, {'id': ident, 'message': 'Консультация сохранена локально'}
        except LookupError as e:
            return 404, {'error': str(e)}
    return 404, {'error': 'Адрес API не найден'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'SmartCampusTURAN/1.0'

    def _json(self, status: int, data: Any, cookie: str | None = None):
        content = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            # Клиент мог закрыть вкладку или отменить запрос до отправки ответа.
            return

    def _static(self, path: str):
        if path == '/':
            target = ROOT / 'static' / 'index.html'
        elif path in ('/static/app.js', '/static/style.css'):
            target = ROOT / path.lstrip('/')
        else:
            return self.send_error(404)
        if not target.is_file():
            return self.send_error(404)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(target))[0] or 'text/plain')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path.startswith('/api/'):
            user = self._user()
            if url.path == '/api/auth/me':
                return self._json(200, {'user': user}) if user else self._json(401, {'error': 'Требуется вход в систему', 'auth': True})
            if url.path == '/api/auth/roles':
                return self._json(200, {'roles': auth.ROLES, 'details': auth.ROLE_DETAIL})
            if url.path != '/api/health' and user is None:
                return self._json(401, {'error': 'Требуется вход в систему', 'auth': True})
            try:
                status, data = api_response(url.path, parse_qs(url.query), 'GET')
            except Exception as exc:
                print('API error:', repr(exc))
                status, data = 500, {'error': 'Ошибка обработки запроса'}
            return self._json(status, data)
        return self._static(url.path)

    # ---------- сессии ----------
    COOKIE = 'sc_session'

    def _token(self) -> str | None:
        raw = self.headers.get('Cookie')
        if not raw:
            return None
        try:
            jar = SimpleCookie(raw)
        except Exception:
            return None
        morsel = jar.get(self.COOKIE)
        return morsel.value if morsel else None

    def _user(self) -> dict | None:
        if MODEL is None:
            bootstrap()
        return auth.user_by_token(DB_PATH, self._token())

    def _session_cookie(self, token: str, max_age: int) -> str:
        secure = '; Secure' if self.headers.get('X-Forwarded-Proto', '') == 'https' else ''
        return f'{self.COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}'

    def do_POST(self):
        url = urlsplit(self.path)
        routes = ('/api/consultations', '/api/students', '/api/auth/register', '/api/auth/login',
                  '/api/auth/logout', '/api/profile', '/api/profile/password')
        if url.path not in routes:
            return self._json(404, {'error': 'Неизвестный адрес'})
        cookie = None
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > 12000 or (size == 0 and url.path != '/api/auth/logout'):
                return self._json(413, {'error': 'Неверный размер запроса'})
            payload = json.loads(self.rfile.read(size)) if size else {}
            if url.path == '/api/auth/logout':
                auth.logout(DB_PATH, self._token())
                status, data, cookie = 200, {'message': 'Вы вышли из системы'}, self._session_cookie('', 0)
            elif url.path in ('/api/auth/register', '/api/auth/login'):
                if MODEL is None:
                    bootstrap()
                if not isinstance(payload, dict):
                    raise auth.AuthError('Неверный формат данных')
                fn = auth.register if url.path.endswith('register') else auth.login
                user = fn(DB_PATH, payload)
                token = auth.create_session(DB_PATH, user['id'])
                status = 201 if url.path.endswith('register') else 200
                data = {'user': user, 'message': 'Добро пожаловать!'}
                cookie = self._session_cookie(token, auth.SESSION_DAYS * 86400)
            else:
                user = self._user()
                if user is None:
                    return self._json(401, {'error': 'Требуется вход в систему', 'auth': True})
                if not isinstance(payload, dict):
                    raise auth.AuthError('Неверный формат данных')
                if url.path == '/api/profile':
                    status, data = 200, {'user': auth.update_profile(DB_PATH, user['id'], payload),
                                         'message': 'Профиль сохранён'}
                elif url.path == '/api/profile/password':
                    auth.change_password(DB_PATH, user['id'], payload)
                    status, data = 200, {'message': 'Пароль изменён'}
                elif not user['can_edit']:
                    status, data = 403, {'error': 'Это действие доступно только преподавателям и работникам университета'}
                else:
                    status, data = api_response(url.path, {}, 'POST', payload)
        except auth.AuthError as exc:
            status, data = 400, {'error': str(exc)}
        except (json.JSONDecodeError, ValueError):
            status, data = 400, {'error': 'Некорректный JSON'}
        except Exception as exc:
            print('POST error:', repr(exc))
            status, data = 500, {'error': 'Ошибка сохранения'}
        self._json(status, data, cookie)


def main():
    bootstrap()
    address = os.environ.get('CAMPUS_HOST', '127.0.0.1')
    port = int(os.environ.get('CAMPUS_PORT', '8000'))
    httpd = SmartCampusHTTPServer((address, port), Handler)
    print(f'\nSMART CAMPUS TURAN\nОткройте: http://{address}:{port}\nДля остановки: Ctrl+C\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nСервер остановлен.')
    finally:
        httpd.server_close()

if __name__ == '__main__':
    main()
