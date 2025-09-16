import pandas as pd
import DBUpdater_new
from threading import Lock

class DataManager:
    def __init__(self):
        self.db_updater = DBUpdater_new.DBUpdater()
        self.market_db = DBUpdater_new.MarketDB()
        self.db_lock = Lock()
        self.run_search = True

    def update_stocks(self, nation):
        with self.db_lock:
            self.db_updater.update_comp_info(nation)
            self.db_updater.update_daily_price(nation, 1)

    def stop_update(self):
        self.db_updater.update_daily_price("stop")

    def update_specific_stock(self, company):
        with self.db_lock:
            if company == 'default':
                self.db_updater.init_db()
                self.db_updater.update_comp_info('all')
                self.db_updater.update_daily_price('all', 2)
            else:
                self.update_stock_price(company, 2)

    def update_stock_price(self, company, period):
        with self.db_lock:
            stock_list = self.market_db.get_comp_info(company)
            val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]
            
            # 로컬 DB에 회사 정보가 없으면, 전체 종목 리스트를 갱신하고 다시 시도합니다.
            if val.empty:
                print(f"'{company}' not found in local DB. Updating company list...")
                # 한국 주식 시장을 기준으로 업데이트합니다.
                self.db_updater.update_comp_info('kr') 
                # 회사 정보를 다시 조회합니다.
                stock_list = self.market_db.get_comp_info(company)
                val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]

            if not val.empty:
                code = val.iloc[0]['code']
                country = val.iloc[0]['country']
                df = None
                if country == 'kr':
                    df = self.db_updater.read_naver(code, period)
                elif country == 'us':
                    self.db_updater.ric_code()
                    df = self.db_updater.read_yfinance(code, period)
                
                if df is not None:
                    self.db_updater.replace_into_db(df, 0, code, company)
            else:
                # 갱신 후에도 종목을 찾을 수 없는 경우, 에러를 발생시킵니다.
                raise ValueError(f"'{company}' could not be found even after updating the company list.")

    def search_stock(self, nation, search_condition, callback):
        self.run_search = True
        stock_list = self.prepare_stock_data(nation)
        for idx in range(len(stock_list)):
            if not self.run_search:
                break
            company = stock_list["company"].values[idx]
            df = self.get_daily_price(company, "2022-01-01")
            if df is not None and not df.empty:
                try:
                    if eval(search_condition):
                        callback(company)
                except Exception as e:
                    print(f"Error evaluating search condition for {company}: {e}")

    def stop_search(self):
        self.run_search = False

    def prepare_stock_data(self, nation):
        with self.db_lock:
            stock_list = self.market_db.get_comp_info()
        stock_list["len_code"] = stock_list.code.str.len()
        if nation in ["us", "kr"]:
            idx = (stock_list[stock_list.len_code == 6].index if nation == "us"
                   else stock_list[stock_list.len_code < 6].index)
            stock_list = stock_list.drop(idx)
        return stock_list

    def get_daily_price(self, company, start_date):
        """
        종목의 일별 시세를 조회합니다. 
        정보가 없을 경우 자동으로 갱신 후 다시 조회하는 안정적인 로직입니다.
        """
        # 1. DB에 종목 정보가 있는지 먼저 확인합니다.
        code, _ = self.get_stock_info(company)

        # 2. 종목 정보가 없으면, 종목 목록과 가격을 업데이트합니다.
        if code is None:
            print(f"Company '{company}' not found in DB. Triggering update...")
            try:
                # update_stock_price는 종목 정보 갱신과 가격 갱신을 모두 처리합니다.
                self.update_stock_price(company, 2)
            except ValueError as e:
                # 업데이트 후에도 종목을 찾지 못하면, 치명적인 오류로 간주합니다.
                print(f"FATAL: Could not retrieve data for '{company}' even after update. Error: {e}")
                return None

        # 3. 이제 종목 정보가 있으므로, 가격 데이터를 조회합니다.
        with self.db_lock:
            df = self.market_db.get_daily_price(company, start_date)

        # 4. 가격 데이터가 없으면, 가격만 다시 업데이트합니다.
        if df is None or df.empty:
            print(f"No price data found for '{company}'. Attempting price update...")
            try:
                # 가격만 업데이트하기 위해 period=2로 설정
                self.update_stock_price(company, 2)
                with self.db_lock:
                    df = self.market_db.get_daily_price(company, start_date)
            except ValueError as e:
                print(f"ERROR: Could not update price for '{company}'. Error: {e}")
                return None

        # 5. 최종적으로 데이터가 있으면 보조지표를 계산하여 반환합니다.
        if df is not None and not df.empty:
            return self.calculate_indicators(df)
        
        # 모든 시도 후에도 데이터가 없으면 None을 반환합니다.
        print(f"WARNING: No data returned for '{company}' after all attempts.")
        return None

    def calculate_indicators(self, df):
        # 이동평균
        for period in [5, 10, 12, 20, 26, 60, 130]:
            df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        # 볼린저 밴드
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['STD20'] = df['close'].rolling(window=20).std()
        df['Bollinger_Upper'] = df['MA20'] + (2 * df['STD20'])
        df['Bollinger_Lower'] = df['MA20'] - (2 * df['STD20'])

        # 엔벨로프
        df['ENTOP'] = df['MA20'] + df['MA20'] * 0.1
        df['ENBOTTOM'] = df['MA20'] - df['MA20'] * 0.1

        # 수익률
        for period in [1, 5, 20]:
            df[f'RET{period}'] = ((df["close"].pct_change(period)) * 100).round(1)

        # RSI
        df['U'] = df['close'].diff().clip(lower=0)
        df['D'] = -df['close'].diff().clip(upper=0)
        df['RS'] = (df['U'].ewm(span=14, adjust=False).mean() / df['D'].ewm(span=14, adjust=False).mean())
        df['RSI'] = 100 - (100 / (1 + df['RS']))
        df['RSI_SIGNAL'] = df['RSI'].rolling(window=14).mean()

        # MACD
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macdhist'] = df['macd'] - df['signal']

        # 스토캐스틱
        ndays_high = df.high.rolling(window=14, min_periods=1).max()
        ndays_low = df.low.rolling(window=14, min_periods=1).min()
        df['fast_k'] = (df.close - ndays_low) / (ndays_high - ndays_low) * 100
        df['slow_d'] = df['fast_k'].rolling(window=3).mean()

        df = df.dropna()
        df.index = pd.to_datetime(df.date)
        return df

    def get_stock_info(self, company):
        with self.db_lock:
            stock_list = self.market_db.get_comp_info()
        val = stock_list[(stock_list["company"] == company) | (stock_list["code"] == company)]
        if not val.empty:
            return val.iloc[0]["code"], val.iloc[0]["country"]
        return None, None

    def get_stock_urls(self, code, country):
        """
        네이버 금융 페이지의 가능한 URL 목록을 생성합니다.
        미국 주식의 경우, 나스닥(.O) 등 다양한 형식을 시도합니다.
        """
        if country == "kr":
            return [f"https://m.stock.naver.com/domestic/stock/{code}/total"]
        elif country == "us":
            return [
                f"https://m.stock.naver.com/worldstock/stock/{code}/total",
                f"https://m.stock.naver.com/worldstock/stock/{code}.O/total", # NASDAQ
                f"https://m.stock.naver.com/worldstock/stock/{code}.K/total"  # NYSE 등
            ]
        return []

