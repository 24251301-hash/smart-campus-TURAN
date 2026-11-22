"""Небольшое воспроизводимое нагрузочное испытание локального API."""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percent))
    return ordered[index]


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        old_db, old_xapi = server.DB_PATH, server.XAPI_PATH
        server.DB_PATH = Path(folder) / "load.sqlite3"
        server.XAPI_PATH = Path(__file__).resolve().parents[1] / "data" / "xAPI-Edu-Data.csv"
        server.MODEL = None
        server.bootstrap()
        class QuietHandler(server.Handler):
            def log_message(self, format, *args):
                return

        httpd = server.SmartCampusHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        url = base + "/api/dashboard"
        reg = Request(base + "/api/auth/register", data=json.dumps({
            "full_name": "Нагрузочный Тест", "email": "load@turan-edu.kz", "role": "teacher",
            "password": "loadtest123"}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(reg, timeout=10) as response:
            cookie = response.headers["Set-Cookie"].split(";")[0]

        def one_request(_: int) -> tuple[float, bool]:
            started = time.perf_counter()
            try:
                with urlopen(Request(url, headers={"Cookie": cookie}), timeout=10) as response:
                    ok = response.status == 200 and bool(response.read())
            except Exception:
                ok = False
            return (time.perf_counter() - started) * 1000, ok

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(one_request, range(100)))
        duration = time.perf_counter() - started
        latencies = [elapsed for elapsed, _ in results]
        passed = sum(ok for _, ok in results)
        report = {
            "requests": len(results),
            "concurrency": 12,
            "successful": passed,
            "errors": len(results) - passed,
            "duration_seconds": round(duration, 3),
            "requests_per_second": round(len(results) / duration, 1),
            "latency_ms": {
                "median": round(statistics.median(latencies), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "maximum": round(max(latencies), 2),
            },
        }
        artifacts = Path(__file__).resolve().parents[1] / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "load_test.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))

        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
        server.DB_PATH, server.XAPI_PATH = old_db, old_xapi
        server.MODEL = None
        server._enriched_cached.cache_clear()


if __name__ == "__main__":
    main()
