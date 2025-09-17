import pandas as pd
import DBUpdater_new
from threading import Lock
from tqdm import tqdm
import FinanceDataReader as fdr # 실시간 데이터 조회를 위해 추가

class DataManager:
    def __init__(self):
        self.db_updater = DBUpdater_new.DBUpdater()
        self.market_db = DBUpdater_new.MarketDB()
        self.db_lock = Lock()
        self.run_search = True

    def get_stock_info(self, company):
        """DB에서 종목 정보를 조회하고, 없으면 인터넷에서 검색하여 새로 추가합니다."""
        with self.db_lock:
            # 1. 먼저 로컬 DB에서 기존 방식으로 정보를 조회합니다.
            stock_info_df = self.market_db.get_comp_info(company)
            
            if not stock_info_df.empty:
                # DB에 정보가 있으면 바로 반환
                print(f"DB에서 '{company}' 정보를 찾았습니다.")
                return stock_info_df.iloc[0]['code'], stock_info_df.iloc[0]['country']
            
            # 2. DB에 정보가 없다면 FinanceDataReader를 이용해 인터넷에서 검색합니다.
            print(f"DB에 '{company}' 정보가 없어 인터넷에서 검색합니다.")
            try:
                # 미국(NASDAQ, NYSE, AMEX)과 한국(KRX) 시장에서 종목을 찾습니다.
                markets = ['NASDAQ', 'NYSE', 'AMEX', 'KRX']
                for market in markets:
                    df_stocks = fdr.StockListing(market)
                    # Symbol(티커) 또는 Name(공식 명칭)으로 검색 (대소문자 구분 없음)
                    stock = df_stocks[
                        (df_stocks['Symbol'].str.lower() == company.lower()) | 
                        (df_stocks['Name'].str.lower() == company.lower())
                    ]
                    
                    if not stock.empty:
                        code = stock.iloc[0]['Symbol']
                        name = stock.iloc[0]['Name']
                        country = 'us' if market != 'KRX' else 'kr'
                        
                        print(f"인터넷에서 종목을 찾았습니다: 코드='{code}', 이름='{name}', 국가='{country}'")
                        
                        # 3. 찾은 정보를 DB에 새로 추가합니다.
                        # MarketDB 클래스에 직접 접근하여 SQL을 실행합니다.
                        with self.market_db.conn:
                            self.market_db.conn.execute(
                                "INSERT OR IGNORE INTO company_info (code, company, country) VALUES (?, ?, ?)",
                                (code, name, country)
                            )
                        print(f"'{name}'({code}) 정보를 로컬 DB에 성공적으로 추가했습니다.")
                        
                        # DB에 추가했으므로 해당 종목의 일별 시세도 업데이트합니다.
                        self.db_updater.update_daily_price_by_code(code, country)
                        
                        return code, country
                
                # 4. 모든 시장을 검색해도 종목을 찾지 못한 경우
                print(f"'{company}'에 대한 종목 정보를 인터넷에서도 찾을 수 없습니다.")
                return None, None

            except Exception as e:
                print(f"인터넷에서 종목 정보 조회 중 오류 발생: {e}")
                return None, None


    def get_daily_price(self, company, start_date):
        """종목의 일별 시세를 조회하고 보조지표를 계산합니다."""
        # get_stock_info가 DB에 없는 종목을 자동으로 추가하므로, 이 함수는 수정할 필요가 없습니다.
        code, country = self.get_stock_info(company)
        
        if code is None:
            # get_stock_info에서 최종적으로 종목을 찾지 못한 경우
            return None

        with self.db_lock:
            # get_stock_info를 통해 DB에 종목이 보장되므로, market_db에서 조회합니다.
            # 이 때, 사용자가 입력한 이름(company)이 아닌 DB에 저장된 공식 이름으로 조회해야 할 수 있습니다.
            # MarketDB의 get_daily_price가 code로도 조회가 가능하다면 더 안정적입니다.
            df = self.market_db.get_daily_price(code, start_date)

        if df is None or df.empty:
            return None
        
        return self.calculate_indicators(df)

    # --- 이하 다른 함수들은 기존 코드를 그대로 유지 ---

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
        
        for company in tqdm(stock_list["company"].values, desc=f"{nation.upper()} 종목 탐색 중"):
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

        df = df.dropna()
        return df

    def get_stock_urls(self, code, country):
        """네이버 금융 페이지의 URL 목록을 생성합니다."""
        if country == "kr":
            return [f"https://m.stock.naver.com/domestic/stock/{code}/total"]
        elif country == "us":
            return [
                f"https://m.stock.naver.com/worldstock/stock/{code}/total",
                f"https://m.stock.naver.com/worldstock/stock/{code}.O/total",
                f"https://m.stock.naver.com/worldstock/stock/{code}.K/total"
            ]
        return []