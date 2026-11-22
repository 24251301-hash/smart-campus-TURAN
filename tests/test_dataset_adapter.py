import csv
import tempfile
import unittest
from pathlib import Path

from dataset_adapter import DatasetFormatError, dataset_summary, load_xapi_rows, rows_to_matrix
from ml_engine import ModelEngine


HEADERS = [
    "StudentID", "StudentName", "StudentGroup", "NameSource",
    "gender", "NationalITy", "PlaceofBirth", "StageID", "GradeID", "SectionID",
    "Topic", "Semester", "Relation", "raisedhands", "VisITedResources",
    "AnnouncementsView", "Discussion", "ParentAnsweringSurvey",
    "ParentschoolSatisfaction", "StudentAbsenceDays", "Class",
]


def write_fixture(path: Path, rows: int = 45) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        for index in range(rows):
            label = ("L", "M", "H")[index % 3]
            low = label == "L"
            high = label == "H"
            writer.writerow({
                "StudentID": f"XAPI-{index + 1:03d}",
                "StudentName": f"Студент {index + 1}",
                "StudentGroup": "XAPI-MiddleSchool-G-08-A",
                "NameSource": "synthetic_demo",
                "gender": "M", "NationalITy": "Jordan", "PlaceofBirth": "Jordan",
                "StageID": "MiddleSchool", "GradeID": "G-08", "SectionID": "A",
                "Topic": "IT", "Semester": "F", "Relation": "Father",
                "raisedhands": 15 if low else 85 if high else 50,
                "VisITedResources": 20 if low else 92 if high else 58,
                "AnnouncementsView": 18 if low else 80 if high else 45,
                "Discussion": 12 if low else 75 if high else 40,
                "ParentAnsweringSurvey": "Yes", "ParentschoolSatisfaction": "Good",
                "StudentAbsenceDays": "Above-7" if low else "Under-7",
                "Class": label,
            })


class DatasetAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "xAPI-Edu-Data.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_dataset_has_explicit_fallback_status(self):
        summary = dataset_summary(self.path)
        self.assertFalse(summary["available"])
        self.assertEqual(summary["rows"], 0)

    def test_valid_dataset_is_loaded_and_summarized(self):
        write_fixture(self.path)
        rows = load_xapi_rows(self.path)
        x, y = rows_to_matrix(rows)
        self.assertEqual(x.shape, (45, 5))
        self.assertEqual(set(y), {"high", "medium", "normal"})
        self.assertEqual(rows[0]["student_id"], "XAPI-001")
        self.assertEqual(rows[0]["student_name"], "Студент 1")
        summary = dataset_summary(self.path)
        self.assertTrue(summary["available"])
        self.assertEqual(summary["rows"], 45)
        self.assertEqual(summary["named_rows"], 45)

    def test_invalid_schema_is_rejected(self):
        self.path.write_text("Class,raisedhands\nH,50\n", encoding="utf-8")
        with self.assertRaises(DatasetFormatError):
            load_xapi_rows(self.path)

    def test_model_can_train_on_xapi_format(self):
        write_fixture(self.path, rows=60)
        model = ModelEngine.train(str(self.path))
        self.assertEqual(model.quality["training_source"], "Открытый набор xAPI-Edu-Data")
        prediction = model.predict({
            "raisedhands": 10, "visited_resources": 15,
            "announcements_view": 10, "discussion": 10, "absence_score": 100,
        })
        self.assertIn(prediction["risk"], {"high", "medium", "normal"})


if __name__ == "__main__":
    unittest.main()
