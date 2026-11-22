"""Локальная SQLite-база демонстрационных студентов и консультаций."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from dataset_adapter import DatasetFormatError, load_xapi_rows

GROUP = "ИС-242(4)-2"


SEED_STUDENTS = [
    ("Диас К.", 62, 48, 2.8, 3, -28, 3),
    ("Нурай С.", 78, 66, 3.2, 1, -28, 8),
    ("Дильназ С.", 81, 61, 3.0, 3, -15, 7),
    ("Амир Ж.", 94, 88, 3.8, 0, 10, 11),
    ("Диас Т.", 89, 82, 3.6, 0, 8, 12),
    ("Артур П.", 91, 79, 3.5, 0, 4, 10),
    ("Алихан Н.", 57, 43, 2.4, 5, -30, 3),
    ("Сания А.", 65, 45, 2.7, 4, -22, 4),
    ("Тимур М.", 54, 40, 2.5, 5, -39, 2),
    ("Айдана Б.", 60, 47, 2.6, 4, -32, 4),
    ("Ерасыл Д.", 68, 49, 2.9, 4, -26, 4),
    ("Жанель Р.", 80, 62, 3.1, 2, -11, 8),
    ("Айсулу А.", 82, 65, 3.0, 1, -16, 7),
    ("Мади С.", 76, 67, 3.1, 2, -10, 8),
    ("Ренат Г.", 81, 64, 3.2, 2, -18, 9),
    ("Алия К.", 92, 91, 3.8, 0, 9, 11),
    ("Ержан Ж.", 90, 86, 3.6, 0, 4, 10),
    ("Меруерт С.", 95, 94, 3.9, 0, 13, 12),
    ("Даулет А.", 88, 80, 3.5, 0, 0, 11),
    ("Азамат М.", 93, 85, 3.6, 0, 7, 10),
    ("Дана О.", 96, 93, 4.0, 0, 9, 12),
    ("Нурсултан Р.", 89, 85, 3.7, 0, 5, 11),
    ("Камилла П.", 98, 94, 3.9, 0, 12, 12),
    ("Еркебулан С.", 87, 81, 3.5, 0, 2, 11),
    ("Индира М.", 92, 87, 3.8, 0, 6, 12),
    ("Бекзат Д.", 91, 83, 3.5, 0, 3, 11),
    ("София Т.", 95, 90, 3.9, 0, 11, 12),
    ("Ермек А.", 90, 88, 3.7, 0, 7, 11),
]


@contextmanager
def connect(db_path: str | Path):

    conn = sqlite3.connect(str(db_path), timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _xapi_student(row: dict, index: int) -> tuple:
    engagement = round(
        0.25 * row["raisedhands"]
        + 0.35 * row["visited_resources"]
        + 0.20 * row["announcements_view"]
        + 0.20 * row["discussion"],
        1,
    )
    attendance = (94 - index % 6) if row["absence_score"] == 0 else (68 - index % 9)
    grade = {"normal": 3.7, "medium": 3.0, "high": 2.2}[row["risk"]]
    overdue = max(0, min(6, round((100 - row["visited_resources"]) / 25)
                              + (1 if row["absence_score"] else 0) - 1))
    lms_change = max(-45, min(35, round(
        (row["visited_resources"] + row["announcements_view"]) / 2 - 50
    )))
    on_time = max(0, min(12, round(
        (row["visited_resources"] + row["raisedhands"]) / 18
    )))
    dataset_id = row.get("student_id") or f"XAPI-{index + 1:03d}"
    name = row.get("student_name") or f"Студент {dataset_id}"
    group = row.get("student_group") or "XAPI-UNASSIGNED"
    return (
        name, group, attendance, engagement, grade, overdue, lms_change, on_time,
        row["raisedhands"], row["visited_resources"], row["announcements_view"],
        row["discussion"], row["absence_score"], dataset_id, row.get("class_label", ""),
        row.get("name_source") or "synthetic_demo",
    )


def init_db(db_path: str | Path, dataset_path: str | Path | None = None) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                student_group TEXT NOT NULL,
                attendance REAL NOT NULL CHECK(attendance BETWEEN 0 AND 100),
                engagement REAL NOT NULL CHECK(engagement BETWEEN 0 AND 100),
                grade REAL NOT NULL CHECK(grade BETWEEN 0 AND 4),
                overdue INTEGER NOT NULL CHECK(overdue >= 0),
                lms_change REAL NOT NULL,
                on_time_tasks INTEGER NOT NULL DEFAULT 0,
                raisedhands REAL NOT NULL DEFAULT 0,
                visited_resources REAL NOT NULL DEFAULT 0,
                announcements_view REAL NOT NULL DEFAULT 0,
                discussion REAL NOT NULL DEFAULT 0,
                absence_score REAL NOT NULL DEFAULT 0,
                dataset_id TEXT NOT NULL DEFAULT '',
                source_class TEXT NOT NULL DEFAULT '',
                name_source TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                appointment_at TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_consultations_student ON consultations(student_id);
        """)
        existing = {row[1] for row in db.execute("PRAGMA table_info(students)")}
        numeric_columns = (
            "raisedhands", "visited_resources", "announcements_view", "discussion", "absence_score"
        )
        text_columns = ("dataset_id", "source_class", "name_source")
        for name in numeric_columns:
            if name not in existing:
                db.execute(f"ALTER TABLE students ADD COLUMN {name} REAL NOT NULL DEFAULT 0")
        for name in text_columns:
            if name not in existing:
                db.execute(f"ALTER TABLE students ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")

        xapi_rows = None
        if dataset_path and Path(dataset_path).is_file():
            try:
                xapi_rows = load_xapi_rows(dataset_path)
            except DatasetFormatError:
                xapi_rows = None
        current_count = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        xapi_count = db.execute(
            "SELECT COUNT(*) FROM students WHERE dataset_id LIKE 'XAPI-%'"
        ).fetchone()[0]
        if xapi_rows and (current_count == 0 or xapi_count == 0):
            # Одноразовая миграция старых демонстрационных карточек на строки xAPI.
            db.execute("DELETE FROM consultations")
            db.execute("DELETE FROM students")
            db.executemany("""
                INSERT INTO students
                (name, student_group, attendance, engagement, grade, overdue, lms_change,
                 on_time_tasks, raisedhands, visited_resources, announcements_view,
                 discussion, absence_score, dataset_id, source_class, name_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [_xapi_student(row, index) for index, row in enumerate(xapi_rows)])
        elif current_count == 0:
            db.executemany("""
                INSERT INTO students
                (name, student_group, attendance, engagement, grade, overdue, lms_change,
                 on_time_tasks, dataset_id, name_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [(name, GROUP, att, eng, grade, overdue, lms, ontime,
                     f"DEMO-{index + 1:03d}", "fallback_demo")
                    for index, (name, att, eng, grade, overdue, lms, ontime)
                    in enumerate(SEED_STUDENTS)])
        db.execute("""
            UPDATE students SET
                raisedhands = CASE WHEN raisedhands = 0 THEN MIN(100, engagement * 0.82) ELSE raisedhands END,
                visited_resources = CASE WHEN visited_resources = 0 THEN MIN(100, engagement * 1.05) ELSE visited_resources END,
                announcements_view = CASE WHEN announcements_view = 0 THEN MIN(100, engagement * 0.68) ELSE announcements_view END,
                discussion = CASE WHEN discussion = 0 THEN MIN(100, engagement * 0.60) ELSE discussion END,
                absence_score = CASE WHEN attendance < 75 THEN 100 ELSE 0 END
            WHERE name_source IN ('', 'fallback_demo')
        """)


def students(db_path: str | Path) -> list[dict]:
    with connect(db_path) as db:
        return [dict(row) for row in db.execute("SELECT * FROM students ORDER BY id")]


def create_student(db_path: str | Path, values: dict) -> int:
    """Добавляет введённую пользователем карточку и возвращает внутренний ID."""
    with connect(db_path) as db:
        cursor = db.execute("""
            INSERT INTO students
            (name, student_group, attendance, engagement, grade, overdue, lms_change,
             on_time_tasks, raisedhands, visited_resources, announcements_view,
             discussion, absence_score, dataset_id, source_class, name_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', 'manual_entry')
        """, (
            values["name"], values["student_group"], values["attendance"],
            values["engagement"], values["grade"], values["overdue"],
            values["lms_change"], values["on_time_tasks"], values["raisedhands"],
            values["visited_resources"], values["announcements_view"],
            values["discussion"], values["absence_score"],
        ))
        ident = int(cursor.lastrowid)
        db.execute("UPDATE students SET dataset_id=? WHERE id=?", (f"MANUAL-{ident:03d}", ident))
        return ident


def consultations(db_path: str | Path, student_id: int | None = None) -> list[dict]:
    with connect(db_path) as db:
        if student_id is None:
            rows = db.execute("""SELECT c.*, s.name as student_name FROM consultations c
                                 JOIN students s ON s.id=c.student_id ORDER BY c.created_at DESC, c.id DESC""")
        else:
            rows = db.execute("""SELECT c.*, s.name as student_name FROM consultations c
                                 JOIN students s ON s.id=c.student_id WHERE student_id=?
                                 ORDER BY c.created_at DESC, c.id DESC""", (student_id,))
        return [dict(row) for row in rows]


def schedule(db_path: str | Path, student_id: int, appointment_at: str, note: str) -> int:
    with connect(db_path) as db:
        exists = db.execute("SELECT 1 FROM students WHERE id=?", (student_id,)).fetchone()
        if not exists:
            raise LookupError("Студент не найден")
        cursor = db.execute("""INSERT INTO consultations (student_id,appointment_at,note,created_at)
                              VALUES (?,?,?,?)""",
                            (student_id, appointment_at, note, datetime.now().isoformat(timespec='seconds')))
        return int(cursor.lastrowid)
