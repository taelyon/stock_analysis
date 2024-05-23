import sqlite3
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import calendar
from threading import Timer
from pandas_datareader import data as pdr
import yfinance as yf
yf.pdr_override()
requests.packages.urllib3.disable_warnings()
import warnings
warnings.filterwarnings('ignore')
import re
from pykrx import stock


class DBUpdater:
    def __init__(self):
        # SQLite 데이터베이스 연결
        self.conn = sqlite3.connect('investetf.db')
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_info (
                code TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                last_update DATE,
                country TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_price (
                code TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (code, date)
            )
        """)
        self.conn.commit()
        self.codes = dict()

    def __del__(self):
        pass

    def init_db(self):
        self.conn = sqlite3.connect('investetf.db')
        cursor = self.conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table in tables:
            cursor.execute(f"DELETE FROM {table[0]};")
            self.conn.commit()

        cursor.close()

    def get_kr_eft_list(self):
        today = datetime.today().strftime("%Y%m%d")
        stocks = []

        df = stock.get_etf_ticker_list(date=today) # ETF
        for ticker in df:
            name = stock.get_etf_ticker_name(ticker)
            stocks.append((ticker, name))

        df_stocks = pd.DataFrame(stocks, columns=['code', 'company'])

        return df_stocks

    def update_comp_info(self, nation):
        sql = "SELECT * FROM company_info"
        df = pd.read_sql(sql, self.conn)
        for idx in range(len(df)):
            self.codes[df['code'].values[idx]] = df['company'].values[idx]

        today = datetime.today().strftime('%Y-%m-%d')

        cursor = self.conn.cursor()
        cursor.execute("SELECT last_update FROM company_info")
        rs = cursor.fetchone()

        if nation == 'kr':
            if rs is None or rs[0] < today:
                print('ETF 종목 업데이트')
                krx = self.get_kr_eft_list()
                for idx in range(len(krx)):
                    code = krx.code.values[idx]
                    company = krx.company.values[idx]
                    cursor.execute(
                        "REPLACE INTO company_info (code, company, last_update, country) VALUES (?, ?, ?, ?)",
                        (code, company, today, nation)
                    )
                    self.codes[code] = company
                self.conn.commit()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] REPLACE INTO company_info VALUES ({today}, {nation})")
                print('')

        cursor.close()

    def read_naver(self, code, period):
        try:
            if period == 1:
                url = f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=5&requestType=0'
            elif period == 2:
                url = f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=500&requestType=0'
            req = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
            soup = BeautifulSoup(req.text, "lxml")
            stock_soup = soup.find_all('item')

            stock_date = []
            for stock in stock_soup:
                stock_date.append(stock['data'].split('|'))

            df = pd.DataFrame(stock_date)
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].apply(
                pd.to_numeric, errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            print('Exception occured:', str(e))
            return None
        return df

    def replace_into_db(self, df, num, code, company):
        cursor = self.conn.cursor()
        
        # 날짜 열을 datetime 형식으로 변환
        df['date'] = pd.to_datetime(df['date'])

        for r in df.itertuples():
            cursor.execute(
                "REPLACE INTO daily_price VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, r.date.strftime('%Y-%m-%d'), r.open, r.high, r.low, r.close, r.volume)
            )
        self.conn.commit()
        cursor.close()
        print('[{}] #{:04d} {} ({}) : {} rows > REPLACE INTO daily_price [OK]'.format(datetime.now().strftime('%Y-%m-%d %H:%M'), num+1, company, code, len(df)))

    def update_daily_price(self, nation, period=None):
        self.codes = dict()

        if nation == 'kr':
            sql = "SELECT code, company FROM company_info WHERE country = ?"
            df = pd.read_sql(sql, self.conn, params=(nation,))
            for idx, row in df.iterrows():
                self.codes[row['code']] = row['company']

        global run
        run = True
        if nation == 'stop':
            run = False

        for idx, code in enumerate(self.codes):
            if run:
                if nation == 'kr' and len(code) >= 6:
                    df = self.read_naver(code, period)
                    self.replace_into_db(df, idx, code, self.codes[code])
                else:
                    continue
                
    def execute_daily(self):
        self.update_comp_info('kr')
        self.update_daily_price('kr', 1)

        tmnow = datetime.now()
        lastday = calendar.monthrange(tmnow.year, tmnow.month)[1]
        if tmnow.month == 12 and tmnow.day == lastday:
            tmnext = tmnow.replace(year=tmnow.year+1, month=1, day=1, hour=17, minute=0, second=0)
        elif tmnow.day == lastday:
            tmnext = tmnow.replace(month=tmnow.month+1, day=1, hour=17, minute=0, second=0)
        else:
            tmnext = tmnow.replace(day=tmnow.day+1, hour=17, minute=0, second=0)
        tmdiff = tmnext - tmnow
        secs = tmdiff.seconds

        t = Timer(secs, self.execute_daily)
        print("Waiting for next update ({}) ...".format(tmnext.strftime('%Y-%m-%d %H:%M')))
        t.start()

class MarketDB:
    def __init__(self):
        # SQLite3용 SQLAlchemy 엔진 생성
        self.conn = sqlite3.connect('investetf.db')
        self.codes = {}

    def __del__(self):
        pass

    def get_kr_stock_list(self):
        today = datetime.today().strftime("%Y%m%d")
        stocks = []

        df = stock.get_etf_ticker_list(date=today) # ETF
        for ticker in df:
            name = stock.get_etf_ticker_name(ticker)
            stocks.append((ticker, name))

        df_stocks = pd.DataFrame(stocks, columns=['Code', 'Name'])

        return df_stocks
        
    def get_comp_info(self, company=None):
        sql = "SELECT * FROM company_info"
        stock_list = pd.read_sql(sql, self.conn)

        if company == 'all':
            return stock_list
        
        # 입력된 종목코드나 종목명이 없는 경우, 최신 종목 리스트에서 추가
        if company is not None:
            if company not in stock_list['code'].values and company not in stock_list['company'].values:
                print(f"{company}은(는) 새로운 종목입니다.")
                kr_stock_list = self.get_kr_stock_list()

                if company in kr_stock_list['Code'].values:
                    new_stock = kr_stock_list[kr_stock_list['Code'] == company]
                elif company in kr_stock_list['Name'].values:
                    new_stock = kr_stock_list[kr_stock_list['Name'] == company]
                else:
                    print(f"{company}에 해당하는 종목을 찾을 수 없습니다.")
                    return stock_list
                
                today = datetime.today().strftime('%Y-%m-%d')
                new_stock['last_update'] = today
                new_stock['country'] = 'kr'

                # 새로운 종목을 stock_list에 추가
                stock_list = pd.concat([stock_list, new_stock.rename(columns={'Name': 'company', 'Code': 'code'})], ignore_index=True)

                # 데이터베이스에 업데이트
                cursor = self.conn.cursor()
                code = new_stock.Code.values[0]
                company = new_stock.Name.values[0]
                today = new_stock.last_update.values[0]
                nation = new_stock.country.values[0]
                cursor.execute(
                    "REPLACE INTO company_info (code, company, last_update, country) VALUES (?, ?, ?, ?)",
                    (code, company, today, nation)
                )
                self.codes[code] = company
                self.conn.commit()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] REPLACE INTO company_info VALUES ({today}, {nation})")

        # self.codes 딕셔너리에 코드와 회사명 저장
        for idx in range(len(stock_list)):
            self.codes[stock_list['code'].values[idx]] = stock_list['company'].values[idx]

        return stock_list

    def get_daily_price(self, code, start_date=None, end_date=None):
        if start_date is None:
            one_year_ago = datetime.today() - timedelta(days=365)
            start_date = one_year_ago.strftime('%Y-%m-%d')
            print(f"start_date is initialized to '{start_date}'")
        else:
            start_lst = re.split(r'\D+', start_date)
            if start_lst[0] == '':
                start_lst = start_lst[1:]
            start_year = int(start_lst[0])
            start_month = int(start_lst[1])
            start_day = int(start_lst[2])
            if start_year < 1900 or start_year > 2200:
                print(f"ValueError: start_year({start_year:d}) is wrong.")
                return
            if start_month < 1 or start_month > 12:
                print(f"ValueError: start_month({start_month:d}) is wrong.")
                return
            if start_day < 1 or start_day > 31:
                print(f"ValueError: start_day({start_day:d}) is wrong.")
                return
            start_date = f"{start_year:04d}-{start_month:02d}-{start_day:02d}"

        if end_date is None:
            end_date = datetime.today().strftime('%Y-%m-%d')
            print(f"end_date is initialized to '{end_date}'")
        else:
            end_lst = re.split(r'\D+', end_date)
            if end_lst[0] == '':
                end_lst = end_lst[1:]
            end_year = int(end_lst[0])
            end_month = int(end_lst[1])
            end_day = int(end_lst[2])
            if end_year < 1800 or end_year > 2200:
                print(f"ValueError: end_year({end_year:d}) is wrong.")
                return
            if end_month < 1 or end_month > 12:
                print(f"ValueError: end_month({end_month:d}) is wrong.")
                return
            if end_day < 1 or end_day > 31:
                print(f"ValueError: end_day({end_day:d}) is wrong.")
                return
            end_date = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"

        codes_keys = list(self.codes.keys())
        codes_values = list(self.codes.values())
        if code in codes_keys:
            pass
        elif code in codes_values:
            idx = codes_values.index(code)
            code = codes_keys[idx]
        else:
            print(f"ValueError: Code({code}) doesn't exist.")
            return

        sql = f"SELECT * FROM daily_price WHERE code = '{code}' AND date >= '{start_date}' AND date <= '{end_date}'"
        df = pd.read_sql(sql, self.conn)
        df.index = df['date']
        return df
    
if __name__ == '__main__':
    dbu = DBUpdater()
    dbu.execute_daily()
