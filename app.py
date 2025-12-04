import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import datetime
import requests
import io
import time
import pytz

# --- 1. 頁面設定 ---
st.set_page_config(page_title="牧羊人風險戰情室", layout="wide", page_icon="📊")

# --- 2. CSS 優化 ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #aaaaaa !important; }
    header {visibility: hidden;} 
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem; }
    div.css-1r6slb0 { background-color: #1e222d; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 時間處理 (顯示台灣時間) ---
tw = pytz.timezone('Asia/Taipei')
now_time = datetime.datetime.now(tw).strftime('%Y-%m-%d %H:%M:%S')

# --- 標題區 ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("📊 牧羊人量化戰情室")
with col_h2:
    st.caption("🕒 最後更新 (Taiwan Time):")
    st.subheader(f"{now_time}")

# --- 4. [核心修正] 智能籌碼爬蟲 (修正日期 11/19 問題) ---
@st.cache_data(ttl=3600)
def get_taifex_chips():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    url_pc = "https://www.taifex.com.tw/cht/3/pcRatioDown"
    
    # 策略：從今天開始，一天一天往回找，最多找 7 天
    # 這樣可以確保抓到的是「離現在最近」的一筆有效資料 (例如昨天或上週五)
    for i in range(7):
        target_date = datetime.datetime.now(tw) - datetime.timedelta(days=i)
        date_str = target_date.strftime('%Y/%m/%d')
        
        payload = {
            'queryStartDate': date_str,
            'queryEndDate': date_str # 只查那一天，精準度最高
        }
        
        try:
            res = requests.post(url_pc, data=payload, headers=headers)
            
            # 解碼嘗試 (防止 Big5 亂碼)
            try:
                df = pd.read_csv(io.StringIO(res.text), index_col=False)
            except:
                df = pd.read_csv(io.BytesIO(res.content), encoding='big5', index_col=False)
            
            # 如果這一天有資料
            if not df.empty:
                row = df.iloc[-1]
                ratio = float(row['買賣權未平倉量比率%'])
                return {
                    "date": row['日期'], # 抓到的正確日期
                    "pc_ratio": ratio,
                    "status": "偏多 (支撐強)" if ratio > 100 else "偏空 (壓力大)"
                }
        except:
            continue # 這天失敗，找前一天
            
    return None

# --- 5. 市場數據 (Yahoo) ---
@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        if len(data) < 15: return None
        
        current_price = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        change = (current_price - prev_close) / prev_close * 100
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])
        
        return {"price": current_price, "change": change, "rsi": current_rsi, "history": data['Close']}
    except: return None

# --- 6. 繪圖函數 ---
def plot_gauge(value, title, left_label, right_label, is_risk_asset=False, is_pc_ratio=False):
    if is_pc_ratio:
        bar_color = "#26a69a" if value > 100 else "#ef5350"
        min_v, max_v = 50, 150
    elif is_risk_asset:
        bar_color = "#ef5350" if value > 70 else "#26a69a" if value < 30 else "#b0bec5"
        min_v, max_v = 0, 100
    else:
        bar_color = "#26a69a" if value < 40 else "#ef5350" if value > 60 else "#b0bec5"
        min_v, max_v = 0, 100

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number = {'suffix': "", 'font': {'size': 24, 'color': "white"}},
        title = {'text': title, 'font': {'size': 14, 'color': "#ccc"}},
        gauge = {
            'axis': {'range': [min_v, max_v], 'tickwidth': 1, 'tickcolor': "#333"},
            'bar': {'color': bar_color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
            'steps': [{'range': [min_v, max_v], 'color': '#131722'}],
            'threshold': {'line': {'color': "white", 'width': 2}, 'thickness': 0.75, 'value': value}
        }
    ))
    fig.update_layout(
        height=180, margin={'t': 30, 'b': 20, 'l': 20, 'r': 20},
        paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"},
        annotations=[
            dict(x=0.2, y=0.1, text=left_label, showarrow=False, font=dict(size=12, color="#888")),
            dict(x=0.8, y=0.1, text=right_label, showarrow=False, font=dict(size=12, color="#888"))
        ]
    )
    return fig

# --- 7. 版面佈局 ---

# A. 籌碼面
st.subheader("♟️ 選擇權籌碼 (P/C Ratio)")
chips = get_taifex_chips()
if chips:
    col_chip1, col_chip2 = st.columns([1, 3])
    with col_chip1:
        st.metric(label=f"日期: {chips['date']}", value=f"{chips['pc_ratio']}%", delta=chips['status'])
    with col_chip2:
        st.plotly_chart(plot_gauge(chips['pc_ratio'], "P/C Ratio 動能", "偏空/壓力", "偏多/支撐", is_pc_ratio=True), use_container_width=True, config={'displayModeBar': False})
else:
    st.info("📊 正在讀取期交所數據...")

st.markdown("---")

# B. 壓力源
st.subheader("🔥 市場壓力源")
col1, col2, col3, col4 = st.columns(4)
stress_tickers = [("^VIX", "VIX 恐慌"), ("DX-Y.NYB", "美元指數"), ("^TNX", "美債10年"), ("JPY=X", "日圓")]

for col, (symbol, name) in zip([col1, col2, col3, col4], stress_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 強度", "安全", "恐慌/壓力", is_risk_asset=False), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

# C. 風險資產 (修正：這裡只會有一個迴圈，不會重複了)
st.subheader("📉 風險資產")
col5, col6 = st.columns(2)
asset_tickers = [("EWT", "台股 ETF"), ("BTC-USD", "比特幣")]

for col, (symbol, name) in zip([col5, col6], asset_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 動能", "恐慌 (超賣)", "貪婪 (過熱)", is_risk_asset=True), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

# --- 8. 自動刷新 ---
st.sidebar.title("⚙️ 系統控制")
auto_refresh = st.sidebar.checkbox("啟用自動刷新 (每60秒)", value=True)

if st.sidebar.button("🔄 立即重新整理"):
    st.cache_data.clear()
    st.rerun()

if auto_refresh:
    timer_placeholder = st.sidebar.empty()
    for i in range(60, 0, -1):
        timer_placeholder.progress(i / 60, text=f"⏳ 下次更新: {i} 秒")
        time.sleep(1)
    st.cache_data.clear()
    st.rerun()
