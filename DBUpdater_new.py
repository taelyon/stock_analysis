import sqlite3
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from curl_cffi import requests
import calendar
from threading import Timer
import yfinance as yf
# requests.packages.urllib3.disable_warnings()
import warnings
warnings.filterwarnings('ignore')
import re
from pykrx import stock

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
        pass

    def init_db(self):
        self.conn = sqlite3.connect('investar.db')
        cursor = self.conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table in tables:
            cursor.execute(f"DELETE FROM {table[0]};")
            self.conn.commit()

        cursor.close()

    def read_krx_code(self):
        result = []
        for sosok in range(2):
            page_range = 8 if sosok == 0 else 4
            for page in range(1, page_range):
                url = f"https://finance.naver.com/sise/sise_market_sum.nhn?sosok={sosok}&page={page}"
                data = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
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
                print('한국 주식 종목 업데이트 시작')
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
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 한국 주식 종목 업데이트 완료 ({today}, {nation})")
                print('')

        elif nation == 'us':
            if rs is None or rs[0] < today:
                print('미국 주식 종목 업데이트 시작')
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
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 미국 주식 종목 업데이트 완료 ({today}, {nation})")
                print('')

        elif nation == 'all':
            if rs is None or rs[0] < today:
                print('전체 주식 종목 업데이트 시작')
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
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 전체 주식 종목 업데이트 완료 ({today}, {nation})")
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
                start_date = datetime(2024, 1, 1)
            else:
                print("Invalid period. Choose 1 for the last week or 2 for data since 2024.")
                return None

            session = requests.Session(impersonate="chrome")
            session.verify = False

            stock_data = yf.download(code, start=start_date, end=datetime.today(), progress=False, session=session, auto_adjust=True)
            stock_data.columns = stock_data.columns.get_level_values(0)
            stock_data.columns.name = None

            stock_data['date'] = stock_data.index.strftime('%Y-%m-%d')
            stock_data.reset_index(drop=True, inplace=True)

            columns = ['date', 'Open', 'High', 'Low', 'Close', 'Volume']
            stock_data = stock_data[columns]
            stock_data.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
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
        df = df.reset_index(drop=True)

        data_to_insert = [
            (code, r.date.strftime('%Y-%m-%d'), r.open, r.high, r.low, r.close, r.volume)
            for r in df.itertuples()
        ]
        cursor.executemany(
            "REPLACE INTO daily_price VALUES (?, ?, ?, ?, ?, ?, ?)",
            data_to_insert
        )
        self.conn.commit()
        cursor.close()
        print('[{}] #{:04d} {} ({}) : {}일 주가 업데이트 [OK]'.format(datetime.now().strftime('%Y-%m-%d %H:%M'), num+1, company, code, len(df)))

    def update_daily_price(self, nation, period=None):
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
                    df = self.read_naver(code, period)
                elif nation == 'us' and len(code) < 6:
                    df = self.read_yfinance(code, period)
                elif nation == 'all':
                    if len(code) >= 6:
                        df = self.read_naver(code, period)   # For initial run, change to 2 to update
                    else:
                        df = self.read_yfinance(code, period) # For initial run, change to 2 to update
                else:
                    continue

                if df is None:
                    continue

                self.replace_into_db(df, idx, code, self.codes[code])

    def execute_daily(self):
        self.update_comp_info('all')
        self.update_daily_price('all', 1)

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
        self.conn = sqlite3.connect('investar.db')
        self.codes = {}

    def __del__(self):
        pass

    def get_krx_ticker_by_name(self, name):
        tickers = stock.get_market_ticker_list(market="ALL")
        for ticker in tickers:
            if stock.get_market_ticker_name(ticker) == name:
                return ticker
        tickers = stock.get_etf_ticker_list()  # ETF
        for ticker in tickers:
            if stock.get_etf_ticker_name(ticker) == name:
                return ticker
        return None

    def is_hangul(self, text):
        hangul_regex = re.compile('[\u3131-\u3163\uac00-\ud7a3]')
        return bool(hangul_regex.search(text))

    def get_comp_info(self, company=None):
        if company:
            # 특정 회사 정보만 조회하는 경우
            sql = "SELECT * FROM company_info WHERE code = ? OR company = ?"
            stock_list = pd.read_sql(sql, self.conn, params=(company, company))
        else:
            # 모든 회사 정보를 조회하는 경우
            sql = "SELECT * FROM company_info"
            stock_list = pd.read_sql(sql, self.conn)

        if company == 'default':
            return stock_list
        
        # stock_list가 비어있고, company 인자가 있는 경우 (신규 종목 추가 로직)
        if stock_list.empty and company:
            print(f"{company}은(는) 새로운 종목입니다.")
            stocks = []
            if company.isdigit():  # 한국 증시 종목코드
                code = company
                company_name = stock.get_market_ticker_name(code)
                if isinstance(company_name, pd.DataFrame) and company_name.empty:
                    company_name = stock.get_etf_ticker_name(code)
                stocks.append((code, company_name, 'kr'))
            elif self.is_hangul(company):  # 한국 증시 종목명
                code = self.get_krx_ticker_by_name(company)
                company_name = company
                stocks.append((code, company_name, 'kr'))
            elif company.isalpha():  # 미국 증시 종목코드
                code = company
                stock_info = yf.Ticker(code)
                company_info = stock_info.info
                company_name = company_info.get('longName', 'N/A')
                stocks.append((code, company_name, 'us'))
            else:
                print(f"{company}에 해당하는 종목을 찾을 수 없습니다.")
                # 빈 DataFrame을 반환하여 이후 로직에서 오류가 발생하지 않도록 함
                return pd.DataFrame()

            if stocks:
                df_stocks = pd.DataFrame(stocks, columns=['code', 'company', 'country'])
                
                # 데이터 정제
                new_stock = df_stocks.copy()
                new_stock['company'] = new_stock['company'].str.replace("'", "").str.replace("Inc.", "Inc", regex=False).str.replace("Co.", "Co", regex=False).str.replace("Corp.", "Corp", regex=False).str.replace("Corporation", "Corp", regex=False).str.replace(",", "", regex=False)
                new_stock['code'] = new_stock['code'].str.replace(".", "-", regex=False)
                new_stock['last_update'] = datetime.today().strftime('%Y-%m-%d')
                
                # 데이터베이스에 새로운 종목 정보 추가
                new_stock.to_sql('company_info', self.conn, if_exists='append', index=False)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 신규 주식 종목 추가 ({new_stock.iloc[0]['company']})")
                
                # 새로 추가된 종목 정보를 stock_list에 할당
                stock_list = new_stock

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
            # 신규 종목일 수 있으므로 get_comp_info를 호출하여 DB에 추가 시도
            self.get_comp_info(code)
            # 재귀 호출 대신, 다시 한번 코드를 찾아봄
            if code in self.codes:
                pass # 성공적으로 추가됨
            else:
                 print(f"ValueError: Code({code}) still doesn't exist after attempting to add.")
                 return pd.DataFrame() # 빈 DataFrame 반환

        sql = f"SELECT * FROM daily_price WHERE code = ? AND date >= ? AND date <= ?"
        df = pd.read_sql(sql, self.conn, params=(code, start_date, end_date))
        df.index = df['date']
        return df
    
if __name__ == '__main__':
    dbu = DBUpdater()
    dbu.execute_daily()
