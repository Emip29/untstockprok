import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

from alpha_vantage.fundamentaldata import FundamentalData
from stocknews import StockNews

st.set_page_config(layout="wide")
st.title("📈 Stock Dashboard (Robust Charts)")

# ---------------- Sidebar ----------------
ticker = st.sidebar.text_input("Ticker (e.g. AAPL)").upper().strip()
start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")

# helper: find datetime column or make one
def ensure_datetime_column(df: pd.DataFrame) -> pd.DataFrame:
    # If any column is datetime-like, use it
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df = df.rename(columns={col: "Date"}) if col != "Date" else df
            return df
    # else, if index is a DatetimeIndex, reset index to create Date
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        if df.columns[0] != "Date":
            df = df.rename(columns={df.columns[0]: "Date"})
        # ensure it's datetime
        df["Date"] = pd.to_datetime(df["Date"])
        return df
    # last resort: try to parse first column as datetime
    try:
        df = df.reset_index()
        df = df.rename(columns={df.columns[0]: "Date"})
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        return df
    except Exception:
        return df

# ---------------- Main logic ----------------
if not ticker:
    st.info("Enter a ticker symbol in the sidebar to load data.")
    st.stop()

# download data
try:
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
except Exception as e:
    st.error("Error downloading data from yfinance.")
    st.exception(e)
    st.stop()

if data is None or data.empty:
    st.error("No price data returned for this ticker & date range. Try widening the range or using a different ticker.")
    st.write("Returned columns:", [] if data is None else list(data.columns))
    st.stop()

# choose price column
if "Adj Close" in data.columns:
    price_col = "Adj Close"
elif "AdjClose" in data.columns:
    price_col = "AdjClose"
elif "Close" in data.columns:
    price_col = "Close"
else:
    st.error("No usable price column found in the returned data.")
    st.write("Returned columns:", list(data.columns))
    st.stop()

# prepare dataframe for plotting
df_plot = ensure_datetime_column(data.copy())

# If ensure_datetime_column didn't create "Date", create from index
if "Date" not in df_plot.columns:
    df_plot = df_plot.reset_index()
    df_plot = df_plot.rename(columns={df_plot.columns[0]: "Date"})
df_plot["Date"] = pd.to_datetime(df_plot["Date"], errors="coerce")

# Ensure price and volume exist and are numeric
if price_col not in df_plot.columns:
    st.error(f"Price column {price_col} not found in prepared data.")
    st.write("Prepared columns:", list(df_plot.columns))
    st.stop()

# convert price to numeric, drop NaNs
df_plot[price_col] = pd.to_numeric(df_plot[price_col], errors="coerce")
if "Volume" in df_plot.columns:
    df_plot["Volume"] = pd.to_numeric(df_plot["Volume"], errors="coerce")
else:
    df_plot["Volume"] = np.nan  # keep column for plotting if missing

# drop rows where Date or price is NaN
df_plot = df_plot.dropna(subset=["Date", price_col])

# if not enough points, show friendly message
if df_plot.shape[0] < 2:
    st.warning("Not enough valid price points to draw a chart. Try a different date range or ticker.")
    st.write("Preview of returned data:")
    st.dataframe(df_plot.head(10))
    st.stop()

# Sort by date to be safe
df_plot = df_plot.sort_values("Date")

# build figure with graph_objects: price line + volume bars (secondary y)
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df_plot["Date"],
        y=df_plot[price_col],
        mode="lines",
        name=price_col,
        line=dict(width=2),
        yaxis="y1",
        hovertemplate="%{x|%Y-%m-%d}: %{y:.2f}<extra></extra>",
    )
)

# add volume as bar on secondary y if available (not all tickers)
if df_plot["Volume"].notna().any():
    fig.add_trace(
        go.Bar(
            x=df_plot["Date"],
            y=df_plot["Volume"],
            name="Volume",
            marker=dict(opacity=0.4),
            yaxis="y2",
            hovertemplate="%{x|%Y-%m-%d}: %{y:.0f}<extra></extra>",
        )
    )

