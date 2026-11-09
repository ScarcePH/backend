import unittest
from datetime import datetime, timedelta, timezone

from db.repository.dashboard import _to_local_naive_datetime


class DashboardDatetimeTestCase(unittest.TestCase):
    def test_naive_datetime_is_unchanged(self):
        value = datetime(2026, 11, 8, 12)

        self.assertEqual(value, _to_local_naive_datetime(value))

    def test_aware_datetime_is_converted_to_local_naive_datetime(self):
        value = datetime(
            2026, 11, 8, 12, tzinfo=timezone(timedelta(hours=8))
        )

        self.assertEqual(
            value.astimezone().replace(tzinfo=None),
            _to_local_naive_datetime(value),
        )
