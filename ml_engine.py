"""Два воспроизводимых метода ML для демонстрационного мониторинга.

При наличии data/xAPI-Edu-Data.csv модель обучается на открытом наборе xAPI.
Без файла используется синтетический резервный набор с той же схемой признаков.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from dataset_adapter import XAPI_MODEL_FEATURES, load_xapi_rows, rows_to_matrix

FEATURES = XAPI_MODEL_FEATURES
RISK_RU = {"high": "Высокий", "medium": "Средний", "normal": "Норма"}
SEED = 20261024


def synthetic_risk_rule(raisedhands: float, visited_resources: float, announcements_view: float,
                        discussion: float, absence_score: float) -> str:
    """Правило генерации искусственных меток (НЕ истинные медицинские/учебные выводы)."""
    score = (0.18 * (100 - raisedhands)
             + 0.34 * (100 - visited_resources)
             + 0.16 * (100 - announcements_view)
             + 0.14 * (100 - discussion)
             + 0.28 * absence_score)
    return "high" if score >= 43 else "medium" if score >= 24 else "normal"


def make_training_data(n: int = 1400, seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    raisedhands = rng.uniform(0, 100, n)
    visited_resources = rng.uniform(0, 100, n)
    announcements_view = rng.uniform(0, 100, n)
    discussion = rng.uniform(0, 100, n)
    absence_score = rng.choice([0.0, 100.0], size=n, p=[0.62, 0.38])
    x = np.stack([
        raisedhands, visited_resources, announcements_view, discussion, absence_score
    ], axis=1)
    y = np.array([synthetic_risk_rule(*row) for row in x])
    return x, y


@dataclass
class ModelEngine:
    classifier: RandomForestClassifier
    detector: IsolationForest
    quality: dict[str, Any]

    @classmethod
    def train(cls, dataset_path: str | None = None, seed: int = SEED) -> "ModelEngine":
        source = "Автоматически сгенерированные синтетические данные"
        if dataset_path:
            x, y = rows_to_matrix(load_xapi_rows(dataset_path))
            source = "Открытый набор xAPI-Edu-Data"
        else:
            x, y = make_training_data(seed=seed)
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=seed, stratify=y
        )
        forest = RandomForestClassifier(
            n_estimators=160, min_samples_leaf=2, max_depth=12,
            class_weight="balanced", random_state=seed, n_jobs=1
        )
        forest.fit(x_train, y_train)
        predictions = forest.predict(x_test)
        detector = IsolationForest(
            n_estimators=120, contamination=0.12, random_state=seed, n_jobs=1
        )
        detector.fit(x_train)
        return cls(forest, detector, {
            "validation_accuracy": round(float(accuracy_score(y_test, predictions)), 3),
            "validation_macro_f1": round(float(f1_score(y_test, predictions, average="macro")), 3),
            "training_rows": int(len(x_train)), "test_rows": int(len(x_test)),
            "training_source": source,
            "warning": (
                "Модель демонстрационная; переносимость результатов на студентов университета "
                "должна проверяться на локальных обезличенных данных."
            ),
            "methods": ["Random Forest — классификация", "Isolation Forest — обнаружение аномалий"],
            "feature_importance": [
                {"name": name, "importance": round(float(value), 4)}
                for name, value in zip(FEATURES, forest.feature_importances_)
            ]
        })

    def predict(self, student: dict[str, Any]) -> dict[str, Any]:
        return self.predict_many([student])[0]

    def predict_many(self, students: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Пакетный прогноз для сотен карточек без повторных вызовов моделей."""
        if not students:
            return []
        x = np.asarray(
            [[float(student[name]) for name in FEATURES] for student in students],
            dtype=float,
        )
        risks = self.classifier.predict(x)
        probabilities = self.classifier.predict_proba(x)
        anomalies = self.detector.predict(x)
        raw_scores = self.detector.decision_function(x)
        return [{
            "risk": str(risk),
            "risk_label": RISK_RU[str(risk)],
            "confidence": round(float(np.max(probability)), 3),
            "is_anomaly": bool(anomaly == -1),
            "anomaly_score": round(float(raw_score), 3),
            "model_methods": self.quality["methods"],
        } for risk, probability, anomaly, raw_score in zip(
            risks, probabilities, anomalies, raw_scores
        )]


def observations(student: dict[str, Any], group_avg: float) -> list[str]:
    notes: list[str] = []
    if student["engagement"] < group_avg:
        notes.append(f"Вовлечённость ниже средней по группе на {group_avg - student['engagement']:.0f} п. п.")
    if student["attendance"] < 75:
        notes.append(f"Посещаемость {student['attendance']:.0f}%: показатель требует внимания.")
    if student["overdue"] > 0:
        notes.append(f"Просроченных заданий: {student['overdue']}.")
    if student["lms_change"] <= -15:
        notes.append(f"Активность LMS изменилась на {student['lms_change']:.0f}% относительно прошлого периода.")
    if student["grade"] < 3:
        notes.append(f"Средний балл {student['grade']:.1f} из 4.")
    if not notes:
        notes.append("Выраженных факторов снижения активности по выбранным показателям нет.")
    return notes


def recommendation(student: dict[str, Any], risk: str) -> str:
    if risk == "high":
        return "Предложить индивидуальную консультацию, выяснить причины снижения активности и проверить изменения через 7 дней."
    if risk == "medium":
        return "Напомнить о сроках заданий, уточнить учебные затруднения и проверить показатели на следующей неделе."
    return "Продолжать наблюдение, поддерживать стабильное участие в учебном процессе."
