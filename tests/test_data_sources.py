"""Offline checks for the source boundary and daily-series calculations."""

import unittest
from datetime import date

import pandas as pd

from data_sources import SourceUnavailable, load_taifex_ratio, load_yahoo_quote


class FakeResponse:
    def __init__(self, content: bytes, error: Exception | None = None):
        self.content = content
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class SourcesTest(unittest.TestCase):
    def test_taifex_skips_empty_day_and_uses_matching_date(self):
        seen = []
        csv = "日期,買賣權未平倉量比率%\n2026/9/27,92.50\n2026/9/28,101.25\n".encode()

        def post(_url, *, data, timeout):
            seen.append(data["queryStartDate"])
            self.assertGreater(timeout, 0)
            if data["queryStartDate"] == "2026/09/28":
                return FakeResponse("日期,買賣權未平倉量比率%\n".encode("utf-8-sig"))
            return FakeResponse(csv)

        result = load_taifex_ratio(post=post, today=date(2026, 9, 28))
        self.assertEqual((result.date, result.ratio), ("2026-09-27", 92.5))
        self.assertEqual(seen, ["2026/09/28", "2026/09/27"])

    def test_taifex_http_failure_is_visible_instead_of_older_fallback(self):
        def post(_url, **_kwargs):
            return FakeResponse(b"", ConnectionError("offline"))

        with self.assertLogs("data_sources", level="ERROR"):
            with self.assertRaisesRegex(SourceUnavailable, "期交所連線失敗"):
                load_taifex_ratio(post=post, today=date(2026, 9, 28))

    def test_taifex_schema_change_is_visible(self):
        with self.assertLogs("data_sources", level="ERROR"):
            with self.assertRaisesRegex(SourceUnavailable, "回傳格式異常"):
                load_taifex_ratio(
                    post=lambda *_a, **_k: FakeResponse(b"<html>different response</html>"),
                    today=date(2026, 9, 28),
                )

    def test_yahoo_valid_series_and_rsi(self):
        series = [100.0] + [float(100 + day) for day in range(1, 16)]
        frame = pd.DataFrame({"Close": series}, index=pd.date_range("2026-09-01", periods=16))
        quote = load_yahoo_quote("EWT", download=lambda *_a, **_k: frame)
        self.assertEqual(quote.date, "2026-09-16")
        self.assertEqual(quote.price, 115)
        self.assertAlmostEqual(quote.change_pct, 100 / 114)
        self.assertEqual(quote.rsi, 100)

    def test_yahoo_missing_and_network_errors_are_visible(self):
        with self.assertLogs("data_sources", level="WARNING"):
            with self.assertRaisesRegex(SourceUnavailable, "無資料"):
                load_yahoo_quote("EWT", download=lambda *_a, **_k: pd.DataFrame())

        def offline(*_args, **_kwargs):
            raise ConnectionError("offline")

        with self.assertLogs("data_sources", level="ERROR"):
            with self.assertRaisesRegex(SourceUnavailable, "下載失敗"):
                load_yahoo_quote("EWT", download=offline)


if __name__ == "__main__":
    unittest.main()
