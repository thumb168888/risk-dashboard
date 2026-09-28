"""Exercise the Streamlit page with fake sources, without live market requests."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from data_sources import MarketQuote, PutCallRatio, SourceUnavailable


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit is not installed")
class DashboardSmokeTest(unittest.TestCase):
    def test_failure_and_success_views(self):
        from streamlit.testing.v1 import AppTest

        # Check failure first: Streamlit caches successful source results across
        # AppTest sessions, just as it does across reruns of a real page.
        with patch("data_sources.load_taifex_ratio", side_effect=SourceUnavailable("測試失敗")), \
             patch("data_sources.load_yahoo_quote", side_effect=SourceUnavailable("測試失敗")):
            failed = AppTest.from_file(APP_PATH).run(timeout=30)

        self.assertEqual(len(failed.exception), 0)
        self.assertEqual(len(failed.warning), 7)

        quote = MarketQuote("2026-09-01", 100.0, 1.0, 50.0)
        ratio = PutCallRatio("2026-09-01", 95.0)
        with patch("data_sources.load_taifex_ratio", return_value=ratio), \
             patch("data_sources.load_yahoo_quote", return_value=quote):
            app = AppTest.from_file(APP_PATH).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 7)
        self.assertEqual(len(app.warning), 0)


if __name__ == "__main__":
    unittest.main()
