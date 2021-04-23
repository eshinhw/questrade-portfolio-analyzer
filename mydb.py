import os
import json
import requests
import sqlalchemy
import pandas as pd
import datetime as dt
import yfinance as yf
import mysql.connector
import pandas_datareader.data as web

# https://financialmodelingprep.com/developer/docs

with open('./credentials/pi_db_server.txt', 'r') as fp:
    secret = fp.readlines()
    host_ip = secret[0].rstrip('\n')
    user_id = secret[1].rstrip('\n')
    pw = secret[2]
    fp.close()

FMP_API_KEYS = open("./credentials/fmp_api.txt", 'r').read()
DIV_TBN = 'Annual_Dividends'
PRICE_TBN = 'Price'

class db_master:

    def __init__(self, symbol):
        self.key = FMP_API_KEYS
        self.db = mysql.connector.connect(
            host = host_ip,
            user = user_id,
            passwd = pw
        )
        self.symbol = symbol.upper()
        self.mycursor = self.db.cursor()
        self.mycursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.symbol}")
        self.db.commit()

        creds = {'usr': user_id,
                'pwd': pw,
                'hst': host_ip,
                'prt': 3306,
                'dbn': self.symbol}
        connstr = 'mysql+mysqlconnector://{usr}:{pwd}@{hst}:{prt}/{dbn}'
        self.engine = sqlalchemy.create_engine(connstr.format(**creds))

    def income_statement(self, period: str, limit: int):
        if period.upper() == 'Y':
            annual = requests.get(f"https://financialmodelingprep.com/api/v3/income-statement/{self.symbol}?limit={limit}&apikey={self.key}").json()
            return annual

            #annual = requests.get(f'https://financialmodelingprep.com/api/v3/ratios-ttm/{symbol}?apikey={key}')
        if period.upper() == 'Q':
            quarter = requests.get(f"https://financialmodelingprep.com/api/v3/income-statement/{self.symbol}?period=quarter&limit={limit}&apikey={self.key}").json()
            return quarter

        return None

    def financial_ratios(self, limit: int):
        self.mycursor.execute(f"USE {self.symbol}")
        self.mycursor.execute("CREATE TABLE IF NOT EXISTS Financial_Ratios (Date VARCHAR(100) NOT NULL, Ratio VARCHAR(255) NOT NULL, Value float)")
        self.db.commit()

        financial_growth = requests.get(f'https://financialmodelingprep.com/api/v3/financial-growth/{self.symbol}?period=quarter&limit={limit}&apikey={self.key}').json()[0]
        financial_ratios = requests.get(f'https://financialmodelingprep.com/api/v3/ratios-ttm/{self.symbol}?apikey={self.key}').json()[0]

        vals = []
        date = financial_growth.get('date')

        for k in financial_growth.keys():
            if k in ('symbol', 'period', 'date'):
                continue
            else:
                val = financial_growth.get(k)
                vals.append((date,k,val))

        for k in financial_ratios.keys():
            val = financial_ratios.get(k)
            vals.append((date,k,val))

        self.mycursor.executemany("INSERT INTO Financial_Ratios (Date, Ratio, Value) VALUES (%s,%s,%s)", vals)
        self.db.commit()

    def dividend_history_export_to_sql(self):
        try:
            data = yf.Ticker(self.symbol).history(period='max')
        except:
            return None

        div = data[data['Dividends'] > 0.01]
        first_year = div.index[0].year
        last_year = div.index[-1].year
        data = {'Year': [], 'Dividends': []}
        for year in range(first_year,last_year):
            div_sum = div[div.index.year == year]['Dividends'].sum()
            data['Year'].append(year)
            data['Dividends'].append(div_sum)
        annual_div = pd.DataFrame(data)
        self.mycursor.execute(f"USE {self.symbol}")
        self.mycursor.execute(f"CREATE TABLE IF NOT EXISTS {DIV_TBN} (Year VARCHAR(20), Dividends float)")
        self.db.commit()

        annual_div.to_sql(name=DIV_TBN, con=self.engine, if_exists='replace', index=False)

    def dividend_history_import_to_df(self):
        self.mycursor.execute(f"USE {self.symbol}")
        self.mycursor.execute(f"SELECT * FROM {DIV_TBN}")

        df = pd.DataFrame(self.mycursor.fetchall(), columns=['Year', 'Dividends'])
        df.set_index('Year',inplace=True)
        return df

    def price_history_export_to_sql(self, start_date=None, end_date=None):
        try:
            prices = web.DataReader(self.symbol, 'yahoo', start_date, end_date)
        except:
            return None

        prices.reset_index(inplace=True)
        self.mycursor.execute(f"USE {self.symbol}")
        self.mycursor.execute(f"CREATE TABLE IF NOT EXISTS {PRICE_TBN} (Date datetime, High float, Low float, Open float, Close float, Volume float, Adj_Close float)")
        self.db.commit()

        prices.to_sql(name=PRICE_TBN, con=self.engine, if_exists='replace', index=False)

    def price_history_import_to_df(self, start_date=None, end_date=None):
        self.mycursor.execute(f"USE {self.symbol}")
        self.mycursor.execute(f"SELECT * FROM {PRICE_TBN}")
        df = pd.DataFrame(self.mycursor.fetchall(), columns=['Date', 'High', 'Low', 'Open', 'Close', 'Volume', 'Adj_Close'])
        df.set_index('Date',inplace=True)
        return df

if __name__ == '__main__':
    pass
