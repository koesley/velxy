"""Regression tests for UTC-stable CRM customer task timeline dates."""
import datetime
import os
import time
import unittest
from unittest.mock import patch
import business_os_v59 as crm

class TaskTimelineUtcTests(unittest.TestCase):
    def test_epoch(self):
        self.assertEqual(crm.task_due_utc_timestamp("1970-01-01"), 0)
    def test_known_date(self):
        self.assertEqual(crm.task_due_utc_timestamp("2026-11-22"),
                         int(datetime.datetime(2026,11,22,tzinfo=datetime.timezone.utc).timestamp()))
    def test_dst_boundary(self):
        before=crm.task_due_utc_timestamp("2026-03-08")
        after=crm.task_due_utc_timestamp("2026-03-09")
        self.assertEqual(after-before, 86400)
    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            crm.task_due_utc_timestamp("2026-02-30")
    def test_no_localtime_dependency(self):
        with patch.object(time, "mktime", side_effect=AssertionError("local timezone used")):
            self.assertEqual(crm.task_due_utc_timestamp("1970-01-02"), 86400)

if __name__ == "__main__":
    unittest.main()
