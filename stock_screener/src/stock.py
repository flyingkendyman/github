import os
import requests
import time
import pandas as pd
import numpy as np

from bs4 import BeautifulSoup
from alpha_vantage.timeseries import TimeSeries
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar


def get_sp500_stocks_wiki(url=None):
    """
    Scapes a wikipedia web page to retrieve a table of S&P500 component stocks.
    Use this function if you require an updated table.

    args:
    ------
        url: (str) url leading to the wikipedia web page
    Return:
    ------
        df: (pd.DataFrame) a copy of the wikipedia table  
    """

    website_url = requests.get(url)
    soup = BeautifulSoup(website_url.text, 'lxml')
    my_table = soup.find('table', {'class': 'wikitable sortable'})
    my_table

    table_rows = my_table.find_all('tr')

    data = []
    for row in table_rows:
        data.append([t.text.strip() for t in row.find_all('td')])

    df = pd.DataFrame(data[1:], columns=['Ticker', 'Security', 'SEC_Filings',
                                         'GICS', 'GICS_Sub', 'HQ',
                                         'Date_First_Added', 'CIK', 'Founded'])

    return df


def get_sp500_stocks_file(file_path=None):
    """
    Reads a csv file containing the wikipedia S&P500 component stocks table

    args:
    ------
        file_path: (str) path leading to the csv file
    Return:
    ------
        df: (pd.DataFrame) a copy of the wikipedia table
    """

    df = pd.read_csv(file_path)

    return df


def filter_stocks_industry(df, ind_excld=[]):
    """
    Filters a dataframe based on the GICS industries

    args:
    ------
        df: (pd.DataFrame) a copy of the wikipedia table
        ind_excld: (list) GICS industries to be excluded
    Return:
    ------
        df_excld: (pd.DataFrame) filtered dataframe
    """

    df_excld = df[~df['GICS'].isin(ind_excld)]

    return df_excld


def get_stock_price(df_excld):
    """
    Retrieves the daily stock price from a dataframe of stocks and their
    respective tickers

    args:
    ------
        df_excld: (pd.DataFrame) filtered dataframe of stocks containing only
                  stocks from selected industries
    Return:
    ------
        info: (list) a complete history of stocks' pricing/volume information 
        symbols: (list) stock tickers
    """

    ts = TimeSeries(os.environ['ALPHA_VANTAGE_KEY'])

    info = []
    symbols = []
    counter = 0

    for t in df_excld['Ticker']:

        if counter % 5 == 0:
            time.sleep(65)

        i, m  = ts.get_daily(symbol=t, outputsize='full')
        info.append(i)
        symbols.append(m['2. Symbol'])
        counter += 1

    return info, symbols


def get_stock_price_df(info, symbols):
    """
    Converts pricing/volume information and the stocks symbols into
    a dataframe

    args:
    ------
        info: (list) a complete history of stocks' pricing/volume information 
        symbols: (list) stock tickers
    Return:
    ------
        df_full: (pd.DataFrame) consists of stock tickers their pricing/volume
                 information
    """

    df_l = []

    for num, i in enumerate(info):
        df = pd.DataFrame.from_dict(i, orient='index')
        df['Symbol'] = symbols[num]
        df_l.append(df)

    df_full = pd.concat(df_l)
    df_full = df_full.rename(columns={'1. open': 'Open',
                                      '2. high': 'High',
                                      '3. low': 'Low',
                                      '4. close': 'Close',
                                      '5. volume': 'Volume'})

    return df_full


def get_fed_holidays(start_date, end_date):
    """
    Retrieve a dataframe outlining the days that the US market is closed

    args:
    ------
        start_date: (str) start date for the period in focus
        end_date: (str) end date for the period in focus
    Return:
    ------
        df_holiday: (pd.DataFrame) returns the days that are US market holidays
    """

    dr = pd.date_range(start=start_date, end=end_date)
    df = pd.DataFrame()
    df['Date'] = dr

    cal = calendar()
    holidays = cal.holidays(start=dr.min(), end=dr.max())

    df['Holiday'] = df['Date'].isin(holidays)
    df_holiday = df[df['Holiday'] == True]

    return df_holiday


def get_rsi(prices, n=14):
    """
    Calculates the Relative Strength Index (RSI) for a stock
    Credits: sentdex - https://www.youtube.com/watch?v=4gGztYfp3ck

    args:
    ------
        prices: (list) prices for a stock
        n: (int) size of RSI look-back period
    Return:
    ------
        rsi: (float): momentum indicator that measures the magnitude of recent
                      price changes to evaluate overbought or oversold 
                      conditions

        https://www.investopedia.com/terms/r/rsi.asp
    """

    deltas = np.diff(prices)
    seed = deltas[:n+1]
    up = seed[seed >= 0].sum()/n
    down = -seed[seed < 0].sum()/n
    rs = up/down
    rsi = np.zeros_like(prices)
    rsi[:n] = 100. - 100./(1. + rs)

    for i in range(n, len(prices)):
        delta = deltas[i-1]

        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up*(n-1) + upval)/n
        down = (down*(n-1) + downval)/n

        rs = up/down
        rsi[i] = 100. - 100./(1.+rs)

    return rsi
