import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

from alpha_vantage.fundamentaldata import FundamentalData
from stocknews import StockNews

st.title("Stock Dashboard")

ticker = st.sidebar.text_input("Ticker", value="AAPL")
start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")

try:
    data = yf.download(ticker, start=start_date, end=end_date)

except Exception as e:
    st.error(f"Error downloading data: {e}")
    st.stop()

if data.empty:
    st.error("No price data returned. Try another ticker or date range.")
    st.stop()

if isinstance(data.columns, pd.MultiIndex):
    data.columns = ["_".join([str(c) for c in col if c]) for col in data.columns]

possible_cols = ["Adj Close", "AdjClose", "Close"]

flat_matches = [c for c in data.columns if any(pc in c for pc in possible_cols)]

if flat_matches:
    price_col = flat_matches[0]
elif "Close" in data.columns:
    price_col = "Close"
else:
    st.error("Could not identify a price column.\nColumns returned:")
    st.write(list(data.columns))
    st.stop()

price_series = data[price_col]

if isinstance(price_series, pd.DataFrame):
    num_cols = price_series.select_dtypes(include="number").columns
    if len(num_cols) == 0:
        st.error("Price column is not numeric.")
        st.write(price_series.head())
        st.stop()
    price_series = price_series[num_cols[0]]

price_series = pd.to_numeric(price_series, errors="coerce")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=data.index,
    y=price_series,
    mode="lines",
    name=price_col
))
fig.update_layout(
    title=f"{ticker} Price Chart",
    xaxis_title="Date",
    yaxis_title="Price"
)

st.plotly_chart(fig)

pricing_tab, fundamental_tab, news_tab = st.tabs(
    ["Pricing Data", "Fundamental Data", "Top 10 News"]
)

with pricing_tab:
    st.header("Price Movements")

    df_price = pd.DataFrame()
    df_price["Price"] = price_series
    df_price["% Change"] = df_price["Price"].pct_change()
    df_price.dropna(inplace=True)

    st.write(df_price)

    annual_return = df_price["% Change"].mean() * 252 * 100
    st.write(f"Annual Return: {annual_return:.2f}%")

    stdev = df_price["% Change"].std() * np.sqrt(252)
    st.write(f"Standard Deviation: {stdev * 100:.2f}%")


with fundamental_tab:
    st.header("Fundamental Data")

    try:
        key = "H05KEVYJHB1ZVGY6"
        fd = FundamentalData(key, output_format="pandas")
        st.subheader("Balance Sheet (Annual)")
        bs = fd.get_balance_sheet_annual(ticker)[0]
        bs = bs.T[2:]
        bs.columns = list(fd.get_balance_sheet_annual(ticker)[0].T.iloc[0])
        st.write(bs)
        st.subheader("Income Statement (Annual)")
        inc = fd.get_income_statement_annual(ticker)[0]
        inc2 = inc.T[2:]
        inc2.columns = list(inc.T.iloc[0])
        st.write(inc2)
        st.subheader("Cash Flow Statement (Annual)")
        cf = fd.get_cash_flow_annual(ticker)[0]
        cf2 = cf.T[2:]
        cf2.columns = list(cf.T.iloc[0])
        st.write(cf2)

    except Exception as e:
        st.error(f"Error loading fundamental data: {e}")


with news_tab:
    st.header(f"Latest News for {ticker}")

    try:
        sn = StockNews(ticker, save_news=False)
        df_news = sn.read_rss()

        for i in range(min(10, len(df_news))):
            st.subheader(f"News {i+1}")
            st.write(df_news["published"][i])
            st.write(df_news["title"][i])
            st.write(df_news["summary"][i])

            title_sent = df_news["sentiment_title"][i]
            summary_sent = df_news["sentiment_summary"][i]

            st.write(f"Title Sentiment: {title_sent}")
            st.write(f"Summary Sentiment: {summary_sent}")

    except Exception as e:
        st.error(f"News could not be loaded: {e}")
