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

class DBUpdater:
    def __init__(self):
        # SQLite 데이터베이스 연결
        self.conn = sqlite3.connect('investar.db')
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
        self.conn.close()

    def read_krx_code(self):
        result = []
        for sosok in range(2):
            page_range = 8 if sosok == 0 else 4
            for page in range(1, page_range):
                url = f"https://finance.naver.com/sise/sise_market_sum.nhn?sosok={sosok}&page={page}"
                data = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
                bsObj = BeautifulSoup(data.text, "html.parser")
                type_2 = bsObj.find("table", {"class": "type_2"})
                trs = type_2.find("tbody").findAll("tr")

                for tr in trs:
                    try:
                        tds = tr.findAll("td")
                        if len(tds) > 1:
                            aTag = tds[1].find("a")
                            stock_code = aTag['href'].split('=')[-1]
                            stock_name = aTag.text.strip()
                            result.append({"code": stock_code, "company": stock_name})
                    except Exception as e:
                        continue
        krx = pd.DataFrame(result, columns=['code', 'company'])
        return krx

    def read_spx_code(self):
        url = f'https://www.slickcharts.com/sp500'
        r = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
        spx = pd.read_html(r.text)[0]
        spx = spx.rename(columns={'Symbol': 'code', 'Company': 'company'})
        spx = spx[['code', 'company']]
        spx['company'] = spx['company'].str.replace("'", "")
        spx['company'] = spx['company'].str.replace("Inc.", "Inc", regex=False)
        spx['company'] = spx['company'].str.replace("Co.", "Co", regex=False)
        spx['company'] = spx['company'].str.replace("Corp.", "Corp", regex=False)
        spx['company'] = spx['company'].str.replace("Corporation", "Corp", regex=False)
        spx['company'] = spx['company'].str.replace(",", "", regex=False)
        spx['code'] = spx['code'].str.replace(".", "-", regex=False)
        return spx

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
                print('한국 주식 종목 업데이트')
                krx = self.read_krx_code()
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

        elif nation == 'us':
            if rs is None or rs[0] < today:
                print('미국 주식 종목 업데이트')
                spx = self.read_spx_code()
                for idx in range(len(spx)):
                    code = spx.code.values[idx]
                    company = spx.company.values[idx]
                    cursor.execute(
                        "REPLACE INTO company_info (code, company, last_update, country) VALUES (?, ?, ?, ?)",
                        (code, company, today, nation)
                    )
                    self.codes[code] = company
                self.conn.commit()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] REPLACE INTO company_info VALUES ({today}, {nation})")
                print('')

        elif nation == 'all':
            if rs is None or rs[0] < today:
                print('전체 주식 종목 업데이트')
                krx = self.read_krx_code()
                for idx in range(len(krx)):
                    code = krx.code.values[idx]
                    company = krx.company.values[idx]
                    cursor.execute(
                        "REPLACE INTO company_info (code, company, last_update, country) VALUES (?, ?, ?, ?)",
                        (code, company, today, 'kr')
                    )
                    self.codes[code] = company

                spx = self.read_spx_code()
                for idx in range(len(spx)):
                    code = spx.code.values[idx]
                    company = spx.company.values[idx]
                    cursor.execute(
                        "REPLACE INTO company_info (code, company, last_update, country) VALUES (?, ?, ?, ?)",
                        (code, company, today, 'us')
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

    def ric_code(self):
        result = []
        url = 'https://blog.naver.com/PostView.naver?blogId=taelyon&logNo=222768959654'
        req = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
        soup = BeautifulSoup(req.text, features="lxml")
        box_type_l = soup.find("div", {"class": "se-table-container"})
        type_2 = box_type_l.find("table", {"class": "se-table-content"})
        tbody = type_2.find("tbody")
        trs = tbody.findAll("tr")
        stockInfos = []
        for tr in trs:
            try:
                tds = tr.findAll("td")
                code = tds[0].text[1:-1]
                ric = tds[1].text[1:-1]
                company = tds[2].text[1:-1]
                stockInfo = {"code": code, "ric": ric, "company": company}
                stockInfos.append(stockInfo)
            except Exception as e:
                pass
        list = stockInfos
        result += list

        df_ric = pd.DataFrame(result)
        df_ric = df_ric.drop(df_ric.index[0])
        return df_ric
    
    def read_yfinance(self, code, period):
        try:
            if period == 1:
                start_date = datetime.today() - timedelta(days=10)
            elif period == 2:
                start_date = datetime(2022, 1, 1)
            else:
                print("Invalid period. Choose 1 for the last week or 2 for data since 2021.")
                return None

            stock_data = pdr.get_data_yahoo(code, start_date, datetime.today())
            stock_data['date'] = stock_data.index.strftime('%Y-%m-%d')
            stock_data.reset_index(drop=True, inplace=True)
            stock_data['code'] = code

            columns = ['code', 'date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
            stock_data = stock_data[columns]
            stock_data.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Adj Close': 'close', 'Volume': 'volume'
            }, inplace=True)
            stock_data = stock_data[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()

            if period == 1:
                return stock_data.iloc[-5:]

            return stock_data

        except requests.ConnectionError as e:
            print(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            print(f"Request timed out: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

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

    def update_daily_price(self, nation):
        self.codes = dict()

        if nation in ['kr', 'us', 'all']:
            sql = f"SELECT code, company FROM company_info WHERE country = ? OR ? = 'all'"
            df = pd.read_sql(sql, self.conn, params=(nation, nation))
            for idx, row in df.iterrows():
                self.codes[row['code']] = row['company']

        global run
        run = True
        if nation == 'stop':
            run = False

        for idx, code in enumerate(self.codes):
            if run:
                if nation == 'kr' and len(code) >= 6:
                    df = self.read_naver(code, 1)
                elif nation == 'us' and len(code) < 6:
                    df = self.read_yfinance(code, 1)
                elif nation == 'all':
                    if len(code) >= 6:
                        df = self.read_naver(code, 2)   # For initial run, change to 2 to update
                    else:
                        df = self.read_yfinance(code, 2) # For initial run, change to 2 to update
                else:
                    continue

                if df is None:
                    continue

                self.replace_into_db(df, idx, code, self.codes[code])

    def execute_daily(self):
        self.update_comp_info('all')
        self.update_daily_price('all')

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

if __name__ == '__main__':
    dbu = DBUpdater()
    dbu.execute_daily()
