import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="牧羊人風險戰情室", layout="wide", page_icon="📊")

# --- CSS 優化 (隱藏預設選單，讓畫面更像 App) ---
st.markdown("""
    <style>
    .reportview-container { margin-top: -2em; }
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 標題 ---
st.title("📊 牧羊人量化風險戰情室 (Python版)")
st.caption("Deployment: Streamlit Cloud | Data: Yahoo Finance (Real-time)")

# --- 核心函數：取得數據並計算分數 ---
# 這裡我們可以寫自己的邏輯！不必再依賴 TradingView 的指針
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(data) < 2:
            return None
        
        # 取得最新價格與漲跌
        current_price = data['Close'].iloc[-1].item()
        prev_close = data['Close'].iloc[-2].item()
        change = (current_price - prev_close) / prev_close * 100
        
        # 計算 RSI (14) 作為量化指標
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1].item()
        
        return {
            "price": current_price,
            "change": change,
            "rsi": rsi,
            "history": data['Close']
        }
    except Exception as e:
        return None

# --- 繪製儀錶板 (Gauge) 的函數 ---
def plot_gauge(value, title, min_val=0, max_val=100, is_risk_asset=False):
    # 如果是風險資產(如台股)，RSI低(30)是超賣(買點)，RSI高(70)是超買(賣點)
    # 如果是避險資產(如VIX)，數值越高越危險
    
    if is_risk_asset:
        # 資產類：低分(左)危險，高分(右)強勢
        colors = [
            (0.3, "red"), (0.7, "gray"), (1.0, "green")
        ]
        current_color = "red" if value < 30 else "green" if value > 70 else "white"
    else:
        # 壓力類(VIX)：低分(左)安全，高分(右)危險
        colors = [
            (0.3, "green"), (0.7, "gray"), (1.0, "red")
        ]
        current_color = "green" if value < 20 else "red" if value > 30 else "white"

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        title = {'text': title, 'font': {'size': 20}},
        number = {'font': {'color': current_color}},
        gauge = {
            'axis': {'range': [min_val, max_val], 'tickwidth': 1},
            'bar': {'color': current_color}, # 指針顏色
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [min_val, min_val+(max_val-min_val)*0.3], 'color': "#1e222d"},
                {'range': [min_val+(max_val-min_val)*0.3, min_val+(max_val-min_val)*0.7], 'color': "#131722"},
                {'range': [min_val+(max_val-min_val)*0.7, max_val], 'color': "#1e222d"}
            ],
        }
    ))
    fig.update_layout(
        height=250, 
        margin={'t':30,'b':10,'l':20,'r':20},
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': "white"}
    )
    return fig

# --- 主畫面佈局 ---
# 定義我們要監控的商品 (代碼使用 Yahoo Finance)
tickers = {
    "VIX 恐慌指數": {"symbol": "^VIX", "type": "stress"},
    "美元指數": {"symbol": "DX-Y.NYB", "type": "stress"},
    "10年美債殖利": {"symbol": "^TNX", "type": "stress"},
    "台股 (EWT)": {"symbol": "EWT", "type": "asset"},
    "日圓 (JPY=X)": {"symbol": "JPY=X", "type": "stress"}, # 日圓匯率
    "比特幣": {"symbol": "BTC-USD", "type": "asset"},
}

# 建立 3欄 x 2列 的網格
cols = st.columns(3) # 第一排
cols2 = st.columns(3) # 第二排
all_cols = cols + cols2

# 迴圈處理每個商品
for i, (name, info) in enumerate(tickers.items()):
    with all_cols[i]:
        # 顯示載入中...
        with st.spinner(f"Loading {name}..."):
            data = get_market_data(info["symbol"])
        
        if data:
            # 1. 顯示大數字 (Metric)
            st.metric(
                label=name,
                value=f"{data['price']:.2f}",
                delta=f"{data['change']:.2f}%",
                delta_color="inverse" if info["type"] == "stress" else "normal" 
                # inverse: VIX漲顯示紅色(壞事)，normal: 台股漲顯示綠色(好事)
            )
            
            # 2. 顯示儀錶板 (RSI 作為量化指針)
            # 這裡我們用 RSI (0-100) 來當作「溫度計」
            # 當然，你也可以自己寫更複雜的 Python 邏輯來計算這個分數
            fig = plot_gauge(
                data['rsi'], 
                f"RSI 強度: {data['rsi']:.1f}", 
                is_risk_asset=(info["type"] == "asset")
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. 簡單的小線圖
            st.line_chart(data['history'], height=100)
            
        else:
            st.error(f"無法讀取 {name}")

# --- 側邊欄：進階功能 ---
st.sidebar.header("⚙️ 控制台")
st.sidebar.info("這是 Python 版本，可以在後端執行複雜運算。")
if st.sidebar.button("重新整理數據"):
    st.rerun()

# 這裡示範 Python 才能做的事：條件判斷
st.sidebar.header("🤖 風險快篩")
vix_data = get_market_data("^VIX")
if vix_data and vix_data['price'] > 20:
    st.sidebar.error(f"⚠️ 警告：VIX 目前 {vix_data['price']:.2f}，市場情緒恐慌！")
else:
    st.sidebar.success("✅ 目前 VIX 處於安全水位。")