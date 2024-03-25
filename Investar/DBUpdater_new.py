import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import pymysql
import calendar
from threading import Timer
from pandas_datareader import data as pdr
# import sys
# sys.path.append('c:/myPackage/stock/Investar')  # Analyzer 모듈이 있는 경로 추가
# import Analyzer
import yfinance as yf
yf.pdr_override()
requests.packages.urllib3.disable_warnings()
import warnings
warnings.filterwarnings('ignore')

class DBUpdater:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost', user='root', password='taelyon', db='investar', charset='utf8mb4')
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
        # Consolidate requests for KOSPI (sosok=0) and KOSDAQ (sosok=1)
        for sosok in range(2):
            # Set different page ranges for KOSPI and KOSDAQ
            page_range = 8 if sosok == 0 else 4
            for page in range(1, page_range):
                url = f"https://finance.naver.com/sise/sise_market_sum.nhn?sosok={sosok}&page={page}"
                data = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
                bsObj = BeautifulSoup(data.text, "html.parser")

                # Simplify finding the table with stock information
                type_2 = bsObj.find("table", {"class": "type_2"})
                trs = type_2.find("tbody").findAll("tr")

                for tr in trs:
                    try:
                        tds = tr.findAll("td")
                        if len(tds) > 1:  # Ensure the row has the necessary data fields
                            aTag = tds[1].find("a")
                            stock_code = aTag['href'].split('=')[-1]  # Get stock code directly from the link
                            stock_name = aTag.text.strip()  # Clean stock name from any surrounding whitespaces
                            result.append({"code": stock_code, "company": stock_name})
                    except Exception as e:
                        continue  # Skip rows that don't match the expected format

        # Create DataFrame from the accumulated results
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

        with self.conn.cursor() as curs:
            sql = "SELECT last_update FROM company_info"
            curs.execute(sql)
            rs = curs.fetchone()
            today = datetime.today().strftime('%Y-%m-%d')

            if nation == 'kr':
                if rs is None or rs[0].strftime('%Y-%m-%d') < today:
                    print('한국 주식 종목 업데이트')
                    krx = self.read_krx_code()
                    for idx in range(len(krx)):
                        code = krx.code.values[idx]
                        company = krx.company.values[idx]
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                    self.conn.commit()
                    print(f"[{tmnow}] REPLACE INTO company_info VALUES ({today}, {nation})")
                    print('')

            elif nation == 'us':
                if rs is None or rs[-1].strftime('%Y-%m-%d') < today:
                    print('미국 주식 종목 업데이트')
                    spx = self.read_spx_code()
                    for idx in range(len(spx)):
                        code = spx.code.values[idx]
                        company = spx.company.values[idx]
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                    self.conn.commit()
                    print(f"[{tmnow}] REPLACE INTO company_info VALUES ({today}, {nation})")
                    print('')

            elif nation == 'all':
                if rs is None or rs[-1].strftime('%Y-%m-%d') < today:  #rs[0]을 rs로 수정하여 DB 처음 실행시에도 가능
                    print('전체 주식 종목 업데이트')
                    krx = self.read_krx_code()
                    for idx in range(len(krx)):
                        code = krx.code.values[idx]
                        company = krx.company.values[idx]
                        nation = 'kr'
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                    spx = self.read_spx_code()
                    for idx in range(len(spx)):
                        code = spx.code.values[idx]
                        company = spx.company.values[idx]
                        nation = 'us'
                        sql = f"REPLACE INTO company_info (code, company, last_update, country) VALUES ('{code}','{company}','{today}','{nation}')"
                        curs.execute(sql)
                        self.codes[code] = company
                        tmnow = datetime.now().strftime('%Y-%m-%d %H:%M')
                    self.conn.commit()
                    print(f"[{tmnow}] REPLACE INTO company_info VALUES ({today}, {nation})")
                    print('')

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
   
        try:
            # Set date range based on 'period'
            if period == 1:
                start_date = datetime.today() - timedelta(days=10)
            elif period == 2:
                start_date = datetime(2021, 1, 1)
            else:
                print("Invalid period. Choose 1 for the last week or 2 for data since 2021.")
                return None

            # Fetch data from Yahoo Finance
            stock_data = pdr.get_data_yahoo(code, start_date, datetime.today())
            stock_data['date'] = stock_data.index.strftime('%Y-%m-%d')
            stock_data.reset_index(drop=True, inplace=True)
            stock_data['code'] = code
            
            # Select and rename columns
            columns = ['code', 'date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
            stock_data = stock_data[columns]
            stock_data.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Adj Close': 'close', 'Volume': 'volume'
            }, inplace=True)
            stock_data = stock_data[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()

            # For period == 1, return the last 3 days of data
            if period == 1:
                return stock_data.iloc[-3:]
            
            # For period == 2, return all data since start_date
            return stock_data

        except requests.ConnectionError as e:
            print(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            print(f"Request timed out: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    
        return None  # Return None if errors occurred

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

    # def update_stock_price(self, company, period):
    #     mk = Analyzer.MarketDB()
    #     stk = mk.get_comp_info()
    #     val = stk[(stk['company'] == company) | (stk['code'] == company)]
    #     code = val.iloc[0]['code']
    #     company = val.iloc[0]['company']
    #     if val.iloc[0]['country'] == 'kr':
    #         df = self.read_naver(code, period)
    #     elif val.iloc[0]['country'] == 'us':
    #         self.ric_code()
    #         df = self.read_yfinance(code, period)
    #     # df = df.dropna()
    #     self.replace_into_db(df, 0, code, company)

if __name__ == '__main__':
    dbu = DBUpdater()
    # dbu.update_comp_info('all')
    dbu.execute_daily()