fig.update_layout(
    title=f"{ticker} — {price_col} ({start_date} → {end_date})",
    xaxis=dict(title="Date", type="date", rangeslider=dict(visible=True)),
    yaxis=dict(title=f"Price ({price_col})", side="left", showgrid=True),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=20, t=80, b=60),
    template="plotly_white",
)

# add secondary y axis for volume
if df_plot["Volume"].notna().any():
    fig.update_layout(
        yaxis2=dict(
            title="Volume",
            overlaying="y",
            side="right",
            showgrid=False,
            position=0.98,
        )
    )

st.plotly_chart(fig, use_container_width=True)

# ---------------- Tabs for the rest of your app ----------------
pricing_data, fundamental_data, news_tab = st.tabs(
    ["📊 Pricing Data", "📚 Fundamental Data", "📰 Top News"]
)

with pricing_data:
    st.header("Price Movements & Stats")
    data2 = data.copy()

    # normalize price for calculations (ensure numeric)
    if price_col not in data2.columns:
        st.error("Price column missing from raw data.")
        st.stop()
    data2[price_col] = pd.to_numeric(data2[price_col], errors="coerce")
    data2["% Change"] = data2[price_col].pct_change()
    data2 = data2.dropna(subset=[price_col, "% Change"])

    st.dataframe(data2.tail(50))

    annual_return = data2["% Change"].mean() * 252 * 100
    st.write("Annual Return:", f"{annual_return:.2f}%")

    stdev = np.std(data2["% Change"]) * np.sqrt(252) * 100
    st.write("Standard Deviation:", f"{stdev:.2f}%")

    # optional moving averages
    st.subheader("Moving Averages")
    ma_df = data2[[price_col]].copy()
    ma_df["MA20"] = ma_df[price_col].rolling(20).mean()
    ma_df["MA50"] = ma_df[price_col].rolling(50).mean()
    ma_df["MA200"] = ma_df[price_col].rolling(200).mean()
    st.line_chart(ma_df.tail(200))

with fundamental_data:
    st.header("Fundamental Data (Alpha Vantage)")
    key = "XCWQ3FD4VCKVL1NA"
    try:
        fd = FundamentalData(key, output_format="pandas")
        balance_sheet = fd.get_balance_sheet_annual(ticker)[0]
        bs = balance_sheet.T[2:]
        bs.columns = list(balance_sheet.T.iloc[0])
        st.subheader("Balance Sheet")
        st.write(bs)
        income_statement = fd.get_income_statement_annual(ticker)[0]
        is1 = income_statement.T[2:]
        is1.columns = list(income_statement.T.iloc[0])
        st.subheader("Income Statement")
        st.write(is1)
        cash_flow = fd.get_cash_flow_annual(ticker)[0]
        cf = cash_flow.T[2:]
        cf.columns = list(cash_flow.T.iloc[0])
        st.subheader("Cash Flow Statement")
        st.write(cf)
    except Exception as e:
        st.error("Could not load fundamental data. Alpha Vantage may be rate-limiting or the ticker is unsupported.")
        st.write(e)

with news_tab:
    st.header(f"Top News for {ticker}")
    try:
        sn = StockNews(ticker, save_news=False)
        df_news = sn.read_rss()
        n = min(10, len(df_news))
        for i in range(n):
            st.subheader(f"News {i+1}")
            st.write("Published:", df_news["published"][i])
            st.write("Title:", df_news["title"][i])
            st.write("Summary:", df_news["summary"][i])
            st.write("Title Sentiment:", df_news["sentiment_title"][i])
            st.write("Summary Sentiment:", df_news["sentiment_summary"][i])
            st.markdown("---")
    except Exception as e:
        st.error("Could not load news. The feed may be rate-limited.")
        st.write(e)
