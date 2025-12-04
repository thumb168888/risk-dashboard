import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import datetime
import requests
import io

# --- 1. 頁面設定 ---
st.set_page_config(page_title="牧羊人風險戰情室", layout="wide", page_icon="📊")

# --- 2. CSS 優化 (深色模式) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #aaaaaa !important; }
    header {visibility: hidden;} 
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem; }
    /* 卡片樣式 */
    div.css-1r6slb0 { background-color: #1e222d; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 標題 ---
st.title("📊 牧羊人量化戰情室 (情緒標註版)")
st.caption(f"Last Update: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- 3. 籌碼爬蟲 (TAIFEX) ---
@st.cache_data(ttl=3600)
def get_taifex_chips():
    try:
        url_pc = "https://www.taifex.com.tw/cht/3/pcRatioDown"
        # 簡易邏輯：抓今天，若無則抓近30天最後一筆
        res_pc = requests.post(url_pc, data={'queryStartDate': datetime.datetime.now().strftime('%Y/%m/%d'), 
                                             'queryEndDate': datetime.datetime.now().strftime('%Y/%m/%d')})
        if res_pc.content == b'': 
             start = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y/%m/%d')
             end = datetime.datetime.now().strftime('%Y/%m/%d')
             res_pc = requests.post(url_pc, data={'queryStartDate': start, 'queryEndDate': end})

        df_pc = pd.read_csv(io.StringIO(res_pc.text), index_col=False)
        last_pc_ratio = float(df_pc.iloc[-1]['買賣權未平倉量比率%'])
        pc_date = df_pc.iloc[-1]['日期']
        
        return {
            "date": pc_date,
            "pc_ratio": last_pc_ratio,
            "status": "偏多 (支撐強)" if last_pc_ratio > 100 else "偏空 (壓力大)"
        }
    except: return None

# --- 4. 市場數據 (Yahoo) ---
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

# --- 5. 繪圖函數 (新增：左右標籤) ---
def plot_gauge(value, title, left_label, right_label, is_risk_asset=False, is_pc_ratio=False):
    
    # 1. 顏色邏輯
    if is_pc_ratio:
        bar_color = "#26a69a" if value > 100 else "#ef5350"
        min_v, max_v = 50, 150
    elif is_risk_asset:
        # 風險資產(股票)：右邊(>70)是貪婪/過熱(紅)，左邊(<30)是恐慌/超賣(綠)
        bar_color = "#ef5350" if value > 70 else "#26a69a" if value < 30 else "#b0bec5"
        min_v, max_v = 0, 100
    else:
        # 壓力源(VIX)：右邊(>60)是恐慌(紅)，左邊(<40)是安全(綠)
        bar_color = "#26a69a" if value < 40 else "#ef5350" if value > 60 else "#b0bec5"
        min_v, max_v = 0, 100

    # 2. 建立儀錶板
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

    # 3. 新增左右文字標籤 (Annotations)
    fig.update_layout(
        height=180, 
        margin={'t': 30, 'b': 20, 'l': 20, 'r': 20},
        paper_bgcolor='rgba(0,0,0,0)', 
        font={'color': "white"},
        annotations=[
            # 左邊標籤
            dict(x=0.2, y=0.1, text=left_label, showarrow=False, font=dict(size=12, color="#888")),
            # 右邊標籤
            dict(x=0.8, y=0.1, text=right_label, showarrow=False, font=dict(size=12, color="#888"))
        ]
    )
    return fig

# --- 6. 版面佈局 ---

# 籌碼面
st.subheader("♟️ 選擇權籌碼 (P/C Ratio)")
chips = get_taifex_chips()
if chips:
    col_chip1, col_chip2 = st.columns([1, 3])
    with col_chip1:
        st.metric(label=f"P/C Ratio ({chips['date']})", value=f"{chips['pc_ratio']}%", delta=chips['status'])
    with col_chip2:
        # P/C: 左邊=偏空，右邊=偏多
        st.plotly_chart(plot_gauge(chips['pc_ratio'], "P/C Ratio 動能", "偏空/壓力", "偏多/支撐", is_pc_ratio=True), use_container_width=True, config={'displayModeBar': False})
else:
    st.info("Loading Chips...")

st.markdown("---")

# 壓力源 (VIX類型：右邊是恐慌)
st.subheader("🔥 市場壓力源")
col1, col2, col3, col4 = st.columns(4)
stress_tickers = [("^VIX", "VIX 恐慌"), ("DX-Y.NYB", "美元指數"), ("^TNX", "美債10年"), ("JPY=X", "日圓")]

for col, (symbol, name) in zip([col1, col2, col3, col4], stress_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                # 壓力源：左邊=安全，右邊=恐慌
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 強度", "安全", "恐慌/壓力", is_risk_asset=False), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

# 風險資產 (股票類型：左邊是恐慌/超賣，右邊是貪婪/過熱)
st.subheader("📉 風險資產")
col5, col6 = st.columns(2)
asset_tickers = [("EWT", "台股 ETF"), ("BTC-USD", "比特幣")]

for col, (symbol, name) in zip([col5, col6], asset_tickers):
    with col:
        with st.container():
            data = get_market_data(symbol)
            if data:
                st.metric(label=name, value=f"{data['price']:.2f}", delta=f"{data['change']:.2f}%")
                # 資產：左邊=恐慌(超賣)，右邊=貪婪(過熱)
                st.plotly_chart(plot_gauge(data['rsi'], "RSI 動能", "恐慌 (超賣)", "貪婪 (過熱)", is_risk_asset=True), use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("Loading...")

# 自動刷新
if st.sidebar.button("🔄 重新整理"):
    st.cache_data.clear()
    st.rerun()
