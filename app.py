import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import datetime
import time
import pytz # 用來處理時區

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="牧羊人風險戰情室", 
    layout="wide", 
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# --- 2. CSS 樣式 (維持深色模式) ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    [data-testid="stMetricLabel"] {
        color: #aaaaaa !important;
    }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem; }
    
    /* 卡片背景 */
    div.css-1r6slb0 {
        background-color: #1e222d;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 時間處理 (轉換為台灣時間) ---
tw_tz = pytz.timezone('Asia/Taipei')
now_time = datetime.datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')

# --- 標題區 ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("📊 牧羊人量化戰情室 (Auto)")
with col_h2:
    st.caption(f"🕒 最後更新 (TW):")
    st.markdown(f"**{now_time}**")

# --- 4. 數據核心 (設定 ttl=60秒 保護機制) ---
# 注意：這裡設定 60 秒快取。即使頁面 5 秒刷一次，數據每 60 秒才會真正更新一次。
@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if len(data) < 15: return None
        
        current_price = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        change = (current_price - prev_close) / prev_close * 100
        
        # RSI 計算
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])
        
        return {
            "price": current_price,
            "change": change,
            "rsi": current_rsi,
            "history": data['Close']
        }
    except:
        return None

# --- 5. 儀錶板繪圖 ---
def plot_gauge(value, title, is_risk_asset=False):
    if is_risk_asset:
        bar_color = "#ff5252" if value > 70 else "#00e676" if value < 30 else "#b0bec5"
    else:
        bar_color = "#00e676" if value < 40 else "#ff5252" if value > 60 else "#b0bec5"

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number = {'suffix': "", 'font': {'size': 24, 'color': "white"}},
        title = {'text': title, 'font': {'size': 14, 'color': "#aaaaaa"}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#555"},
            'bar': {'color': bar_color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
            'steps': [{'range': [0, 100], 'color': '#131722'}],
            'threshold': {'line': {'color': "white", 'width': 2}, 'thickness': 0.75, 'value': value}
        }
    ))
    fig.update_layout(
        height=160, 
        margin={'t': 30, 'b': 10, 'l': 30, 'r': 30},
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "white"}
    )
    return fig

# --- 6. 內容佈局 ---

# 壓力源
st.subheader("🔥 市場壓力源")
col1, col2, col3, col4 = st.columns(4)
stress_tickers = [("^VIX", "VIX 恐慌"), ("DX-Y.NYB", "美元指數"), ("^TNX", "美債10年"), ("JPY=X", "日圓")]

for col, (symbol, name) in zip([col1, col2, col3, col4], stress_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 強度"), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

st.markdown("---")

# 風險資產
st.subheader("📉 風險資產")
col5, col6 = st.columns(2)
asset_tickers = [("EWT", "台股 ETF"), ("BTC-USD", "比特幣")]

for col, (symbol, name) in zip([col5, col6], asset_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 動能", True), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

# --- 7. 自動刷新邏輯 (放在最後面) ---
st.sidebar.title("⚙️ 設定")
st.sidebar.write("數據來源: Yahoo Finance (快取60秒)")

# 倒數計時器容器
placeholder = st.sidebar.empty()
refresh_time = 5 # 設定幾秒刷新一次

# 顯示倒數條
for i in range(refresh_time, 0, -1):
    placeholder.progress(i / refresh_time, text=f"下一次更新: {i} 秒後")
    time.sleep(1) # 等待一秒

# 時間到，執行刷新
st.rerun()
