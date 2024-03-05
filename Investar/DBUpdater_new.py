import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests, lxml
import pymysql
import calendar
from threading import Timer
from pandas_datareader import data as pdr
import sys
sys.path.append('c:/myPackage/stock/Investar')  # Analyzer 모듈이 있는 경로 추가
import Analyzer
import yfinance as yf
yf.pdr_override()
requests.packages.urllib3.disable_warnings()
import warnings
warnings.filterwarnings('ignore')

class DBUpdater:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost', user='root', password='taelyon', db='investar', charset='utf8')
        with self.conn.cursor() as curs:
            sql = """CREATE TABLE IF NOT EXISTS company_info (code VARCHAR(20), company VARCHAR(50), last_update 
            DATE, country VARCHAR(20), PRIMARY KEY (code)) """    #country 추가
            curs.execute(sql)
            sql = """CREATE TABLE IF NOT EXISTS daily_price (code VARCHAR(20), date DATE, open FLOAT(20), 
            high FLOAT(20), low FLOAT(20), close FLOAT(20), volume BIGINT(20), PRIMARY KEY (code, date)) """   #diff제거
            curs.execute(sql)
        self.conn.commit()
        self.codes = dict()

    def __del__(self):
        self.conn.close()

    def read_krx_code(self):
        result = []
        for sosok in range(0, 2):
            if sosok == 0:
                for page in range(1, 8):
                    url = "https://finance.naver.com/sise/sise_market_sum.nhn?sosok={}&page={}".format(sosok, page)
                    data = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
                    bsObj = BeautifulSoup(data.text, "html.parser")
                    box_type_l = bsObj.find("div", {"class": "box_type_l"})
                    type_2 = box_type_l.find("table", {"class": "type_2"})
                    tbody = type_2.find("tbody")
                    trs = tbody.findAll("tr")
                    stockInfos = []
                    for tr in trs:
                        try:
                            tds = tr.findAll("td")
                            aTag = tds[1].find("a")
                            href = aTag["href"]
                            name = aTag.text
                            stockInfo = {"code": href[22:], "company": name}
                            stockInfos.append(stockInfo)
                        except Exception as e:
                            pass
                    list = stockInfos
                    result += list
            elif sosok == 1:
                for page in range(1, 4):
                    url = "https://finance.naver.com/sise/sise_market_sum.nhn?sosok={}&page={}".format(sosok, page)
                    data = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=False)
                    bsObj = BeautifulSoup(data.text, "html.parser")
                    box_type_l = bsObj.find("div", {"class": "box_type_l"})
                    type_2 = box_type_l.find("table", {"class": "type_2"})
                    tbody = type_2.find("tbody")
                    trs = tbody.findAll("tr")
                    stockInfos = []
                    for tr in trs:
                        try:
                            tds = tr.findAll("td")
                            aTag = tds[1].find("a")
                            href = aTag["href"]
                            name = aTag.text
                            stockInfo = {"code": href[22:], "company": name}
                            stockInfos.append(stockInfo)
                        except Exception as e:
                            pass
                    list = stockInfos
                    result += list

        krx = pd.DataFrame(result, columns=('code', 'company'))
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

        with self.conn.cursor() as curs:
            sql = "SELECT last_update FROM company_info"
            curs.execute(sql)
            rs = curs.fetchall()
            today = datetime.today().strftime('%Y-%m-%d')

            if nation == 'kr':
                if rs[0][0] is None or rs[0][0].strftime('%Y-%m-%d') < today:
                    krx = self.read_krx_code()
                    for idx in range(len(krx)):
                        code = krx.code.values[idx]
                        company = krx.company.values[idx]
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                        print(f"[{tmnow}] {idx:04d} REPLACE INTO company_info VALUES ({code}, {company}, {today}, {nation})")
                    self.conn.commit()
                    print('')

            elif nation == 'us':
                if rs[-1][0] is None or rs[-1][0].strftime('%Y-%m-%d') < today:
                    spx = self.read_spx_code()
                    for idx in range(len(spx)):
                        code = spx.code.values[idx]
                        company = spx.company.values[idx]
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                        print(f"[{tmnow}] {idx:04d} REPLACE INTO company_info VALUES ({code}, {company}, {today}, {nation})")
                    self.conn.commit()
                    print('')

            elif nation == 'all':
                if rs[-1][0] is None or rs[-1][0].strftime('%Y-%m-%d') < today:  #DB 처음 실행시 오류(indexerrror) 나면 주석처리후 실행
                    krx = self.read_krx_code()
                    for idx in range(len(krx)):
                        code = krx.code.values[idx]
                        company = krx.company.values[idx]
                        nation = 'kr'
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                        print(f"[{tmnow}] {idx:04d} REPLACE INTO company_info VALUES ({code}, {company}, {today}, {nation})")
                    spx = self.read_spx_code()
                    for idx in range(len(spx)):
                        code = spx.code.values[idx]
                        company = spx.company.values[idx]
                        nation = 'us'
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                        print(f"[{tmnow}] {idx:04d} REPLACE INTO company_info VALUES ({code}, {company}, {today}, {nation})")
                    self.conn.commit()
                    print('')

    def read_naver(self, code, period):
        try:
            if period == 1:
                url = f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=3&requestType=0'
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
            df['date'] = pd.to_datetime(df['date'])  # 날짜 컬럼을 date로 수정
            # stock_table = stock_table.set_index('날짜')
        except Exception as e:
            print('Exception occured :', str(e))
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
        # 야후 파이낸스 주가 읽어오기
        try:
            if period == 1:

                # pdr 활용
                com = pdr.get_data_yahoo(code, (datetime.today() - timedelta(days=6)), datetime.today())
                com['date'] = com.index.strftime('%Y-%m-%d')
                com = com.reset_index(drop=True)
                com['code'] = code
                df = com[['code', 'date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']]
                df = df.rename(
                    columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Adj Close': 'close', 'Volume': 'volume'})
                df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
                df = df.dropna()
                df = df.iloc[-3:]
                return df
            elif period == 2:
                com = pdr.get_data_yahoo(code, '2021-01-01', datetime.today())
                com['date'] = com.index.strftime('%Y-%m-%d')
                com = com.reset_index(drop=True)
                com['code'] = code
                df = com[['code', 'date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']]
                df = df.rename(
                    columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Adj Close': 'close', 'Volume': 'volume'})
                df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
                return df
        except requests.ConnectionError as e:
            print(f"Connection error occurred: {e}")
        # 연결 오류에 대한 추가 처리
        except requests.Timeout as e:
            print(f"Request timed out: {e}")
            # 타임아웃 오류에 대한 추가 처리
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            # 기타 예상치 못한 오류에 대한 처리
        return None  # 오류가 발생했을 경우 None을 반환하거나 적절한 복구 조치를 취합니다.

    def replace_into_db(self, df, num, code, company):
        with self.conn.cursor() as curs:
            for r in df.itertuples():
                sql = f"REPLACE INTO daily_price VALUES ('{code}','{r.date}',{r.open},{r.high},{r.low},{r.close},{r.volume})"
                curs.execute(sql)
            self.conn.commit()
            print('[{}] #{:04d} {} ({}) : {} rows > REPLACE INTO daily_price [OK]'.format(datetime.now().strftime('%Y-%m-%d %H:%M'), num+1, company, code, len(df)))

    def update_daily_price(self, nation):
    # Initialize or clear self.codes
        self.codes = dict()
        
        # Update self.codes based on the nation
        if nation in ['kr', 'us', 'all']:        
            sql = f"SELECT code, company FROM company_info WHERE country = '{nation}' OR '{nation}' = 'all'"
            df = pd.read_sql(sql, self.conn)
            for idx, row in df.iterrows():
                self.codes[row['code']] = row['company']

        # Continue with the existing logic to update daily prices using the updated self.codes
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
                        df = self.read_naver(code, 1)  # For initial run, change to 2 to update
                    else:
                        df = self.read_yfinance(code, 1)  # For initial run, change to 2 to update
                else:
                    continue  # Skip if none of the conditions match

                if df is None:
                    continue  # Skip if no data fetched

                self.replace_into_db(df, idx, code, self.codes[code])

    def execute_daily(self):
        # self.ric_code()
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

    def update_stock_price(self, company, period):
        mk = Analyzer.MarketDB()
        stk = mk.get_comp_info()
        val = stk[(stk['company'] == company) | (stk['code'] == company)]
        code = val.iloc[0]['code']
        company = val.iloc[0]['company']
        if val.iloc[0]['country'] == 'kr':
            df = self.read_naver(code, period)
        elif val.iloc[0]['country'] == 'us':
            self.ric_code()
            df = self.read_yfinance(code, period)
        # df = df.dropna()
        self.replace_into_db(df, 0, code, company)

if __name__ == '__main__':
    dbu = DBUpdater()
    # dbu.update_comp_info('all')
    dbu.execute_daily()