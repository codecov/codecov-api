from django.test import TestCase

from core.models import Commit

from .factories import CommitFactory


class CommitTests(TestCase):
    def setUp(self):
        self.commit = CommitFactory()

    def test_report_totals_by_file_name(self):
        report_totals_by_file_name = sorted(
            Commit.report_totals_by_file_name(self.commit.id),
            key=lambda report: report.file_name,
        )

        self.assertEqual(report_totals_by_file_name[0].file_name, "awesome/__init__.py")
        self.assertEqual(
            report_totals_by_file_name[0].totals,
            [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
        )

        self.assertEqual(report_totals_by_file_name[1].file_name, "tests/__init__.py")
        self.assertEqual(
            report_totals_by_file_name[1].totals,
            [0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0],
        )

        self.assertEqual(
            report_totals_by_file_name[2].file_name, "tests/test_sample.py"
        )
        self.assertEqual(
            report_totals_by_file_name[2].totals,
            [0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0],
        )

    def test_report_totals_by_file_name_null_report(self):
        self.commit.report = None
        self.commit.save()

        report_totals_by_file_name = list(
            Commit.report_totals_by_file_name(self.commit.id)
        )
        self.assertEqual(report_totals_by_file_name, [])
