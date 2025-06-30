import yfinance as yf
import pandas as pd


def fetch_price_data(ticker, period="1y", interval="1d"):
    """Fetch historical OHLCV data for a given ticker."""
    data = yf.download(ticker, group_by='Ticker', period=period, interval=interval)
    data.reset_index(inplace=True)
    return data


def load_sp500_table():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    df.rename(columns={"Symbol": "Ticker"}, inplace=True)
    return df[["Ticker", "Security", "GICS Sector", "GICS Sub-Industry"]]


