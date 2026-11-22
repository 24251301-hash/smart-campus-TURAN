"""Статические проверки обязательных элементов интерфейса и адаптивности."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")


class FrontendContractTests(unittest.TestCase):
    def test_document_language_and_mobile_viewport(self):
        self.assertIn('<html lang="ru">', HTML)
        self.assertIn('name="viewport"', HTML)

    def test_main_landmarks_are_accessible(self):
        self.assertIn('aria-label="Основное меню"', HTML)
        self.assertIn('aria-live="polite"', HTML)
        self.assertIn('tabindex="-1"', HTML)

    def test_required_routes_exist(self):
        for route in ("#/overview", "#/students", "#/analytics"):
            self.assertIn(route, HTML + JS)

    def test_filters_and_consultation_flow_exist(self):
        self.assertIn('data-filter="at-risk"', JS)
        self.assertIn('id="consult-form"', JS)
        self.assertIn('id="add-student-form"', JS)
        self.assertIn("Добавить студента", JS)
        self.assertIn('/api/consultations', JS)
        self.assertIn("'/api/students'", JS)

    def test_mobile_and_reduced_motion_styles_exist(self):
        self.assertIn('@media(max-width:720px)', CSS)
        self.assertIn('@media(prefers-reduced-motion:reduce)', CSS)

    def test_user_feedback_improvements_exist(self):
        """Доработки по итогам пользовательского тестирования (13 участников)."""
        self.assertIn('class="hint"', JS)            # подсказки к показателям
        self.assertIn('guide-note', JS)              # «Как читать панель»
        self.assertIn('novalidate', JS)              # собственная проверка формы
        self.assertIn('field-help', JS)              # подсказки под полями
        self.assertIn('success-banner', JS)          # подтверждение добавления
        self.assertIn('wake-note', JS + HTML)        # сообщение о запуске сервера

    def test_accounts_and_profile_ui_exist(self):
        self.assertIn('id="auth-root"', HTML)
        self.assertIn('#/profile', HTML)
        self.assertIn('Мой профиль', HTML)
        for text in ("Преподаватель", "Студент", "Работник университета", "Другое"):
            self.assertIn(text, JS)
        self.assertIn("/api/auth/register", JS)
        self.assertIn("/api/auth/login", JS)
        self.assertIn("id=\"profile-form\"", JS)
        self.assertIn("id=\"password-form\"", JS)


if __name__ == "__main__":
    unittest.main()
