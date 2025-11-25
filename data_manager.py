import pandas as pd
import DBUpdater_new
from threading import Lock
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import yfinance as yf
import logging

# yfinance 라이브러리가 생성하는 INFO, WARNING 수준의 로그를 비활성화합니다.
# 이렇게 하면 'possibly delisted'와 같은 메시지가 콘솔에 나타나지 않습니다.
logging.getLogger('yfinance').setLevel(logging.ERROR)

class DataManager:
    def __init__(self):
        self.db_updater = DBUpdater_new.DBUpdater()
        self.market_db = DBUpdater_new.MarketDB()
        self.db_lock = Lock()
        self.run_search = True

    def get_stock_info(self, company):
        """DB에서 종목 정보를 조회하고, 없으면 인터넷에서 검색하여 새로 추가합니다."""
        with self.db_lock:
            stock_info_df = self.market_db.get_comp_info(company)
            if not stock_info_df.empty:
                # market 정보가 없을 수도 있는 구버전 DB 호환을 위해 .get() 사용
                row = stock_info_df.iloc[0]
                market = row.get('market')
                # 정식 회사명(company)을 함께 반환하도록 수정
                return row['code'], row['country'], market, row['company']

            print(f"DB에 '{company}' 정보가 없어 인터넷에서 검색합니다.")
            try:
                markets = ['NASDAQ', 'NYSE', 'AMEX', 'KRX']
                for market_name in markets:
                    df_stocks = fdr.StockListing(market_name)
                    code_col = 'Code' if market_name == 'KRX' else 'Symbol'
                    if code_col not in df_stocks.columns or 'Name' not in df_stocks.columns:
                        continue
                    
                    # BF.B -> BF-B 와 같은 티커 변환을 고려하여 검색 조건 추가
                    search_name = company.lower()
                    search_name_alt = search_name.replace('.', '-')

                    stock = df_stocks[
                        (df_stocks[code_col].str.lower() == search_name) |
                        (df_stocks[code_col].str.lower() == search_name_alt) |
                        (df_stocks['Name'].str.lower() == search_name)
                    ]
                    
                    if not stock.empty:
                        code = stock.iloc[0][code_col]
                        name = stock.iloc[0]['Name']
                        country = 'us' if market_name != 'KRX' else 'kr'
                        
                        print(f"인터넷에서 종목을 찾았습니다: 코드='{code}', 이름='{name}', 국가='{country}', 마켓='{market_name}'")
                        
                        conn, cur = self.market_db._get_db_conn()
                        with conn:
                            cur.execute(
                                "INSERT OR IGNORE INTO comp_info (code, company, country, market) VALUES (?, ?, ?, ?)",
                                (code, name, country, market_name)
                            )
                        # print(f"'{name}'({code}) 정보를 로컬 DB에 성공적으로 추가했습니다.") # UI 피드백과 중복되므로 로그 제거
                        
                        self.db_updater.update_single_stock_all_data(name)
                        # 정식 회사명(name)을 함께 반환하도록 수정
                        return code, country, market_name, name
                
                print(f"'{company}'에 대한 종목 정보를 인터넷에서도 찾을 수 없습니다.")
                return None, None, None, None
            except Exception as e:
                print(f"인터넷에서 종목 정보 조회 중 오류 발생: {e}")
                return None, None, None, None

    def update_recent_stock_data(self, code, country):
        """특정 종목의 최신 시세 데이터를 DB에 덮어쓰기하여 업데이트합니다."""
        try:
            df_new = None
            if country == 'kr':
                # 국내 주식은 네이버 API를 사용합니다.
                df_new = self.db_updater.read_naver_api(code, "")
                if df_new is not None and not df_new.empty:
                    df_new.set_index('date', inplace=True)
            elif country == 'us':
                # 미국 주식은 yfinance를 사용합니다.
                df_new = self.db_updater.read_yfinance(code, period=1) # period=1은 최신 20일 데이터를 의미합니다.
                if df_new is not None and not df_new.empty:
                    # yfinance가 반환하는 대문자 컬럼명을 소문자로 변경합니다.
                    if isinstance(df_new.columns, pd.MultiIndex):
                        df_new.columns = df_new.columns.get_level_values(0)
                    df_new = df_new.loc[:, ~df_new.columns.duplicated(keep='first')]
                    df_new = df_new[['Open', 'High', 'Low', 'Close', 'Volume']]
                    df_new.columns = ['open', 'high', 'low', 'close', 'volume']

            if df_new is None or df_new.empty:
                print(f"'{code}'에 대한 새로운 시세 데이터가 없습니다.")
                return

            # DBUpdater의 replace_into_db를 사용하여 DB에 저장합니다.
            self.db_updater.replace_into_db(df_new, code)

        except Exception as e:
            print(f"'{code}'의 최신 시세 업데이트 중 오류 발생: {e}")

    def get_daily_price(self, company, start_date=None):
        """
        종목의 일별 시세를 조회하고 보조지표를 계산합니다.
        start_date가 없으면 차트용(최신 업데이트 + 3개월 조회), 있으면 해당 날짜부터 조회합니다.
        """
        # get_stock_info 반환값이 4개로 변경됨 (정식 종목명 추가)
        code, country, _, _ = self.get_stock_info(company)
        if code is None:
            return None

        # 차트 조회를 위한 로직
        if start_date is None:
            self.update_recent_stock_data(code, country)
            fetch_start_date = (datetime.now() - timedelta(days=220)).strftime('%Y-%m-%d')
            with self.db_lock:
                df = self.market_db.get_daily_price(code, fetch_start_date)
            
            if df is None or df.empty:
                return None
            
            calculated_df = self.calculate_indicators(df)
            return calculated_df.tail(90)

        # 백테스팅 등 특정 기간 조회를 위한 기존 로직
        with self.db_lock:
            df = self.market_db.get_daily_price(code, start_date)

        if df is None or df.empty:
            return None
        
        return self.calculate_indicators(df)

    def update_stocks(self, nation):
        """최신 10일치 시세 데이터로 업데이트합니다."""
        self.db_updater.update_comp_info(nation)
        self.db_updater.update_daily_price(nation, 1)

    def stop_update(self):
        """시세 업데이트 중지"""
        self.db_updater.run_update = False

    def update_specific_stock(self, company):
        """특정 종목 또는 전체 DB를 업데이트합니다."""
        print(f"'{company}'의 2024년 이후 전체 데이터 업데이트를 시작합니다...")
        if company.lower() == 'default':
            self.db_updater.run_default_reset()
        else:
            self.db_updater.update_single_stock_all_data(company)
        print(f"'{company}'의 전체 데이터 업데이트가 완료되었습니다.")

    def search_stock(self, nation, search_condition, callback):
        """특정 국가의 모든 종목에 대해 주어진 탐색 조건을 평가하고, 조건에 맞는 종목을 콜백으로 반환합니다."""
        self.run_search = True
        stock_list = self.prepare_stock_data(nation)
        
        for company in stock_list["company"].values:
            if not self.run_search:
                print("탐색이 중지되었습니다.")
                break
            
            df = self.get_daily_price(company, "2024-01-01")
            
            if df is not None and not df.empty:
                try:
                    if eval(search_condition, {'pd': pd}, {'df': df}):
                        callback(company)
                except Exception:
                    pass

    def stop_search(self):
        """종목 탐색 중지"""
        self.run_search = False

    def prepare_stock_data(self, nation):
        """탐색을 위해 DB에서 종목 목록을 준비합니다."""
        with self.db_lock:
            stock_list = self.market_db.get_comp_info()
        
        if nation != 'all':
            stock_list = stock_list[stock_list['country'] == nation]
        return stock_list

    def calculate_indicators(self, df):
        """데이터프레임에 보조지표를 계산하여 추가합니다."""
        df['date'] = pd.to_datetime(df.index)

        for period in [5, 10, 12, 20, 26, 60, 130]:
            df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['STD20'] = df['close'].rolling(window=20).std()
        df['Bollinger_Upper'] = df['MA20'] + (2 * df['STD20'])
        df['Bollinger_Lower'] = df['MA20'] - (2 * df['STD20'])

        df['ENTOP'] = df['MA20'] + df['MA20'] * 0.1
        df['ENBOTTOM'] = df['MA20'] - df['MA20'] * 0.1

        for period in [1, 5, 20]:
            df[f'RET{period}'] = ((df["close"].pct_change(period)) * 100).round(1)

        df['U'] = df['close'].diff().clip(lower=0)
        df['D'] = -df['close'].diff().clip(upper=0)
        df['RS'] = (df['U'].ewm(span=14, adjust=False).mean() / df['D'].ewm(span=14, adjust=False).mean())
        df['RSI'] = 100 - (100 / (1 + df['RS']))
        df['RSI_SIGNAL'] = df['RSI'].rolling(window=14).mean()

        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macdhist'] = df['macd'] - df['signal']

        ndays_high = df.high.rolling(window=14, min_periods=1).max()
        ndays_low = df.low.rolling(window=14, min_periods=1).min()
        df['fast_k'] = (df.close - ndays_low) / (ndays_high - ndays_low) * 100
        df['slow_d'] = df['fast_k'].rolling(window=3).mean()

        # [MODIFIED] 캔들 차트 필수 데이터가 없을 때만 행을 삭제하도록 변경
        df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
        return df

    def get_stock_urls(self, code, country, market):
        """네이버 금융 페이지의 URL 목록을 생성합니다."""
        if country == "kr":
            return [f"https://m.stock.naver.com/domestic/stock/{code}/total"]
        
        elif country == "us":
            # market 정보에 따라 적절한 URL을 생성
            if market == 'NASDAQ':
                return [f"https://m.stock.naver.com/worldstock/stock/{code}.O/total"]
            
            elif market == 'NYSE':
                # IONQ와 같은 특정 예외 케이스 처리
                if code == 'IONQ':
                    return [f"https://m.stock.naver.com/worldstock/stock/{code}.K/total"]
                return [f"https://m.stock.naver.com/worldstock/stock/{code}/total"]
            
            elif market == 'AMEX':
                # AMEX는 기본 URL과 .K를 순차 시도
                return [
                    f"https://m.stock.naver.com/worldstock/stock/{code}/total",
                    f"https://m.stock.naver.com/worldstock/stock/{code}.K/total"
                ]

            # market 정보가 없거나(N/A) 예상치 못한 값일 경우, 기존처럼 모든 가능성을 시도
            else:
                return [
                    f"https://m.stock.naver.com/worldstock/stock/{code}/total",
                    f"https://m.stock.naver.com/worldstock/stock/{code}.O/total",
                    f"https://m.stock.naver.com/worldstock/stock/{code}.K/total"
                ]
                
        return []