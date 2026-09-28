"""Data-source adapters and validation for the public market dashboard."""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


LOGGER = logging.getLogger(__name__)
TAIFEX_URL = "https://www.taifex.com.tw/cht/3/pcRatioDown"


class SourceUnavailable(RuntimeError):
    """The source did not return usable data for this dashboard."""


@dataclass(frozen=True)
class PutCallRatio:
    date: str
    ratio: float


@dataclass(frozen=True)
class MarketQuote:
    date: str
    price: float
    change_pct: float
    rsi: float


def parse_taifex_csv(content: bytes, target: date) -> PutCallRatio | None:
    """Use only the requested date; an empty valid CSV means no trading data."""
    try:
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = content.decode("cp950")
        table = pd.read_csv(io.StringIO(decoded))
    except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError("期交所檔案無法解析") from exc

    table.columns = table.columns.astype(str).str.strip()
    required = {"日期", "買賣權未平倉量比率%"}
    if not required.issubset(table.columns):
        raise ValueError("期交所回傳欄位與預期不符")
    if table.empty:
        return None

    dates = pd.to_datetime(table["日期"], errors="coerce").dt.date
    matching = table.loc[dates == target]
    if matching.empty:
        return None
    raw_ratio = str(matching.iloc[-1]["買賣權未平倉量比率%"])
    try:
        ratio = float(raw_ratio.replace(",", ""))
    except ValueError as exc:
        raise ValueError("期交所比率無法解析") from exc
    if not math.isfinite(ratio) or ratio < 0:
        raise ValueError("期交所比率不合理")
    return PutCallRatio(date=target.isoformat(), ratio=ratio)


def load_taifex_ratio(post=None, today: date | None = None) -> PutCallRatio:
    """Find the newest daily PCR in seven calendar days; fail visibly on errors."""
    if post is None:
        import requests

        post = requests.post
    today = today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    for days_back in range(7):
        target = today - timedelta(days=days_back)
        requested = target.strftime("%Y/%m/%d")
        try:
            response = post(
                TAIFEX_URL,
                data={"queryStartDate": requested, "queryEndDate": requested},
                timeout=8,
            )
            response.raise_for_status()
            result = parse_taifex_csv(response.content, target)
        except Exception as exc:  # External HTTP/CSV boundary: retain traceback in logs.
            LOGGER.exception("TAIFEX PCR request failed for %s", requested)
            raise SourceUnavailable("期交所連線失敗或回傳格式異常") from exc
        if result is not None:
            return result
    raise SourceUnavailable("最近七個日曆日查無可用的期交所資料")


def load_yahoo_quote(symbol: str, download=None) -> MarketQuote:
    """Get one Yahoo Finance daily series, refusing empty or malformed results."""
    if download is None:
        import yfinance as yf

        download = yf.download
    try:
        data = download(
            symbol, period="6mo", interval="1d", progress=False,
            auto_adjust=False, multi_level_index=False, timeout=10,
        )
    except Exception as exc:  # Third-party download boundary: retain traceback in logs.
        LOGGER.exception("Yahoo Finance download failed for %s", symbol)
        raise SourceUnavailable("Yahoo Finance 下載失敗") from exc

    try:
        if data is None or data.empty:
            raise ValueError("無資料")
        prices = data["Close"]
        if isinstance(prices, pd.DataFrame):
            if prices.shape[1] != 1:
                raise ValueError("收盤價欄位不唯一")
            prices = prices.iloc[:, 0]
        prices = pd.to_numeric(prices, errors="coerce").dropna()
        if len(prices) < 15:
            raise ValueError("有效日線不足 15 筆")
        current, previous = float(prices.iloc[-1]), float(prices.iloc[-2])
        if not all(map(math.isfinite, (current, previous))) or previous <= 0:
            raise ValueError("收盤價異常")

        change = prices.diff()
        avg_gain = change.clip(lower=0).rolling(14, min_periods=14).mean().iloc[-1]
        avg_loss = (-change.clip(upper=0)).rolling(14, min_periods=14).mean().iloc[-1]
        rsi = (100.0 if avg_gain > 0 else 50.0) if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        if not math.isfinite(rsi):
            raise ValueError("RSI 無法計算")
        return MarketQuote(
            date=prices.index[-1].strftime("%Y-%m-%d"),
            price=current,
            change_pct=(current - previous) / previous * 100,
            rsi=float(rsi),
        )
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        LOGGER.warning("Invalid Yahoo Finance data for %s: %s", symbol, exc)
        raise SourceUnavailable(f"Yahoo Finance 資料不可用：{exc}") from exc
