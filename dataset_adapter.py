"""Загрузка и проверка открытого набора xAPI-Edu-Data.

В учебной версии к исходным строкам добавлены StudentID, синтетические ФИО и
группы. Они нужны только для карточек интерфейса и не участвуют в обучении ML.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


XAPI_FEATURE_COLUMNS = (
    "raisedhands",
    "VisITedResources",
    "AnnouncementsView",
    "Discussion",
    "StudentAbsenceDays",
)
XAPI_REQUIRED_COLUMNS = (*XAPI_FEATURE_COLUMNS, "Class")
XAPI_IDENTITY_COLUMNS = ("StudentID", "StudentName", "StudentGroup", "NameSource")
XAPI_MODEL_FEATURES = (
    "raisedhands",
    "visited_resources",
    "announcements_view",
    "discussion",
    "absence_score",
)
CLASS_TO_RISK = {"H": "normal", "M": "medium", "L": "high"}
ABSENCE_TO_SCORE = {"Under-7": 0.0, "Above-7": 100.0}


class DatasetFormatError(ValueError):
    """Файл существует, но не соответствует схеме xAPI-Edu-Data."""


def _number(row: dict[str, str], name: str, line: int) -> float:
    try:
        value = float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetFormatError(f"Строка {line}: поле {name} должно быть числом") from exc
    if not 0 <= value <= 100:
        raise DatasetFormatError(f"Строка {line}: поле {name} вне диапазона 0-100")
    return value


def load_xapi_rows(path: str | Path) -> list[dict[str, Any]]:
    """Читает CSV и возвращает ML-признаки и необязательную учебную идентичность."""
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or ())
        missing = [name for name in XAPI_REQUIRED_COLUMNS if name not in headers]
        if missing:
            raise DatasetFormatError("Отсутствуют обязательные столбцы: " + ", ".join(missing))

        result: list[dict[str, Any]] = []
        for line, row in enumerate(reader, start=2):
            absence = str(row.get("StudentAbsenceDays", "")).strip()
            label = str(row.get("Class", "")).strip().upper()
            if absence not in ABSENCE_TO_SCORE:
                raise DatasetFormatError(
                    f"Строка {line}: StudentAbsenceDays должен быть Under-7 или Above-7"
                )
            if label not in CLASS_TO_RISK:
                raise DatasetFormatError(f"Строка {line}: Class должен быть H, M или L")
            result.append({
                "student_id": str(row.get("StudentID", "")).strip(),
                "student_name": str(row.get("StudentName", "")).strip(),
                "student_group": str(row.get("StudentGroup", "")).strip(),
                "name_source": str(row.get("NameSource", "")).strip(),
                "raisedhands": _number(row, "raisedhands", line),
                "visited_resources": _number(row, "VisITedResources", line),
                "announcements_view": _number(row, "AnnouncementsView", line),
                "discussion": _number(row, "Discussion", line),
                "absence_score": ABSENCE_TO_SCORE[absence],
                "risk": CLASS_TO_RISK[label],
                "class_label": label,
            })

    if len(result) < 30:
        raise DatasetFormatError("Для обучения требуется не менее 30 корректных строк")
    return result


def rows_to_matrix(rows: Iterable[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    records = list(rows)
    x = np.asarray(
        [[float(row[name]) for name in XAPI_MODEL_FEATURES] for row in records],
        dtype=float,
    )
    y = np.asarray([str(row["risk"]) for row in records])
    return x, y


def dataset_summary(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {
            "available": False,
            "expected_path": str(source),
            "dataset": "xAPI-Edu-Data",
            "rows": 0,
            "message": "CSV не найден; используется воспроизводимый синтетический резервный набор.",
        }
    rows = load_xapi_rows(source)
    distribution = Counter(str(row["risk"]) for row in rows)
    named_rows = sum(bool(row.get("student_name")) for row in rows)
    return {
        "available": True,
        "expected_path": str(source),
        "dataset": "xAPI-Edu-Data",
        "rows": len(rows),
        "class_distribution": dict(distribution),
        "named_rows": named_rows,
        "identity_source": "synthetic_demo" if named_rows else "not_provided",
        "features": list(XAPI_MODEL_FEATURES),
        "message": "Файл проверен и может использоваться для обучения модели.",
    }
