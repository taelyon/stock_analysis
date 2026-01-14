import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from bs4 import BeautifulSoup
import requests
import re
import yfinance as yf
import exchange_calendars as xcals
import warnings
import json
import threading
import time
import concurrent.futures

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
                code TEXT PRIMARY KEY, company TEXT, market TEXT, country TEXT, updated_date TEXT,
                marcap REAL, changes_ratio REAL
            );"""
        cur.execute(sql_comp_info)
        conn.commit()
        
        # 기존 테이블에 컬럼이 없을 경우 추가 (마이그레이션)
        try:
            cur.execute("ALTER TABLE comp_info ADD COLUMN marcap REAL")
        except:
            pass
        try:
            cur.execute("ALTER TABLE comp_info ADD COLUMN changes_ratio REAL")
        except:
            pass
        try:
            cur.execute("ALTER TABLE comp_info ADD COLUMN sector TEXT")
        except:
            pass

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
        
        # 1. KRX 주식 (KRX-MARCAP)
        print("KRX 주식 목록(KRX-MARCAP) 다운로드 중...")
        krx_list = fdr.StockListing('KRX-MARCAP')
        krx_list.sort_values(by='Marcap', ascending=False, inplace=True)
        krx_list = krx_list.head(500) # 시가총액 상위 500개
        krx_list['Country'] = 'kr'
        
        krx_list = krx_list[['Code', 'Name', 'Market', 'Country', 'Marcap', 'ChagesRatio']]
        krx_list = krx_list.rename(columns={
            'Code': 'code', 'Name': 'company', 'Market': 'market', 'Country': 'country',
            'Marcap': 'marcap', 'ChagesRatio': 'changes_ratio'
        })

        # 2. KRX ETF (ETF/KR)
        print("KRX ETF 목록(ETF/KR) 다운로드 중...")
        etf_list = fdr.StockListing('ETF/KR')
        etf_list['Country'] = 'kr'
        etf_list['Market'] = 'ETF'
        
        # ETF 데이터 컬럼 매핑 ('ChangeRate' -> 'changes_ratio' 등 확인 필요)
        # ETF/KR Columns: ['Symbol', 'Category', 'Name', 'Price', 'RiseFall', 'Change', 'ChangeRate', 'NAV', 'EarningRate', 'Volume', 'Amount', 'MarCap']
        # ChangeRate가 %단위인지 확인 필요. 보통 FDR에서 ChangeRate는 %일 수 있음. KRX-MARCAP의 ChagesRatio도 %임.
        
        etf_list = etf_list[['Symbol', 'Name', 'Market', 'Country', 'MarCap', 'ChangeRate']]
        etf_list = etf_list.rename(columns={
            'Symbol': 'code', 'Name': 'company', 'Market': 'market', 'Country': 'country',
            'MarCap': 'marcap', 'ChangeRate': 'changes_ratio'
        })
        
        # 병합
        combined_list = pd.concat([krx_list, etf_list], ignore_index=True)
        
        today = datetime.today().strftime('%Y-%m-%d')
        combined_list['updated_date'] = today

        print(f"총 {len(combined_list)}개 종목(주식+ETF)을 DB에 저장합니다.")

        for r in combined_list.itertuples():
            # marcap과 changes_ratio 추가 저장
            # NaN 처리
            marcap = r.marcap if pd.notnull(r.marcap) else 0
            changes_ratio = r.changes_ratio if pd.notnull(r.changes_ratio) else 0
            
            sql = f"""
                REPLACE INTO comp_info (code, company, market, country, updated_date, marcap, changes_ratio) 
                VALUES ('{r.code}', "{r.company.replace('"', '""')}", '{r.market}', '{r.country}', '{r.updated_date}', {marcap}, {changes_ratio})
            """
            cur.execute(sql)
        conn.commit()

        
    def us_stock_listing(self):
        """ S&P 500 종목을 가져오되, market 열에는 실제 상장 거래소를 표시합니다. """
        conn, cur = self._get_db_conn()
        
        # 1. 모든 미국 거래소의 전체 종목 목록을 가져와 조회용 테이블 생성
        print("미국 전체 거래소 목록을 조회합니다 (NASDAQ, NYSE, AMEX)...")
        market_map = {}
        for market in ['NASDAQ', 'NYSE', 'AMEX']:
            try:
                market_df = fdr.StockListing(market)
                market_map.update(pd.Series(market, index=market_df.Symbol).to_dict())
                print(f"{market} 목록 조회 완료.")
            except Exception as e:
                print(f"{market} 목록 조회 실패: {e}")
        
        # 2. S&P 500 종목 목록 가져오기
        print("S&P 500 목록을 가져옵니다...")
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {'User-agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            tables = pd.read_html(response.text)
            
            sp500_list = None
            for df in tables:
                if 'Symbol' in df.columns and 'Security' in df.columns:
                    sp500_list = df
                    break
            
            if sp500_list is None:
                print("S&P 500 테이블을 찾을 수 없습니다.")
                return

            sp500_list = sp500_list[['Symbol', 'Security']].rename(columns={'Symbol': 'code', 'Security': 'company'})
        except Exception as e:
            print(f"S&P 500 목록을 가져오는 데 실패했습니다: {e}")
            return

        # 3. S&P 500 목록에 실제 거래소 정보 매핑
        sp500_list['market'] = sp500_list['code'].map(market_map)

        unmatched_symbols = sp500_list['market'].isna()
        if unmatched_symbols.any():
            print("일부 종목의 거래소 정보를 다시 조회합니다 (심볼 형식 변경)...")
            normalized_codes = sp500_list.loc[unmatched_symbols, 'code'].str.replace('.', '-', regex=False)
            sp500_list.loc[unmatched_symbols, 'market'] = normalized_codes.map(market_map)

        sp500_list['market'].fillna('N/A', inplace=True)
        
        sp500_list['country'] = 'us'
        today = datetime.today().strftime('%Y-%m-%d')
        sp500_list['updated_date'] = today

        # 4. DB에 저장
        print("S&P 500 종목 정보를 실제 거래소 정보와 함께 DB에 저장합니다.")
        for r in sp500_list.itertuples():
            company_name = r.company.replace("'", "''")
            sql = f"REPLACE INTO comp_info (code, company, market, country, updated_date) VALUES ('{r.code}', '{company_name}', '{r.market}', '{r.country}', '{r.updated_date}')"
            cur.execute(sql)
        conn.commit()

        na_count = (sp500_list['market'] == 'N/A').sum()
        print(f"총 {len(sp500_list)}개의 S&P 500 종목 정보 업데이트를 완료했습니다. (거래소 정보 N/A: {na_count}개)")

    def update_sector_info(self):
        """네이버 금융에서 업종 정보를 크롤링하여 DB에 업데이트합니다."""
        print("업종 정보를 업데이트합니다 (네이버 금융 크롤링)...")
        conn, cur = self._get_db_conn()
        
        try:
            url = 'https://finance.naver.com/sise/sise_group.nhn?type=upjong'
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 업종 링크 추출
            sector_links = soup.select('table.type_1 tr td a')
            
            total_sectors = len(sector_links)
            print(f"총 {total_sectors}개의 업종을 발견했습니다.")
            
            for i, link in enumerate(sector_links):
                sector_name = link.text
                sector_url = 'https://finance.naver.com' + link['href']
                
                # 업종 상세 페이지에서 종목 코드 추출
                try:
                    res = requests.get(sector_url)
                    s = BeautifulSoup(res.text, 'html.parser')
                    stocks = s.select('div.name_area a')
                    
                    for stock in stocks:
                        # href에서 code 추출 (/item/main.naver?code=000000)
                        code = stock['href'].split('code=')[-1]
                        
                        # DB 업데이트
                        sql = f"UPDATE comp_info SET sector = '{sector_name}' WHERE code = '{code}'"
                        cur.execute(sql)
                        
                except Exception as e:
                    print(f"업종 '{sector_name}' 처리 중 오류: {e}")
                
                if (i + 1) % 10 == 0:
                    print(f"업종 정보 업데이트 진행 중... ({i + 1}/{total_sectors})")
                    
            conn.commit()
            print("업종 정보 업데이트가 완료되었습니다.")
            
        except Exception as e:
            print(f"업종 정보 업데이트 실패: {e}")

    def update_comp_info(self, nation='all'):
        conn, cur = self._get_db_conn()
        today = datetime.today().strftime('%Y-%m-%d')

        if nation in ['all', 'kr']:
            # 날짜 확인
            sql_date = "SELECT max(updated_date) FROM comp_info WHERE country = 'kr'"
            cur.execute(sql_date)
            rs_date = cur.fetchone()
            
            # 데이터 누락 확인 (marcap이 없는 경우)
            sql_check = "SELECT count(*) FROM comp_info WHERE country = 'kr' AND marcap IS NULL"
            cur.execute(sql_check)
            rs_check = cur.fetchone()
            missing_data = rs_check[0] > 0 if rs_check else False
            
            if rs_date is None or rs_date[0] is None or rs_date[0] < today or missing_data:
                print("한국 주식 목록을 업데이트합니다. (최신화 또는 데이터 보강)")
                self.krx_stock_listing()
                self.update_sector_info() # 업종 정보 업데이트 추가
            else:
                print("한국 주식 목록은 최신 상태입니다.")
                # 업종 정보 누락 확인
                sql_sector = "SELECT count(*) FROM comp_info WHERE country = 'kr' AND sector IS NULL"
                cur.execute(sql_sector)
                if cur.fetchone()[0] > 0:
                     print("업종 정보가 누락되어 업데이트를 진행합니다.")
                     self.update_sector_info()

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

    def read_naver_api(self, code, company):
        """네이버 금융 API를 직접 호출하여 시세 데이터를 빠르게 가져옵니다."""
        try:
            # 2024년 이후 데이터는 약 250거래일 미만이므로 count=3000은 충분한 값입니다.
            url = f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime=20240101&endTime=20991231&timeframe=day&count=3000"
            headers = {'User-agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # 첫 줄의 불필요한 문자열 제거 후 JSON 파싱
            data = response.text.strip().replace("'", '"').replace("(", "").replace(")", "")
            data = re.sub(r'([a-zA-Z_]+):', r'"\1":', data) # 키 값을 쌍따옴표로 감싸기
            
            parsed_data = json.loads(data)
            
            df = pd.DataFrame(parsed_data[1:], columns=parsed_data[0])
            df = df.rename(columns={'날짜': 'date', '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'})
            
            df['date'] = pd.to_datetime(df['date'])
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.dropna(subset=numeric_cols, inplace=True)
            df = df.sort_values(by='date', ascending=True).reset_index(drop=True)
            return df
        except Exception as e:
            print(f"[{code}] 네이버 API 호출 중 오류: {e}")
            return None

    def read_yfinance(self, code, period=2):
        end_date = datetime.today() + timedelta(days=1)
        if period == 1:
            start_date = end_date - timedelta(days=20)
        else:
            start_date = datetime(2024, 1, 1)

        return self._download_yfinance_data(code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

    def _download_yfinance_data(self, code, start, end):
        """yfinance를 사용하여 데이터를 다운로드하고, 실패 시 티커를 변경하여 재시도합니다."""
        # 첫 번째 시도
        try:
            ticker = yf.Ticker(code)
            df = ticker.history(start=start, end=end, auto_adjust=False)
            if not df.empty:
                return df
        except Exception as e:
            # yfinance 내부 오류는 무시하고 재시도 로직으로 넘어갑니다.
            pass

        # 티커 변경 후 재시도 (예: BRK.B -> BRK-B)
        try:
            code_alt = code.replace('.', '-')
            ticker_alt = yf.Ticker(code_alt)
            df_alt = ticker_alt.history(start=start, end=end, auto_adjust=False)
            return df_alt if not df_alt.empty else None
        except Exception as e:
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
            print(f"[{code}] 데이터 타입 변환 중 오류: {e}")
            return

        for r in df.itertuples():
            date_str = r.Index.strftime('%Y-%m-%d')
            sql = (f"REPLACE INTO daily_price (code, date, open, high, low, close, diff, volume) "
                   f"VALUES ('{code}', '{date_str}', '{r.open}', '{r.high}', '{r.low}', '{r.close}', '{r.diff}', '{r.volume}')")
            try:
                cur.execute(sql)
            except sqlite3.Error as e:
                print(f"[{code}] DB 저장 중 오류: {e}")
                return
        conn.commit()

    def update_daily_price_by_code(self, code, country, period=2):
        """code와 country를 사용하여 특정 종목의 일별 시세를 업데이트합니다."""
        if not self.run_update:
            return f"[{code}] 업데이트 중단됨."

        df = None
        if country == 'kr':
            df = self.read_naver_api(code, "")
            if df is not None and not df.empty:
                df.set_index('date', inplace=True)
        elif country == 'us':
            df = self.read_yfinance(code, period=period)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
                df = df[['Open', 'High', 'Low', 'Close', 'Volume']] 
                df.columns = ['open', 'high', 'low', 'close', 'volume']

        if df is not None and not df.empty:
            self.replace_into_db(df, code)
            return f"[{code}] ({country}) 업데이트 완료."
        else:
            return f"[{code}] ({country}) 데이터 없음. 업데이트 실패."

    def update_daily_price(self, nation='all', period=1):
        if nation == 'stop':
            self.run_update = False
            return
        self.run_update = True

        conn, cur = self._get_db_conn()
        cur.execute("SELECT code, country FROM comp_info")
        stocks = [(code, country) for code, country in cur.fetchall() if nation == 'all' or nation == country]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.update_daily_price_by_code, code, country, period) for code, country in stocks]
            
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                if not self.run_update:
                    print("\n[알림] 사용자에 의해 업데이트가 중단되었습니다. 남은 작업을 취소합니다...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                try:
                    result = future.result()
                    print(f"({i}/{len(stocks)}) {result}")
                except Exception as e:
                    print(f"({i}/{len(stocks)}) 에러 발생: {e}")

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
            df = self.read_naver_api(code, company)
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
        
        return df

class MarketDB(DBManager):
    def get_comp_info(self, company=None):
        conn, cur = self._get_db_conn()
        if company:
            company_safe = company.replace("'", "''").lower()
            sql = f"SELECT * FROM comp_info WHERE lower(company) = '{company_safe}' or lower(code) = '{company_safe}'"
            df = pd.read_sql(sql, conn)
            
            if df.empty:
                sql = f"SELECT * FROM comp_info WHERE lower(company) LIKE '%{company_safe}%' or lower(code) LIKE '%{company_safe}%'"
                df = pd.read_sql(sql, conn)
            return df
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
