import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from bs4 import BeautifulSoup
import requests
import re
import yfinance as yf
# from tqdm import tqdm # tqdm 라이브러리를 더 이상 사용하지 않으므로 삭제합니다.
import exchange_calendars as xcals
import warnings
import threading
import time

warnings.filterwarnings('ignore')

class DBManager:
    """ 각 스레드가 독립적인 DB 연결을 갖도록 관리하는 기반 클래스 """
    def __init__(self):
        self.thread_local = threading.local()

    def _get_db_conn(self):
        """ 현재 스레드에 대한 DB 연결 및 커서를 가져오거나 생성합니다. """
        if not hasattr(self.thread_local, 'conn'):
            self.thread_local.conn = sqlite3.connect('investar.db')
            self.thread_local.cur = self.thread_local.conn.cursor()
        return self.thread_local.conn, self.thread_local.cur

    def close_db_conn(self):
        """ 현재 스레드의 DB 연결을 닫습니다. (필요시 사용) """
        if hasattr(self.thread_local, 'conn'):
            self.thread_local.conn.close()
            del self.thread_local.conn
            del self.thread_local.cur

class DBUpdater(DBManager):
    def __init__(self):
        """생성자: DB 연결 및 테이블 생성/검증"""
        super().__init__()
        conn, cur = self._get_db_conn()
        self.create_tables(conn, cur)
        self.ric_codes = {}
        self.run_update = True

    def create_tables(self, conn, cur):
        """DB에 필요한 테이블 생성 (없을 경우) 및 스키마 검증"""
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_price'")
        table_exists = cur.fetchone()
        recreate_daily_price = False
        if table_exists:
            cur.execute("PRAGMA table_info(daily_price)")
            columns = [info[1] for info in cur.fetchall()]
            expected_columns = ['code', 'date', 'open', 'high', 'low', 'close', 'diff', 'volume']
            if sorted(columns) != sorted(expected_columns):
                print("daily_price 테이블 스키마가 변경되어 테이블을 삭제합니다.")
                cur.execute("DROP TABLE daily_price")
                recreate_daily_price = True
        
        if not table_exists or recreate_daily_price:
            print("daily_price 테이블을 생성합니다.")
            sql_daily_price = """
                CREATE TABLE daily_price (
                    code TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, diff REAL, volume INTEGER,
                    PRIMARY KEY (code, date)
                );"""
            cur.execute(sql_daily_price)

        sql_comp_info = """
            CREATE TABLE IF NOT EXISTS comp_info (
                code TEXT PRIMARY KEY, company TEXT, market TEXT, country TEXT, updated_date TEXT
            );"""
        cur.execute(sql_comp_info)
        conn.commit()

    def init_db(self, table_name='daily_price'):
        conn, cur = self._get_db_conn()
        cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cur.fetchone() is not None:
            cur.execute(f"DROP TABLE {table_name}")
            conn.commit()
            print(f"'{table_name}' 테이블이 성공적으로 삭제되었습니다.")
        else:
            print(f"'{table_name}' 테이블이 존재하지 않습니다.")

    def krx_stock_listing(self):
        conn, cur = self._get_db_conn()
        krx_list = fdr.StockListing('KRX-MARCAP')
        krx_list.sort_values(by='Marcap', ascending=False, inplace=True)
        krx_list = krx_list.head(500)
        krx_list['Country'] = 'kr'
        krx_list = krx_list[['Code', 'Name', 'Market', 'Country']]
        krx_list = krx_list.rename(columns={'Code': 'code', 'Name': 'company', 'Market': 'market', 'Country': 'country'})
        
        today = datetime.today().strftime('%Y-%m-%d')
        krx_list['updated_date'] = today

        for r in krx_list.itertuples():
            sql = f"REPLACE INTO comp_info (code, company, market, country, updated_date) VALUES ('{r.code}', \"{r.company.replace('\"', '\"\"')}\", '{r.market}', '{r.country}', '{r.updated_date}')"
            cur.execute(sql)
        conn.commit()
        
    def us_stock_listing(self):
        conn, cur = self._get_db_conn()
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {'User-agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            sp500_list = pd.read_html(response.text)[0]
            sp500_list = sp500_list[['Symbol', 'Security']].rename(columns={'Symbol': 'code', 'Security': 'company'})
            sp500_list['market'] = 'S&P500'
        except Exception as e:
            print(f"S&P 500 목록을 가져오는 데 실패했습니다: {e}")
            return

        sp500_list['country'] = 'us'
        today = datetime.today().strftime('%Y-%m-%d')
        sp500_list['updated_date'] = today

        for r in sp500_list.itertuples():
            company_name = r.company.replace("'", "''")
            sql = f"REPLACE INTO comp_info (code, company, market, country, updated_date) VALUES ('{r.code}', '{company_name}', '{r.market}', '{r.country}', '{r.updated_date}')"
            cur.execute(sql)
        conn.commit()

    def update_comp_info(self, nation='all'):
        conn, cur = self._get_db_conn()
        today = datetime.today().strftime('%Y-%m-%d')

        if nation in ['all', 'kr']:
            sql = "SELECT max(updated_date) FROM comp_info WHERE country = 'kr'"
            cur.execute(sql)
            rs = cur.fetchone()
            
            if rs is None or rs[0] is None or rs[0] < today:
                print("한국 주식 목록을 업데이트합니다.")
                self.krx_stock_listing()
            else:
                print("한국 주식 목록은 최신 상태입니다.")

        if nation in ['all', 'us']:
            sql = "SELECT max(updated_date) FROM comp_info WHERE country = 'us'"
            cur.execute(sql)
            rs = cur.fetchone()
            
            if rs is None or rs[0] is None or rs[0] < today:
                print("미국 주식 목록을 업데이트합니다.")
                self.us_stock_listing()
            else:
                print("미국 주식 목록은 최신 상태입니다.")

    def read_naver(self, code, company, pages_to_fetch):
        df = pd.DataFrame()
        for page in range(1, pages_to_fetch + 1):
            page_df = self._read_naver_page(code, page)
            if page_df is None:
                break
            
            df = pd.concat([df, page_df], ignore_index=True)
            if not page_df['날짜'].empty and pd.to_datetime(page_df['날짜'].iloc[-1]) < datetime(2024, 1, 1):
                break
        
        if df.empty:
            return None

        df.dropna(inplace=True)
        df = df.rename(columns={'날짜': 'date', '종가': 'close', '전일비': 'diff',
                                '시가': 'open', '고가': 'high', '저가': 'low', '거래량': 'volume'})
        
        is_negative = df['diff'].astype(str).str.contains('하락')
        df['diff'] = df['diff'].astype(str).str.replace(r'[^0-9]', '', regex=True)
        df['diff'] = pd.to_numeric(df['diff'], errors='coerce').fillna(0).astype(int)
        df.loc[is_negative, 'diff'] *= -1
        
        for col in ['close', 'open', 'high', 'low', 'volume']:
            clean_str = df[col].astype(str).str.replace(',', '')
            numeric_val = pd.to_numeric(clean_str, errors='coerce').fillna(0)
            df[col] = numeric_val.astype(int)

        df['date'] = pd.to_datetime(df['date'])
        df = df[df['date'] >= datetime(2024,1,1)]
        df = df.sort_values(by='date', ascending=True)
        return df

    def _read_naver_page(self, code, page, retries=3):
        url = f"https://finance.naver.com/item/sise_day.nhn?code={code}&page={page}"
        headers = {'User-agent': 'Mozilla/5.0'}
        for i in range(retries):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                tables = pd.read_html(response.text, header=0)
                if not tables or tables[0].empty:
                    return None

                page_df = tables[0]
                page_df.dropna(inplace=True)
                return page_df if not page_df.empty else None

            except Exception:
                time.sleep(0.5)
        return None

    def read_yfinance(self, code, period=2):
        end_date = datetime.today() + timedelta(days=1)
        if period == 1:
            start_date = end_date - timedelta(days=20)
        else:
            start_date = datetime(2024, 1, 1)

        return self._download_with_retry(code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

    def _download_with_retry(self, code, start, end):
        try:
            df = yf.download(code, start=start, end=end, progress=False)
            if df.empty: raise ValueError("Empty DataFrame")
            return df
        except Exception:
            if '.' in code:
                code_alt = code.replace('.', '-')
                try:
                    df = yf.download(code_alt, start=start, end=end, progress=False)
                    if df.empty: raise ValueError("Empty DataFrame after retry")
                    return df
                except Exception: return None
        return None

    def replace_into_db(self, df, code):
        conn, cur = self._get_db_conn()
        if 'diff' not in df.columns:
            df['diff'] = df['close'].diff().fillna(0)
            
        try:
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['diff'] = df['diff'].astype(float)
            df['volume'] = df['volume'].astype(int)
        except Exception as e:
            print(f"데이터 타입 변환 중 오류 ({code}): {e}")
            return

        for r in df.itertuples():
            date_str = r.Index.strftime('%Y-%m-%d')
            sql = (f"REPLACE INTO daily_price (code, date, open, high, low, close, diff, volume) "
                   f"VALUES ('{code}', '{date_str}', '{r.open}', '{r.high}', '{r.low}', '{r.close}', '{r.diff}', '{r.volume}')")
            cur.execute(sql)
        conn.commit()

    def update_daily_price_by_code(self, code, country):
        """code와 country를 사용하여 특정 종목의 일별 시세를 업데이트합니다."""
        df = None
        if country == 'kr':
            df = self.read_naver(code, "", pages_to_fetch=500)
            if df is not None and not df.empty:
                df.set_index('date', inplace=True)
        elif country == 'us':
            df = self.read_yfinance(code, period=2)
            if df is not None and not df.empty:
                df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in df.columns]

        if df is not None and not df.empty:
            self.replace_into_db(df, code)
            print(f"'{code}' ({country})의 업데이트를 완료했습니다.")
        else:
            print(f"'{code}' ({country})의 데이터를 가져오는 데 실패했습니다.")

    def update_daily_price(self, nation='all', period=1):
        conn, cur = self._get_db_conn()
        if nation == 'stop':
            self.run_update = False
            return
        self.run_update = True
        
        if nation in ['kr', 'all']:
            print("KR 주식 업데이트를 시작합니다.")
            cur.execute("SELECT code, company FROM comp_info WHERE country = 'kr'")
            kr_stocks = cur.fetchall()
            for i, (code, company) in enumerate(kr_stocks):
                if not self.run_update: 
                    break
                df = self.read_naver(code, company, 1 if period == 1 else 500)
                if df is not None and not df.empty:
                    df.set_index('date', inplace=True)
                    self.replace_into_db(df, code)
                    print(f"({i+1}/{len(kr_stocks)}) [{code}] {company} 업데이트 완료.")
                else:
                    print(f"({i+1}/{len(kr_stocks)}) [{code}] {company} 업데이트 실패 (데이터 없음).")

        if nation in ['us', 'all']:
            print("\nUS 주식 업데이트를 시작합니다.")
            cur.execute("SELECT code, company FROM comp_info WHERE country = 'us'")
            us_stocks = cur.fetchall()
            for i, (code, company) in enumerate(us_stocks):
                if not self.run_update: 
                    break
                df = self.read_yfinance(code, period)
                if df is not None and not df.empty:
                    df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in df.columns]
                    self.replace_into_db(df, code)
                    print(f"({i+1}/{len(us_stocks)}) [{code}] {company} 업데이트 완료.")
                else:
                    print(f"({i+1}/{len(us_stocks)}) [{code}] {company} 업데이트 실패 (데이터 없음).")
        
        print("\n모든 일별 시세 업데이트가 완료되었습니다.")
    
    def update_single_stock_all_data(self, company):
        mdb = MarketDB()
        comp_info = mdb.get_comp_info(company)
        
        if comp_info.empty:
            print(f"'{company}' 종목을 찾을 수 없습니다. 종목 목록을 먼저 업데이트 해주세요.")
            return

        code = comp_info.iloc[0]['code']
        country = comp_info.iloc[0]['country']
        
        df = None
        if country == 'kr':
            df = self.read_naver(code, company, pages_to_fetch=500)
            if df is not None and not df.empty:
                df.set_index('date', inplace=True)
        elif country == 'us':
            df = self.read_yfinance(code, period=2)
            if df is not None and not df.empty:
                df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in df.columns]

        if df is not None and not df.empty:
            self.replace_into_db(df, code)
            print(f"'{company}' ({code})의 업데이트를 완료했습니다.")
        else:
            print(f"'{company}' ({code})의 데이터를 가져오는 데 실패했습니다.")

    def run_default_reset(self):
        self.init_db('comp_info')
        self.create_tables(*self._get_db_conn())
        self.execute_daily()

    def execute_daily(self):
        self.update_comp_info('all')
        self.update_daily_price('all', 1)
        self.close_db_conn()

