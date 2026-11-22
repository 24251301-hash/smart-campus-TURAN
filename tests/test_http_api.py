import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

import server


class HttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_db = server.DB_PATH
        cls.old_xapi = server.XAPI_PATH
        server.DB_PATH = Path(cls.tmp.name) / "http.sqlite3"
        server.XAPI_PATH = Path(cls.tmp.name) / "missing-xapi.csv"
        server.MODEL = None
        server.bootstrap()
        cls.httpd = server.SmartCampusHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        cls.post(cls, "/api/auth/register", {"full_name": "Ким Елена", "email": "teacher@turan-edu.kz",
                                             "role": "teacher", "detail": "СИИ", "password": "teacher123"})

    def post(self, path, payload):
        request = Request(self.base + path, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        return self.opener.open(request, timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)
        server.DB_PATH = cls.old_db
        server.XAPI_PATH = cls.old_xapi
        server.MODEL = None
        server._enriched_cached.cache_clear()
        cls.tmp.cleanup()

    def get_json(self, path):
        with self.opener.open(self.base + path, timeout=5) as response:
            return response.status, json.load(response)

    def test_health_dashboard_and_dataset_endpoints(self):
        self.assertEqual(self.get_json("/api/health")[0], 200)
        status, dashboard = self.get_json("/api/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["count"], 28)
        status, dataset = self.get_json("/api/dataset")
        self.assertEqual(status, 200)
        self.assertFalse(dataset["available"])

    def test_search_is_url_decoded_and_filtered(self):
        status, data = self.get_json("/api/students?search=%D0%94%D0%B8%D0%B0%D1%81&risk=all")
        self.assertEqual(status, 200)
        self.assertEqual(data["shown"], 2)

    def test_static_files_are_served_with_nosniff(self):
        with urlopen(self.base + "/", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertIn("Smart Campus TURAN", body)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_invalid_consultation_returns_400(self):
        request = Request(
            self.base + "/api/consultations",
            data=json.dumps({"student_id": 1, "appointment_at": "bad", "note": "короткая заметка"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            self.opener.open(request, timeout=5)
        self.assertEqual(raised.exception.code, 400)
        payload = json.loads(raised.exception.read().decode("utf-8"))
        self.assertIn("error", payload)

    def test_z_add_student_endpoint(self):
        payload = {
            "name": "Новый Студент", "student_group": "ИС-242(4)-2",
            "attendance": 90, "engagement": 82, "grade": 3.6, "overdue": 0,
        }
        request = Request(
            self.base + "/api/students",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(request, timeout=5) as response:
            self.assertEqual(response.status, 201)
            created = json.load(response)
        self.assertTrue(created["dataset_id"].startswith("MANUAL-"))
        status, found = self.get_json("/api/students?search=MANUAL-&risk=all")
        self.assertEqual(status, 200)
        self.assertEqual(found["shown"], 1)

    def test_anonymous_requests_are_rejected(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + "/api/dashboard", timeout=5)
        self.assertEqual(raised.exception.code, 401)

    def test_student_role_is_read_only(self):
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        reg = Request(self.base + "/api/auth/register", data=json.dumps({
            "full_name": "Студент Тест", "email": "student@turan-edu.kz", "role": "student",
            "detail": "ИС-242(4)-2", "password": "student123"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with opener.open(reg, timeout=5) as response:
            self.assertEqual(response.status, 201)
            self.assertFalse(json.load(response)["user"]["can_edit"])
        add = Request(self.base + "/api/students", data=json.dumps({"name": "X Y", "student_group": "G",
            "attendance": 50, "engagement": 50, "grade": 3, "overdue": 0}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as raised:
            opener.open(add, timeout=5)
        self.assertEqual(raised.exception.code, 403)

    def test_profile_and_password_flow(self):
        with self.opener.open(self.base + "/api/auth/me", timeout=5) as response:
            self.assertEqual(json.load(response)["user"]["role_label"], "Преподаватель")
        with self.post("/api/profile", {"full_name": "Ким Елена Р.", "detail": "СИИ", "about": "Куратор"}) as response:
            self.assertEqual(json.load(response)["user"]["about"], "Куратор")
        with self.assertRaises(HTTPError) as raised:
            self.post("/api/profile/password", {"old_password": "wrong", "new_password": "newpass123"})
        self.assertEqual(raised.exception.code, 400)

    def test_duplicate_email_and_bad_password(self):
        with self.assertRaises(HTTPError) as raised:
            self.post("/api/auth/register", {"full_name": "Дубль", "email": "TEACHER@turan-edu.kz",
                                             "role": "teacher", "password": "teacher123"})
        self.assertIn("уже зарегистрирован", json.loads(raised.exception.read())["error"])
        with self.assertRaises(HTTPError) as raised:
            self.post("/api/auth/login", {"email": "teacher@turan-edu.kz", "password": "wrong-pass1"})
        self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
