import sys
import os
import time
from threading import Thread, Lock
import pandas as pd
import DBUpdater_new

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from stock_analysis_ui import Ui_MainWindow
from data_manager import DataManager
from chart_manager import ChartManager
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester
from config_manager import ConfigManager
from utils import StdoutRedirect, resource_path

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.console_message_handler = None

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        if self.console_message_handler:
            self.console_message_handler(level, message, lineNumber, sourceId)
        else:
            print(f"JS Console ({level}): {message} at line {lineNumber} in {sourceId}")

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.groupBox_kis.setVisible(False)

        self.data_manager = DataManager()
        self.chart_manager = ChartManager(self.verticalLayout_2, self.verticalLayout_7, self.imagelabel_3)
        self.portfolio_optimizer = PortfolioOptimizer(self.textBrowser, self.verticalLayout_7)
        self.backtester = Backtester(self.textBrowser, self.chart_manager)
        self.config_manager = ConfigManager()
        self.db_updater = DBUpdater_new.DBUpdater()  # DBUpdater 인스턴스 생성

        self.db_lock = Lock()
        self.file_lock = Lock()
        self.run = True
        self.codes = {}
        
        self.current_searched_stock = None
        self.search_condition_text_1 = ""
        self.search_condition_text_2 = ""
        self.search_running = False  # 종목 탐색 실행 플래그


        # 최소 signal connections
        self.btn_find.clicked.connect(self.find_stock)
        self.le_ent.returnPressed.connect(self.find_stock)

        # ListWidget signal connections
        if hasattr(self, 'lb_hold'):
            self.lb_hold.itemDoubleClicked.connect(self.on_list_item_clicked)
        if hasattr(self, 'lb_int'):
            self.lb_int.itemDoubleClicked.connect(self.on_list_item_clicked)
        if hasattr(self, 'lb_search'):
            self.lb_search.itemDoubleClicked.connect(self.on_list_item_clicked)

        # Select Button signal connections
        if hasattr(self, 'btn'):
            self.btn.clicked.connect(lambda: self.on_list_item_clicked(self.lb_search.currentItem()))
        if hasattr(self, 'btn2'):
            self.btn2.clicked.connect(lambda: self.on_list_item_clicked(self.lb_hold.currentItem()))
        if hasattr(self, 'btn3'):
            self.btn3.clicked.connect(lambda: self.on_list_item_clicked(self.lb_int.currentItem()))

        # Backtesting signal connections
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.buyConditionDefaultButton.clicked.connect(self.reset_buy_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.reset_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.reset_sell_condition)
        self.BacktestingButton.clicked.connect(self.run_backtest)
        self.optimize_button.clicked.connect(self.run_portfolio_optimization)

        # Stock Search signal connections
        if hasattr(self, 'btn_search1'):
            self.btn_search1.clicked.connect(lambda: self.filter_search_list('kr'))
        if hasattr(self, 'btn_search2'):
            self.btn_search2.clicked.connect(lambda: self.filter_search_list('us'))
        if hasattr(self, 'btn_search3'):
            self.btn_search3.clicked.connect(lambda: self.filter_search_list('all'))
        if hasattr(self, 'btn_stop2'):
            self.btn_stop2.clicked.connect(self.stop_search)
        if hasattr(self, 'btn_addhold'):
            self.btn_addhold.clicked.connect(lambda: self.add_to_list_from_search('hold'))
        if hasattr(self, 'btn_addint'):
            self.btn_addint.clicked.connect(lambda: self.add_to_list_from_search('interest'))

        # List Box Delete signal connections
        if hasattr(self, 'btn_del1'):
            self.btn_del1.clicked.connect(self.remove_from_hold_list)
        if hasattr(self, 'btn_del2'):
            self.btn_del2.clicked.connect(self.remove_from_interest_list)

        # Search Condition Button signal connections
        if hasattr(self, 'SearchConditionInputButton'):
            self.SearchConditionInputButton.clicked.connect(self.save_search_condition)
        if hasattr(self, 'SearchConditionInputButton_4'):
            self.SearchConditionInputButton_4.clicked.connect(self.reset_search_condition)

        # Cross-List Add signal connections
        if hasattr(self, 'btn_addint1'):
            self.btn_addint1.clicked.connect(self.add_from_hold_to_interest)
        if hasattr(self, 'btn_addhold1'):
            self.btn_addhold1.clicked.connect(self.add_from_interest_to_hold)

        # Find Widget Add signal connections
        if hasattr(self, 'btn_addhold2'):
            self.btn_addhold2.clicked.connect(self.add_from_find_to_hold)
        if hasattr(self, 'btn_addint2'):
            self.btn_addint2.clicked.connect(self.add_from_find_to_interest)

        # Update Button signal connections
        if hasattr(self, 'btn_update1'):
            self.btn_update1.clicked.connect(lambda: self.run_update_thread('kr'))
        if hasattr(self, 'btn_update2'):
            self.btn_update2.clicked.connect(lambda: self.run_update_thread('us'))
        if hasattr(self, 'btn_update3'):
            self.btn_update3.clicked.connect(lambda: self.run_update_thread('all'))
        if hasattr(self, 'btn_stop1'):
            self.btn_stop1.clicked.connect(self.stop_update_thread)
        if hasattr(self, 'btn_update4'):
            self.btn_update4.clicked.connect(self.update_single_stock_ui)


        # stdout 리다이렉션
        self.stdout_redirect = StdoutRedirect()
        self.stdout_redirect.printOccur.connect(self._append_text)
        self.stdout_redirect.start()

        self.initialize_ui()

    def initialize_ui(self):
        self.le_ent.setPlaceholderText("종목코드 또는 종목명 조회")
        
        # 리스트박스 높이 제한
        if hasattr(self, 'lb_search'):
            self.lb_search.setMaximumHeight(150)
        if hasattr(self, 'lb_hold'):
            self.lb_hold.setMaximumHeight(150)
        if hasattr(self, 'lb_int'):
            self.lb_int.setMaximumHeight(150)
        
        try:
            with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except:
            pass

        print("=" * 50)
        print("주식 분석 프로그램이 시작되었습니다.")
        print("=" * 50)

        print("=" * 50)

        self.load_stock_lists()
        self.load_stock_lists()
        self.load_backtest_conditions()
        
        # 백테스팅 시작일 기본값 설정 (1년 전)
        one_year_ago = QtCore.QDate.currentDate().addYears(-1)
        self.dateEdit_start.setDate(one_year_ago)
        
        # 상승주/저가주 버튼 숨기기
        if hasattr(self, 'SearchConditionInputButton_2'):
            self.SearchConditionInputButton_2.hide()
        if hasattr(self, 'SearchConditionInputButton_3'):
            self.SearchConditionInputButton_3.hide()
        
        # 종목 탐색 조건 로딩
        self.load_search_conditions()
        
        # 라디오 버튼 연결
        if hasattr(self, 'radioButton'):
            self.radioButton.toggled.connect(lambda checked: self.on_radio_button_toggled(1) if checked else None)
        if hasattr(self, 'radioButton_2'):
            self.radioButton_2.toggled.connect(lambda checked: self.on_radio_button_toggled(2) if checked else None)

    def load_search_conditions(self):
        """종목 탐색 조건을 파일에서 불러옵니다."""
        try:
            # 상승주 조건 (search_condition_1.txt)
            self.search_condition_1 = self.config_manager.load_condition('search_condition_1.txt')
            if not self.search_condition_1:
                self.search_condition_1 = "(df.RSI.values[-2] < 30 < df.RSI.values[-1] and df.macd.values[-2] < df.macd.values[-1]) or (df.macdhist.values[-2] < 0 < df.macdhist.values[-1])"
                self.config_manager.save_condition('search_condition_1.txt', self.search_condition_1)
            
            # 저가주 조건 (search_condition_2.txt)
            self.search_condition_2 = self.config_manager.load_condition('search_condition_2.txt')
            if not self.search_condition_2:
                self.search_condition_2 = "(df.open.values[-1] < df.ENBOTTOM.values[-1] or df.RSI.values[-1] < 30) and (df.macdhist.values[-2] < df.macdhist.values[-1]) and (df.close.values[-1] > df.open.values[-1])"
                self.config_manager.save_condition('search_condition_2.txt', self.search_condition_2)
            
            # 기본값으로 상승주 조건 표시
            if hasattr(self, 'lineEditSearchCondition'):
                self.lineEditSearchCondition.setText(self.search_condition_1)
                
            # 상승 라디오 버튼을 기본 선택
            if hasattr(self, 'radioButton'):
                self.radioButton.setChecked(True)
                
            print("종목 탐색 조건을 불러왔습니다.")
        except Exception as e:
            print(f"종목 탐색 조건 로딩 실패: {str(e)}")
    
    def on_radio_button_toggled(self, button_id):
        """라디오 버튼 선택 시 해당 조건을 텍스트 필드에 표시합니다."""
        if hasattr(self, 'lineEditSearchCondition'):
            if button_id == 1:  # 상승
                self.lineEditSearchCondition.setText(self.search_condition_1)
            elif button_id == 2:  # 저가
                self.lineEditSearchCondition.setText(self.search_condition_2)

    def load_stock_lists(self):
        """files 폴더의 텍스트 파일에서 종목 리스트를 불러옵니다."""
        try:
            hold_stocks = self.config_manager.load_stock_list('stock_hold.txt')
            interest_stocks = self.config_manager.load_stock_list('stock_interest.txt')
            
            if hasattr(self, 'lb_hold'):
                self.lb_hold.clear()
                self.lb_hold.addItems(hold_stocks)
            
            if hasattr(self, 'lb_int'):
                self.lb_int.clear()
                self.lb_int.addItems(interest_stocks)
            
            # 포트폴리오 입력필드에 보유 종목 자동 입력
            if hasattr(self, 'portfolio'):
                self.portfolio.setText("; ".join(hold_stocks))
                
            print("보유/관심 종목 리스트를 불러왔습니다.")
        except Exception as e:
            print(f"종목 리스트 로딩 실패: {str(e)}")

    def load_backtest_conditions(self):
        """백테스팅 조건식을 불러옵니다."""
        try:
            buy_cond = self.config_manager.load_condition('buy_condition.txt')
            if not buy_cond:
                buy_cond = self.config_manager.save_default_buy_condition()
            self.lineEditBuyCondition.setText(buy_cond)

            sell_cond = self.config_manager.load_condition('sell_condition.txt')
            if not sell_cond:
                sell_cond = self.config_manager.save_default_sell_condition()
            self.lineEditSellCondition.setText(sell_cond)
            print("백테스팅 조건식을 불러왔습니다.")
        except Exception as e:
            print(f"백테스팅 조건식 로딩 실패: {str(e)}")

    def save_buy_condition(self):
        cond = self.lineEditBuyCondition.text()
        self.config_manager.save_condition('buy_condition.txt', cond)
        print("매수 조건식이 저장되었습니다.")

    def reset_buy_condition(self):
        cond = self.config_manager.save_default_buy_condition()
        self.lineEditBuyCondition.setText(cond)
        print("매수 조건식이 초기화되었습니다.")

    def save_sell_condition(self):
        cond = self.lineEditSellCondition.text()
        self.config_manager.save_condition('sell_condition.txt', cond)
        print("매도 조건식이 저장되었습니다.")

    def reset_sell_condition(self):
        cond = self.config_manager.save_default_sell_condition()
        self.lineEditSellCondition.setText(cond)
        self.lineEditSellCondition.setText(cond)
        print("매도 조건식이 초기화되었습니다.")

    def save_search_condition(self):
        """종목 탐색 조건을 저장합니다."""
        try:
            if not hasattr(self, 'lineEditSearchCondition'):
                return
            
            condition = self.lineEditSearchCondition.text()
            
            if hasattr(self, 'radioButton') and self.radioButton.isChecked():
                self.config_manager.save_condition('search_condition_1.txt', condition)
                self.search_condition_1 = condition
                print("상승주 검색 조건이 저장되었습니다.")
            elif hasattr(self, 'radioButton_2') and self.radioButton_2.isChecked():
                self.config_manager.save_condition('search_condition_2.txt', condition)
                self.search_condition_2 = condition
                print("저가주 검색 조건이 저장되었습니다.")
            else:
                print("저장할 조건 유형(상승/저가)을 선택해주세요.")
                
        except Exception as e:
            print(f"조건 저장 중 오류: {str(e)}")

    def reset_search_condition(self):
        """종목 탐색 조건을 초기화합니다."""
        try:
            self.search_condition_1, self.search_condition_2 = self.config_manager.save_default_search_conditions()
            
            if hasattr(self, 'radioButton') and self.radioButton.isChecked():
                self.lineEditSearchCondition.setText(self.search_condition_1)
            elif hasattr(self, 'radioButton_2') and self.radioButton_2.isChecked():
                self.lineEditSearchCondition.setText(self.search_condition_2)
                
            print("검색 조건이 초기화되었습니다.")
        except Exception as e:
            print(f"조건 초기화 중 오류: {str(e)}")

    def run_backtest(self):
        try:
            company = self.lineEdit_stock.text()
            start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")
            buy_cond = self.lineEditBuyCondition.text()
            sell_cond = self.lineEditSellCondition.text()

            if not company:
                print("백테스팅할 종목을 입력해주세요.")
                return

            print(f"백테스팅 시작: {company}, 시작일: {start_date}")
            print(f"매수 조건: {buy_cond}")
            print(f"매도 조건: {sell_cond}")

            # 데이터 업데이트 및 가져오기
            self.update_stock_price(company, 10) # 10년치 데이터
            df = self.data_manager.get_daily_price(company, start_date)

            if df is not None and not df.empty:
                self.backtester.run_backtesting(df, company, start_date, buy_cond, sell_cond)
            else:
                print(f"'{company}'의 데이터를 찾을 수 없습니다.")

        except Exception as e:
            print(f"백테스팅 실행 중 오류 발생: {str(e)}")

    def run_portfolio_optimization(self):
        try:
            portfolio_text = self.portfolio.text()
            if not portfolio_text:
                print("포트폴리오 종목을 입력해주세요.")
                return
            
            if ';' in portfolio_text:
                stock_list = [s.strip() for s in portfolio_text.split(';') if s.strip()]
            else:
                stock_list = [s.strip() for s in portfolio_text.split(',') if s.strip()]

            print(f"포트폴리오 최적화 시작: {stock_list}")
            
            # 각 종목 데이터 업데이트 (필요 시)
            for stock in stock_list:
                self.update_stock_price(stock, 3) # 최근 3년 데이터 (최적화에 충분한 데이터 확보)
                
            self.portfolio_optimizer.optimize_portfolio(stock_list)
            
        except KeyboardInterrupt:
            print("작업이 취소되었습니다.")
        except Exception as e:
            print(f"포트폴리오 최적화 오류: {str(e)}")

    def _append_text(self, msg):
        """로그 위젯에 텍스트를 추가합니다."""
        self.log_widget.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.log_widget.insertPlainText(msg)
        self.log_widget.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def on_list_item_clicked(self, item):
        if item:
            # self.le_ent.setText(item.text())  # 입력 필드 업데이트 하지 않음
            self.find_stock(item.text())

    def find_stock(self, company=None):
        try:
            if company is None:
                company = self.le_ent.text()
            print(f"종목 조회 시작: {company}")
            
            with self.db_lock:
                db_updater = DBUpdater_new.DBUpdater()
                db_updater.update_daily_price("stop")
            
            time.sleep(0.2)
            self.update_stock_price(company, 2)
            
            df = self.data_manager.get_daily_price(company)
            if df is not None and not df.empty:
                self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)
                print(f"'{company}' 차트를 표시했습니다.")
                
                # 웹 페이지 업데이트
                self.update_web_view(company)
            else:
                print(f"'{company}'의 데이터를 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"오류 발생: {str(e)}")

    def update_web_view(self, company):
        """종목에 맞는 네이버 금융 페이지를 웹뷰에 표시합니다."""
        try:
            print(f"웹뷰 업데이트 요청: {company}")
            mk = DBUpdater_new.MarketDB()
            stock_list = mk.get_comp_info(company)
            
            if stock_list.empty:
                if ',' in company:
                    simple_company = company.split(',')[0].strip()
                    stock_list = mk.get_comp_info(simple_company)
            
            if stock_list.empty:
                # 검색 실패 시 검색 페이지로 이동
                url = f"https://m.stock.naver.com/search/index.html?keyword={company}"
                print(f"웹뷰: 종목 정보 없음. 검색 페이지로 이동: {url}")
            else:
                # 정확한 일치가 없으면 첫 번째 결과 사용
                val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]
                if val.empty:
                    val = stock_list.iloc[[0]]
                
                code = val.iloc[0]['code']
                country = val.iloc[0]['country']
                market = val.iloc[0]['market']
                
                print(f"웹뷰 타겟: {company} (Code: {code}, Country: {country}, Market: {market})")

                if country == 'kr':
                    # 네이버 모바일 국내 증권 페이지
                    url = f"https://m.stock.naver.com/domestic/stock/{code}/total"
                elif country == 'us':
                    # 거래소별 접미사 매핑
                    suffix = '.O' # Default to NASDAQ/Other
                    
                    # 예외 케이스 처리
                    if code == 'IONQ':
                        suffix = '.K'
                    elif market == 'NYSE':
                        suffix = '.N'
                    elif market == 'AMEX':
                        suffix = '.A'
                    
                    url = f"https://m.stock.naver.com/worldstock/stock/{code}{suffix}/total"
                else:
                    url = f"https://m.stock.naver.com/search/index.html?keyword={company}"
            
            print(f"웹뷰 URL 설정: {url}")
            if hasattr(self, 'webEngineView'):
                self.webEngineView.setUrl(QtCore.QUrl(url))
                
        except Exception as e:
            print(f"웹뷰 업데이트 오류: {str(e)}")

    def update_stock_price(self, company, period):
        try:
            with self.db_lock:
                mk = DBUpdater_new.MarketDB()
                stock_list = mk.get_comp_info(company)
                
                if stock_list.empty:
                    # 검색 실패 시, 혹시 "Tesla, Inc." 처럼 콤마가 있다면 앞부분만으로 재검색 시도
                    if ',' in company:
                        simple_company = company.split(',')[0].strip()
                        stock_list = mk.get_comp_info(simple_company)

                if stock_list.empty:
                    print(f"'{company}' 종목 정보를 찾을 수 없습니다.")
                    return

                val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]
                if val.empty:
                    # 정확한 일치가 없으면 첫 번째 결과 사용 (유사 검색 결과)
                    val = stock_list.iloc[[0]]
                    
                code = val.iloc[0]['code']
                company_name = val.iloc[0]['company']
                country = val.iloc[0]['country']

                db_updater = DBUpdater_new.DBUpdater()
                
                if country == 'kr':
                    print(f"한국 종목 데이터 업데이트 중: {company_name}({code})")
                    df = db_updater.read_naver_api(code, company_name)
                    if df is not None and not df.empty:
                        df.set_index('date', inplace=True)
                elif country == 'us':
                    print(f"미국 종목 데이터 업데이트 중: {company_name}({code})")
                    df = db_updater.read_yfinance(code, period)
                    if df is not None and not df.empty:
                        # yfinance 데이터의 컬럼명을 소문자로 변환 (Open -> open, Close -> close 등)
                        df.columns = [col.lower() for col in df.columns]
                else:
                    print(f"지원하지 않는 국가: {country}")
                    return
                
                if df is not None and not df.empty:
                    db_updater.replace_into_db(df, code)
                    print(f"'{company_name}' 데이터 업데이트 완료")
                else:
                    print(f"'{company_name}' 데이터를 가져올 수 없습니다.")
                    
        except Exception as e:
            print(f"update_stock_price 오류: {str(e)}")

    def filter_search_list(self, country):
        """선택된 조건(상승/저가)에 맞는 종목을 필터링하여 표시합니다."""
        def run():
            try:
                self.lb_search.clear()
                self.search_running = True
                
                # 선택된 라디오 버튼 확인
                if hasattr(self, 'radioButton') and self.radioButton.isChecked():
                    condition_type = 1  # 상승
                    condition = self.search_condition_1
                elif hasattr(self, 'radioButton_2') and self.radioButton_2.isChecked():
                    condition_type = 2  # 저가
                    condition = self.search_condition_2
                else:
                    print("조건을 선택해주세요.")
                    self.search_running = False
                    return
                
                print(f"{'상승' if condition_type == 1 else '저가'} 조건으로 {country} 종목을 검색합니다...")
                
                mk = DBUpdater_new.MarketDB()
                all_stocks = mk.get_comp_info()
                
                if country == 'kr':
                    all_stocks = all_stocks[all_stocks['country'] == 'kr']
                elif country == 'us':
                    all_stocks = all_stocks[all_stocks['country'] == 'us']
                
                if all_stocks.empty:
                    print("표시할 종목이 없습니다. 먼저 업데이트를 진행해주세요.")
                    self.search_running = False
                    return
                
                # 조건에 맞는 종목 필터링
                matching_stocks = []
                total = len(all_stocks)
                
                for idx, (_, stock) in enumerate(all_stocks.iterrows(), 1):
                    # 중단 확인
                    if not self.search_running:
                        print(f"\n검색이 중단되었습니다. ({len(matching_stocks)}개 종목 발견)")
                        return
                    
                    try:
                        code = stock['code']
                        company = stock['company']
                        
                        # 종목 데이터 가져오기
                        df = mk.get_daily_price(company)
                        
                        if df.empty or len(df) < 30:  # 최소 30일 데이터 필요
                            continue
                        
                        # 기술적 지표 계산
                        df = self.calculate_indicators(df)
                        
                        if df is None or len(df) < 2:
                            continue
                        
                        # 조건 평가
                        try:
                            if eval(condition):
                                # 즉시 리스트 박스에 추가
                                self.lb_search.addItem(company)
                                matching_stocks.append(company)
                                print(f"[{idx}/{total}] {company} - 조건 만족")
                            else:
                                print(f"[{idx}/{total}] {company} - 조건 불만족", end='\r')
                        except Exception as e:
                            print(f"[{idx}/{total}] {company} - 조건 평가 오류: {str(e)}", end='\r')
                            continue
                            
                    except Exception as e:
                        print(f"[{idx}/{total}] {stock.get('company', 'Unknown')} - 처리 오류: {str(e)}", end='\r')
                        continue
                
                # 검색 완료 메시지
                if matching_stocks:
                    print(f"\n검색 완료: {len(matching_stocks)}개 종목이 조건을 만족합니다.")
                else:
                    print("\n조건을 만족하는 종목이 없습니다.")
                    
            except Exception as e:
                print(f"종목 검색 중 오류 발생: {str(e)}")
            finally:
                self.search_running = False
        
        # 백그라운드 스레드에서 실행
        t = Thread(target=run, daemon=True)
        t.start()
    
    def stop_search(self):
        """종목 탐색을 중단합니다."""
        if self.search_running:
            self.search_running = False
            print("종목 탐색 중단 요청됨...")
        else:
            print("실행 중인 탐색이 없습니다.")
    
    def calculate_indicators(self, df):
        """기술적 지표를 계산합니다."""
        try:
            import pandas as pd
            
            # 데이터 복사
            df = df.copy()
            
            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD 계산
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['macdsignal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macdhist'] = df['macd'] - df['macdsignal']
            
            # 엔벨로프 계산 (Envelope Bands)
            df['MA20'] = df['close'].rolling(window=20).mean()
            df['ENTOP'] = df['MA20'] * 1.1  # 상단 밴드 (+10%)
            df['ENBOTTOM'] = df['MA20'] * 0.9  # 하단 밴드 (-10%)
            
            return df
            
        except Exception as e:
            print(f"지표 계산 오류: {str(e)}")
            return None

    def add_to_list_from_search(self, list_type):
        """종목 탐색 리스트에서 선택된 종목을 보유 또는 관심 리스트에 추가합니다."""
        try:
            if not hasattr(self, 'lb_search'):
                return
            
            current_item = self.lb_search.currentItem()
            if not current_item:
                print("추가할 종목을 선택해주세요.")
                return
            
            stock_name = current_item.text()
            
            if list_type == 'hold':
                # 보유 종목 리스트에 추가
                if hasattr(self, 'lb_hold'):
                    # 중복 확인
                    items = [self.lb_hold.item(i).text() for i in range(self.lb_hold.count())]
                    if stock_name not in items:
                        self.lb_hold.addItem(stock_name)
                        # 파일에 저장
                        items.append(stock_name)
                        self.config_manager.save_stock_list('stock_hold.txt', items)
                        print(f"'{stock_name}'을(를) 보유 종목에 추가했습니다.")
                    else:
                        print(f"'{stock_name}'은(는) 이미 보유 종목에 있습니다.")
            
            elif list_type == 'interest':
                # 관심 종목 리스트에 추가
                if hasattr(self, 'lb_int'):
                    # 중복 확인
                    items = [self.lb_int.item(i).text() for i in range(self.lb_int.count())]
                    if stock_name not in items:
                        self.lb_int.addItem(stock_name)
                        # 파일에 저장
                        items.append(stock_name)
                        self.config_manager.save_stock_list('stock_interest.txt', items)
                        print(f"'{stock_name}'을(를) 관심 종목에 추가했습니다.")
                    else:
                        print(f"'{stock_name}'은(는) 이미 관심 종목에 있습니다.")
                        
        except Exception as e:
            print(f"종목 추가 중 오류 발생: {str(e)}")

    def remove_from_hold_list(self):
        """보유 종목 리스트에서 선택된 종목을 삭제합니다."""
        try:
            if not hasattr(self, 'lb_hold'):
                return
            
            current_item = self.lb_hold.currentItem()
            if not current_item:
                print("삭제할 종목을 선택해주세요.")
                return
            
            stock_name = current_item.text()
            
            # 파일에서 삭제
            self.config_manager.remove_stock_from_list('stock_hold.txt', stock_name)
            
            # UI에서 삭제
            row = self.lb_hold.row(current_item)
            self.lb_hold.takeItem(row)
            
            print(f"'{stock_name}'을(를) 보유 종목에서 삭제했습니다.")
            
        except Exception as e:
            print(f"보유 종목 삭제 중 오류 발생: {str(e)}")

    def remove_from_interest_list(self):
        """관심 종목 리스트에서 선택된 종목을 삭제합니다."""
        try:
            if not hasattr(self, 'lb_int'):
                return
            
            current_item = self.lb_int.currentItem()
            if not current_item:
                print("삭제할 종목을 선택해주세요.")
                return
            
            stock_name = current_item.text()
            
            # 파일에서 삭제
            self.config_manager.remove_stock_from_list('stock_interest.txt', stock_name)
            
            # UI에서 삭제
            row = self.lb_int.row(current_item)
            self.lb_int.takeItem(row)
            
            print(f"'{stock_name}'을(를) 관심 종목에서 삭제했습니다.")
            
        except Exception as e:
            print(f"관심 종목 삭제 중 오류 발생: {str(e)}")

    def add_from_hold_to_interest(self):
        """보유 종목 리스트에서 선택된 종목을 관심 종목 리스트에 추가합니다."""
        try:
            if not hasattr(self, 'lb_hold'):
                return
            
            current_item = self.lb_hold.currentItem()
            if not current_item:
                print("관심 종목으로 등록할 보유 종목을 선택해주세요.")
                return
            
            stock_name = current_item.text()
            
            # 관심 종목 리스트에 추가
            if hasattr(self, 'lb_int'):
                # 중복 확인
                items = [self.lb_int.item(i).text() for i in range(self.lb_int.count())]
                if stock_name not in items:
                    self.lb_int.addItem(stock_name)
                    # 파일에 저장
                    items.append(stock_name)
                    self.config_manager.save_stock_list('stock_interest.txt', items)
                    print(f"'{stock_name}'을(를) 관심 종목에 추가했습니다.")
                else:
                    print(f"'{stock_name}'은(는) 이미 관심 종목에 있습니다.")
                    
        except Exception as e:
            print(f"관심 종목 추가 중 오류 발생: {str(e)}")

    def add_from_interest_to_hold(self):
        """관심 종목 리스트에서 선택된 종목을 보유 종목 리스트에 추가합니다."""
        try:
            if not hasattr(self, 'lb_int'):
                return
            
            current_item = self.lb_int.currentItem()
            if not current_item:
                print("보유 종목으로 등록할 관심 종목을 선택해주세요.")
                return
            
            stock_name = current_item.text()
            
            # 보유 종목 리스트에 추가
            if hasattr(self, 'lb_hold'):
                # 중복 확인
                items = [self.lb_hold.item(i).text() for i in range(self.lb_hold.count())]
                if stock_name not in items:
                    self.lb_hold.addItem(stock_name)
                    # 파일에 저장
                    items.append(stock_name)
                    self.config_manager.save_stock_list('stock_hold.txt', items)
                    print(f"'{stock_name}'을(를) 보유 종목에 추가했습니다.")
                else:
                    print(f"'{stock_name}'은(는) 이미 보유 종목에 있습니다.")
                    
        except Exception as e:
            print(f"보유 종목 추가 중 오류 발생: {str(e)}")

    def add_from_find_to_hold(self):
        """종목 조회 입력창의 종목을 보유 종목 리스트에 추가합니다."""
        try:
            stock_name = self.le_ent.text()
            if not stock_name:
                print("추가할 종목을 입력하거나 조회해주세요.")
                return
            
            # 보유 종목 리스트에 추가
            if hasattr(self, 'lb_hold'):
                # 중복 확인
                items = [self.lb_hold.item(i).text() for i in range(self.lb_hold.count())]
                if stock_name not in items:
                    self.lb_hold.addItem(stock_name)
                    # 파일에 저장
                    items.append(stock_name)
                    self.config_manager.save_stock_list('stock_hold.txt', items)
                    print(f"'{stock_name}'을(를) 보유 종목에 추가했습니다.")
                else:
                    print(f"'{stock_name}'은(는) 이미 보유 종목에 있습니다.")
                    
        except Exception as e:
            print(f"보유 종목 추가 중 오류 발생: {str(e)}")

    def add_from_find_to_interest(self):
        """종목 조회 입력창의 종목을 관심 종목 리스트에 추가합니다."""
        try:
            stock_name = self.le_ent.text()
            if not stock_name:
                print("추가할 종목을 입력하거나 조회해주세요.")
                return
            
            # 관심 종목 리스트에 추가
            if hasattr(self, 'lb_int'):
                # 중복 확인
                items = [self.lb_int.item(i).text() for i in range(self.lb_int.count())]
                if stock_name not in items:
                    self.lb_int.addItem(stock_name)
                    # 파일에 저장
                    items.append(stock_name)
                    self.config_manager.save_stock_list('stock_interest.txt', items)
                    print(f"'{stock_name}'을(를) 관심 종목에 추가했습니다.")
                else:
                    print(f"'{stock_name}'은(는) 이미 관심 종목에 있습니다.")
                    
        except Exception as e:
            print(f"관심 종목 추가 중 오류 발생: {str(e)}")

    def run_update_thread(self, nation):
        """DB 업데이트를 별도 스레드에서 실행합니다."""
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            print("이미 업데이트가 진행 중입니다.")
            return

        print(f"'{nation}' 종목 업데이트를 시작합니다...")
        self.update_thread = Thread(target=self._run_update, args=(nation,), daemon=True)
        self.update_thread.start()

    def _run_update(self, nation):
        try:
            # 먼저 종목 목록 업데이트
            self.db_updater.update_comp_info(nation)
            # 그 다음 시세 업데이트
            self.db_updater.update_daily_price(nation)
        except Exception as e:
            print(f"업데이트 중 오류 발생: {e}")

    def stop_update_thread(self):
        """DB 업데이트를 중단합니다."""
        print("업데이트 중단 요청...")
        self.db_updater.update_daily_price('stop')

    def update_single_stock_ui(self):
        """개별 종목 업데이트 (UI 버튼 연결용)"""
        try:
            if not hasattr(self, 'ent_stock'):
                return
            
            company = self.ent_stock.text()
            if not company:
                print("업데이트할 종목명/코드를 입력해주세요.")
                return
            
            print(f"'{company}' 업데이트 요청...")
            # 별도 스레드에서 실행하여 UI 프리징 방지
            t = Thread(target=self.db_updater.update_single_stock_all_data, args=(company,), daemon=True)
            t.start()
            
        except Exception as e:
            print(f"개별 종목 업데이트 오류: {str(e)}")


    def closeEvent(self, event):
        """애플리케이션 종료 시 리소스 정리"""
        if hasattr(self, 'stdout_redirect'):
            self.stdout_redirect.stop()
        super().closeEvent(event)
