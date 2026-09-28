"""Read-only dashboard for publicly available market indicators."""

from datetime import datetime
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import streamlit as st

from data_sources import SourceUnavailable, load_taifex_ratio, load_yahoo_quote


st.set_page_config(page_title="牧羊人市場觀察", layout="wide", page_icon="📊")


@st.cache_data(ttl=3600)
def get_taifex_ratio():
    return load_taifex_ratio()


@st.cache_data(ttl=60)
def get_quote(symbol):
    return load_yahoo_quote(symbol)


def gauge(value, title, maximum=100):
    maximum = max(maximum, value * 1.2)
    figure = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text": title, "font": {"size": 15}},
        gauge={"axis": {"range": [0, maximum]}, "bar": {"color": "#40b6a4"},
               "bgcolor": "#263246"},
    ))
    figure.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=10))
    return figure


st.title("📊 牧羊人市場觀察")
st.caption("公開市場指標的唯讀觀察頁；各卡片的資料日期可能不同。數值不是交易建議。")

st.sidebar.header("更新")
auto_refresh = st.sidebar.checkbox("每 60 秒檢查一次", value=False)
if st.sidebar.button("立即重新整理"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("頁面檢查不代表資料來源已有新資料。")


@st.fragment(run_every="60s" if auto_refresh else None)
def render_dashboard():
    updated_at = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"頁面檢查時間：{updated_at}（臺北）")

    st.subheader("臺指選擇權 Put/Call 比")
    try:
        pcr = get_taifex_ratio()
    except SourceUnavailable as exc:
        st.warning(f"期交所：{exc}。請稍後重新整理。")
    else:
        left, right = st.columns([1, 2])
        with left:
            st.metric("賣權／買權未平倉量比率", f"{pcr.ratio:.2f}%")
            st.caption(f"資料日期：{pcr.date}｜來源：臺灣期貨交易所")
        with right:
            st.plotly_chart(gauge(pcr.ratio, "Put/Call 未平倉量比率", 150), width="stretch", key="pcr-gauge")

    st.subheader("市場指標")
    symbols = [
        ("^VIX", "VIX 指數"), ("DX-Y.NYB", "美元指數"),
        ("^TNX", "美國十年期公債殖利率指數"), ("JPY=X", "美元／日圓"),
        ("EWT", "EWT ETF"), ("BTC-USD", "比特幣／美元"),
    ]
    for index in range(0, len(symbols), 3):
        columns = st.columns(3)
        for column, (symbol, label) in zip(columns, symbols[index:index + 3]):
            with column:
                st.markdown(f"#### {label}")
                try:
                    quote = get_quote(symbol)
                except SourceUnavailable as exc:
                    st.warning(f"{symbol}：{exc}。")
                    continue
                st.metric("收盤值", f"{quote.price:,.2f}", f"{quote.change_pct:+.2f}%")
                st.caption(f"資料日期：{quote.date}｜Yahoo Finance：{symbol}")
                st.plotly_chart(gauge(quote.rsi, "14 日 RSI"), width="stretch", key=f"rsi-{symbol}")


render_dashboard()
st.caption("資料來源：臺灣期貨交易所及經 yfinance 取得的 Yahoo Finance 日線。不同市場有不同交易日與更新時點；請回原始來源核對。")
