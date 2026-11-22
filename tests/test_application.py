"""Запуск: python -m unittest discover -s tests -v."""
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from ml_engine import ModelEngine, make_training_data, synthetic_risk_rule
from storage import init_db, students as read_students


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_path = server.DB_PATH
        server.DB_PATH = Path(cls.tmp.name) / 'test.sqlite3'
        server.bootstrap()

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.old_path
        cls.tmp.cleanup()

    def test_database_is_seeded_once(self):
        self.assertEqual(len(read_students(server.DB_PATH)), 480)
        init_db(server.DB_PATH)
        self.assertEqual(len(read_students(server.DB_PATH)), 480)

    def test_health_and_dashboard(self):
        status, d = server.api_response('/api/dashboard', {}, 'GET')
        self.assertEqual(status, 200)
        self.assertEqual(d['count'], 480)
        self.assertEqual(sum(d['by_risk'].values()), 480)
        self.assertEqual(d['at_risk'], d['high_risk'] + d['by_risk']['medium'])
        self.assertGreater(d['on_time_total'], 0)

    def test_filters_and_search(self):
        status, d = server.api_response('/api/students', {'risk': ['at-risk']}, 'GET')
        self.assertEqual(status, 200)
        self.assertTrue(all(x['risk']!='normal' for x in d['items']))
        status, d = server.api_response('/api/students', {'search': ['xapi-001']}, 'GET')
        self.assertEqual(status, 200)
        self.assertEqual(d['shown'], 1)
        self.assertEqual(d['items'][0]['name'], 'Ахметов Алихан')
        status, d = server.api_response('/api/students', {'risk': ['invalid']}, 'GET')
        self.assertEqual(status, 400)

    def test_profile_and_missing_student(self):
        status, d = server.api_response('/api/students/1', {}, 'GET')
        self.assertEqual(status, 200)
        self.assertEqual(d['name'], 'Ахметов Алихан')
        self.assertEqual(d['dataset_id'], 'XAPI-001')
        self.assertEqual(d['name_source'], 'synthetic_demo')
        self.assertEqual(len(d['model_methods']), 2)
        self.assertTrue(d['factors'])
        self.assertEqual(server.api_response('/api/students/999999', {}, 'GET')[0], 404)

    def test_both_models_work(self):
        engine = server.MODEL
        self.assertIsNotNone(engine)
        x, labels = make_training_data(n=50)
        self.assertEqual(len(x), 50)
        self.assertEqual(len(labels), 50)
        s = read_students(server.DB_PATH)[0]
        prediction = engine.predict(s)
        self.assertIn(prediction['risk'], ('high', 'medium', 'normal'))
        self.assertIsInstance(prediction['is_anomaly'], bool)
        self.assertTrue(0 <= prediction['confidence'] <= 1)

    def test_analytics(self):
        status, data = server.api_response('/api/analytics', {}, 'GET')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['factors']), 4)
        self.assertIn('training_source', data['model'])
        self.assertTrue(all('message' in alert for alert in data['alerts']))

    def test_consultation_validation_and_storage(self):
        future = (datetime.now() + timedelta(days=3)).isoformat(timespec='minutes')
        invalid = dict(student_id=1, appointment_at=future, note='X')
        self.assertEqual(server.api_response('/api/consultations', {}, 'POST', invalid)[0], 400)
        invalid['note'] = 'Уточнить причины пропусков и активность LMS'
        invalid['student_id'] = 99999
        self.assertEqual(server.api_response('/api/consultations', {}, 'POST', invalid)[0], 404)
        invalid['student_id'] = 1
        status, data = server.api_response('/api/consultations', {}, 'POST', invalid)
        self.assertEqual(status, 201)
        self.assertIn('id', data)
        status, rows = server.api_response('/api/consultations', {}, 'GET')
        self.assertEqual(len(rows['items']), 1)
        self.assertEqual(server.api_response('/api/students/1', {}, 'GET')[1]['consultations'][0]['student_id'], 1)

    def test_z_add_student_to_database(self):
        payload = {
            'name': 'Тестовый Студент', 'student_group': 'ИС-242(4)-2',
            'attendance': 88, 'engagement': 76, 'grade': 3.4, 'overdue': 1,
        }
        status, created = server.api_response('/api/students', {}, 'POST', payload)
        self.assertEqual(status, 201)
        self.assertTrue(created['dataset_id'].startswith('MANUAL-'))
        self.assertEqual(created['student']['name_source'], 'manual_entry')
        self.assertEqual(len(read_students(server.DB_PATH)), 481)
        self.assertEqual(server.api_response('/api/students', {}, 'POST', {**payload, 'grade': 5})[0], 400)


if __name__ == '__main__':
    unittest.main()
