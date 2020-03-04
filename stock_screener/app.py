import os
import sys
import time
import logging
import slack
import ssl as ssl_lib
import certifi
import datetime
import numpy as np
import pandas as pd

from flask import Flask
from slackeventsapi import SlackEventAdapter

from src.stock import get_sp500_stocks_wiki, get_sp500_stocks_file, \
                      filter_stocks_industry, get_stock_price, \
                      get_stock_price_df, get_fed_holidays, get_rsi


# Initialize a Flask app to host the events adapter
# app = Flask(__name__)
# slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)

# Initialize a Web API client
slack_web_client = slack.WebClient(token=os.environ['SLACK_BOT_TOKEN'])

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class Smartie:
    """App that sends stock analysis results for the day."""

    def __init__(self, channel):
        self.channel = channel
        self.username = "smartie"
        self.reaction_task_completed = False
        self.pin_task_completed = False
        self.DIVIDER_BLOCK = {"type": "divider"}

    def get_stocks_rsi(self, rsi_n=14, stocks_n=100,
                       file_path='./data/sp500_stocks.csv',
                       ind_excld=['Health Care', 'Utilities', 'Energy']):
        """
        Calculates the Relative Strength Index (RSI) for a group of stocks

        args:
        ------
            rsi_n: (list) size of rsi look-back period
            stocks_n: (int) number of stocks to retrieve the rsi for
            file_path (str): path leading to csv file of S&P500 component 
                                stocks
            ind_excld: (list) GICS Sector industries to be excluded
        Return:
        ------
            df_rsi: (pd.DataFrame) returns the rsi reading for the list of
                        stocks and whether the 30/70 levels have been breached
        """

        sp500_stocks_df = get_sp500_stocks_file(file_path=file_path)

        sp500_stocks_df_excld = filter_stocks_industry(sp500_stocks_df,
                                                       ind_excld=ind_excld)

        sp500_stocks_df_excld = sp500_stocks_df_excld.head(stocks_n)

        info, symbols = get_stock_price(sp500_stocks_df_excld)

        sp500_stocks_price_df = get_stock_price_df(info, symbols)

        symbols = sp500_stocks_price_df['Symbol'].unique()

        rsi_l = []
        status_l = []
        for s in symbols:
            s_df = sp500_stocks_price_df[sp500_stocks_price_df['Symbol'] == s]
            closep = np.array(s_df['Close'].tolist())
            closep = closep.astype(np.float)
            rsi = get_rsi(closep, n=rsi_n)

            if rsi[-1] >=70:
                status = 'Above 70'
            elif rsi[-1] <= 30:
                status = 'Below 30'
            else:
                status = 'Normal'

            rsi_l.append(round(rsi[-1], 1))
            status_l.append(status)

        df_rsi = pd.DataFrame(zip(symbols, rsi_l, status_l),
                              columns=['Symbols', 'RSI', 'Status'])

        return df_rsi

    def get_rsi_string(self, df_rsi, head_n=20, tail_n=20):
        """
        Converts the RSI readings into strings to be displayed in Slack

        args:
        ------
            df_rsi: (pd.DataFrame) the rsi readings for a list of 
                    stocks and whether the 30/70 levels have been breached
            head_n: (int) number of top ranked stocks (based on rsi) reading
                    to be displayed in Slack
            tail_n: (int) number of bottom ranked stocks (based on rsi) reading 
                    to be displayed in Slack
        Return:
        ------
            top_str: (str) concatenated string for top ranked stocks' rsi
                        reading
            btm_str: (str) concatenated string for bottom ranked stocks' rsi
                        reading
        """

        df_rsi = df_rsi.sort_values('RSI',ascending=False)

        df_top = df_rsi.head(head_n)
        df_btm = df_rsi.tail(tail_n)

        top_symbols = df_top['Symbols'].tolist()
        btm_symbols = df_btm['Symbols'].tolist()

        top_rsi = df_top['RSI'].tolist()
        btm_rsi = df_btm['RSI'].tolist()

        top_l = list(zip(top_symbols, top_rsi))
        btm_l = list(zip(btm_symbols, btm_rsi))

        top_str = ""
        for el in top_l:
            top_str = top_str + str(el[0]) + " " + str(el[1]) + "\n"

        btm_str = ""
        for el in btm_l:
            btm_str = btm_str + str(el[0]) + " " + str(el[1]) + "\n"

        return top_str, btm_str

    def _get_text_block(self, string):
        """
        Helper function for get_message_payload_stock method.
        Used to convert a string into a slack formatted text block.

        args:
        ------
            string: (str) concatenated string for the top or bottom ranked
                    stocks' rsi reading
        Return:
        ------
            dictionary containing the correctly formatted text block to be 
            displayed in slack
        """

        return {"type": "section", "text": {"type": "mrkdwn", "text": string}}

    def get_message_payload_stock(self, top_str, btm_str):
        """
        Used to create a message payload to send stock rsi readings

        args:
        ------
            top_str: (str) concatenated string for the top ranked stocks'
                        rsi readings
            bottom_str: (str) concatenated string for the bottom ranked
                        stocks' rsi readings
        Return:
        ------
            dictionary containing payload (stock rsi readings) to be sent
            using Slack's API
        """

        return {
            "channel": self.channel,
            "username": self.username,
            "blocks": [
                self._get_text_block(top_str),
                self.DIVIDER_BLOCK,
                self._get_text_block(btm_str)
            ],
        }

    def get_message_payload(self, string):
        """
        Used to create a message payload to send simple text messages

        args:
        ------
            string: (str) string to be sent using Slack's API
        Return:
        ------
            dictionary containing payload (simple text messages) to be sent
            using Slack's API.
        """

        return {
            "channel": self.channel,
            "username": self.username,
            "text": string
        }


def main():
    s = Smartie(os.environ['CHANNEL_ID'])

    logger.info('Getting fed holidays')
    range_start_date = '2020-01-01'
    range_end_date = '2020-12-31'
    fed_holiday = get_fed_holidays(start_date=range_start_date, end_date=range_end_date)

    logger.info('Getting payload')
    if str(datetime.datetime.now().date()) in fed_holiday:
        logger.info('It is a Holiday')
        message = s.get_message_payload('Market closed, US Federal holiday')
    else:
        logger.info('It is not a Holiday')
        df_rsi = s.get_stocks_rsi(rsi_n=14, stocks_n=10)
        top_str, btm_str = s.get_rsi_string(df_rsi, head_n=5, tail_n=5)
        message = s.get_message_payload_stock(top_str, btm_str)

    logger.info('Posting on Slack')
    response = slack_web_client.chat_postMessage(**message)


if __name__ == "__main__":
    logger.addHandler(logging.StreamHandler(sys.stdout))
    main()
