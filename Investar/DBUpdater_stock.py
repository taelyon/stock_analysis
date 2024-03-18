import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import pymysql, calendar, json
from threading import Timer
from pandas_datareader import data as pdr
import yfinance as yf
yf.pdr_override()
requests.packages.urllib3.disable_warnings()

class DBUpdater:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost', user='root', password='taelyon', db='investar', charset='utf8mb4')

        with self.conn.cursor() as curs:
            sql = """CREATE TABLE IF NOT EXISTS company_info (code VARCHAR(20), company VARCHAR(40), last_update 
            DATE, PRIMARY KEY (code)) """
            curs.execute(sql)
            sql = """CREATE TABLE IF NOT EXISTS daily_price (code VARCHAR(20), date DATE, open FLOAT(20), 
            high FLOAT(20), low FLOAT(20), close FLOAT(20), volume BIGINT(20), PRIMARY KEY (code, date)) """
            curs.execute(sql)
        self.conn.commit()
        self.codes = dict()

    def __del__(self):
        self.conn.close()

    def read_naver(self, code, period):
        try:
            if period == 1:
                url = f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=3&requestType=0'
            elif period == 2:
                url = f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=500&requestType=0'
            req = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
            soup = BeautifulSoup(req.text, 'lxml')
            stock_soup = soup.find_all('item')

            stock_date = []
            for stock in stock_soup:
                stock_date.append(stock['data'].split('|'))

            df = pd.DataFrame(stock_date)
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].apply(
                pd.to_numeric, errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'])  # 날짜 컬럼을 date로 수정
            # stock_table = stock_table.set_index('날짜')
        except Exception as e:
            print('Exception occured :', str(e))
            return None
        return df

    def read_yfinance(self, code, period):
        # 야후 파이낸스 주가 읽어오기
        try:
            if period == 1:
                com = pdr.get_data_yahoo(code, (datetime.today() - timedelta(days=5)), datetime.today())
            elif period == 2:
                com = pdr.get_data_yahoo(code, '2020-01-01', datetime.today())

            com['date'] = com.index
            com = com.reset_index(drop=True)
            com['code'] = code
            df = com[['code','date','Open', 'High','Low','Adj Close', 'Volume']]
            df = df.rename(columns={'Open':'open', 'High':'high', 'Low':'low', 'Adj Close':'close', 'Volume':'volume'})
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            print('Exception occured :', str(e))
            return None
        return df

    def replace_into_db(self, df, num, code, company):
        with self.conn.cursor() as curs:
            for r in df.itertuples():
                sql = f"REPLACE INTO daily_price VALUES ('{code}','{r.date}',{r.open},{r.high},{r.low},{r.close},{r.volume})"
                curs.execute(sql)
            self.conn.commit()
            print('[{}] #{:04d} {} ({}) : {} rows > REPLACE INTO daily_price [OK]'.format(datetime.now().strftime('%Y-%m-%d %H:%M'), num+1, company, code, len(df)))

    def update_stock_price(self, company, period):
        sql = "SELECT * FROM company_info"
        df_com = pd.read_sql(sql, self.conn)
        for idx in range(len(df_com)):
            self.codes[df_com['code'].values[idx]] = df_com['company'].values[idx]

        codes_keys = list(self.codes.keys())
        codes_values = list(self.codes.values())
        if company in codes_keys:
            code = company
        elif company in codes_values:
            idx = codes_values.index(company)
            code = codes_keys[idx]

        if len(code) >= 6:
            df = self.read_naver(code, period)
        elif len(code) < 6:
            df = self.read_yfinance(code, period)
        # df_price = df_price.dropna()
        self.replace_into_db(df, 0, code, self.codes[code])

if __name__ == '__main__':
    dbu = DBUpdater()
    # dbu.execute_daily()
    # dbu.update_comp_info('kr')
    # dbu.update_stock_price('005930')
    # dbu.update_stock_price('005930')