class MarketDB(DBManager):
    def get_comp_info(self, company=None):
        conn, cur = self._get_db_conn()
        if company:
            company_safe = company.replace("'", "''").lower()
            sql = f"SELECT * FROM comp_info WHERE lower(company) LIKE '%{company_safe}%' or lower(code) = '{company_safe}'"
        else:
            sql = "SELECT * FROM comp_info"
        return pd.read_sql(sql, conn)

    def get_daily_price(self, company, start_date=None, end_date=None):
        comp_info = self.get_comp_info(company)
        if comp_info.empty:
            return pd.DataFrame()
            
        code = comp_info.iloc[0]['code']
        name = comp_info.iloc[0]['company']
        
        conn, cur = self._get_db_conn()
        
        if start_date and end_date:
            sql = f"SELECT * FROM daily_price WHERE code = '{code}' AND date BETWEEN '{start_date}' AND '{end_date}'"
        elif start_date:
            sql = f"SELECT * FROM daily_price WHERE code = '{code}' AND date >= '{start_date}'"
        else:
            sql = f"SELECT * FROM daily_price WHERE code = '{code}'"
        
        df = pd.read_sql(sql, conn)
        if not df.empty:
            df.index = pd.to_datetime(df.date)
        return df

if __name__ == '__main__':
    dbu = DBUpdater()
    dbu.execute_daily()