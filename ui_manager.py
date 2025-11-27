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

        self.db_lock = Lock()
        self.file_lock = Lock()
        self.run = True
        self.codes = {}
        
        self.current_searched_stock = None
        self.search_condition_text_1 = ""
        self.search_condition_text_2 = ""

        # 최소 signal connections
        self.btn_find.clicked.connect(self.find_stock)
        self.le_ent.returnPressed.connect(self.find_stock)

        # ListWidget signal connections
        if hasattr(self, 'lb_hold'):
            self.lb_hold.itemClicked.connect(self.on_list_item_clicked)
        if hasattr(self, 'lb_int'):
            self.lb_int.itemClicked.connect(self.on_list_item_clicked)
        if hasattr(self, 'lb_search'):
            self.lb_search.itemClicked.connect(self.on_list_item_clicked)

        # Backtesting signal connections
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.buyConditionDefaultButton.clicked.connect(self.reset_buy_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.reset_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.reset_sell_condition)
        self.BacktestingButton.clicked.connect(self.run_backtest)
        self.optimize_button.clicked.connect(self.run_portfolio_optimization)

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
            self.le_ent.setText(item.text())
            self.find_stock()

    def find_stock(self):
        try:
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

    def closeEvent(self, event):
        """애플리케이션 종료 시 리소스 정리"""
        if hasattr(self, 'stdout_redirect'):
            self.stdout_redirect.stop()
        super().closeEvent(event)
