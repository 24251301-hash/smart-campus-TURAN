"""Пять автоматизированных пользовательских сценариев в Chromium (после входа в систему)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    playwright_tmp = artifacts / "playwright-tmp"
    playwright_tmp.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(playwright_tmp)
    results: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory() as folder:
        old_db, old_xapi = server.DB_PATH, server.XAPI_PATH
        server.DB_PATH = Path(folder) / "ui.sqlite3"
        server.XAPI_PATH = root / "data" / "xAPI-Edu-Data.csv"
        server.MODEL = None
        server.bootstrap()
        class QuietHandler(server.Handler):
            def log_message(self, format, *args):
                return

        httpd = server.SmartCampusHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"

        def record(name: str, action) -> None:
            try:
                action()
                results.append({"scenario": name, "status": "passed"})
            except Exception as exc:
                results.append({"scenario": name, "status": "failed", "detail": str(exc)})
                raise

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            # Вход в систему: регистрируем преподавателя, cookie сессии сохраняется в контексте
            page.request.post(base + "/api/auth/register", data={
                "full_name": "UI Тест", "email": "ui@turan-edu.kz", "role": "teacher", "password": "uitest123"})

            def overview():
                page.goto(base + "/#/overview", wait_until="networkidle")
                page.get_by_role("heading", name="Панель преподавателя").wait_for()
                assert page.locator(".stat-card").count() == 4
                page.screenshot(path=str(artifacts / "ui_overview.png"), full_page=True)
            record("S1 Обзор показателей группы", overview)

            def list_and_filter():
                page.goto(base + "/#/students", wait_until="networkidle")
                page.locator("button[data-filter='at-risk']").click()
                page.locator("#search").fill("XAPI-001")
                page.wait_for_timeout(350)
                assert page.locator("tbody tr").count() >= 1
            record("S2 Фильтрация и поиск студента", list_and_filter)

            def profile():
                page.locator("tbody tr").first.click()
                page.get_by_role("heading", name="Профиль студента").wait_for()
                assert page.get_by_text("ИИ-анализ учебного риска").count() == 1
                assert page.get_by_role("button", name="Назначить консультацию").is_visible()
            record("S3 Просмотр профиля и рекомендации", profile)

            def analytics():
                page.goto(base + "/#/analytics", wait_until="networkidle")
                page.get_by_role("heading", name="Аналитика и риски").wait_for()
                assert page.get_by_text("Источник обучения:").count() == 1
                page.screenshot(path=str(artifacts / "ui_analytics.png"), full_page=True)
            record("S4 Аналитика и источник модели", analytics)

            def mobile():
                mobile_page = page.context.browser.new_page(viewport={"width": 390, "height": 844})
                mobile_page.request.post(base + "/api/auth/login", data={"email": "ui@turan-edu.kz", "password": "uitest123"})
                mobile_page.goto(base + "/#/overview", wait_until="networkidle")
                mobile_page.get_by_role("heading", name="Панель преподавателя").wait_for()
                overflow = mobile_page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                assert not overflow
                mobile_page.screenshot(path=str(artifacts / "ui_mobile.png"), full_page=True)
                mobile_page.close()
            record("S5 Мобильная компоновка", mobile)

            browser.close()

        (artifacts / "ui_smoke.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))

        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
        server.DB_PATH, server.XAPI_PATH = old_db, old_xapi
        server.MODEL = None
        server._enriched_cached.cache_clear()


if __name__ == "__main__":
    main()
