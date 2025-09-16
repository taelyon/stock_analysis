from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from data_manager import DataManager
from chart_manager import ChartManager
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester
from config_manager import ConfigManager
from utils import StdoutRedirect
from threading import Thread

class UIManager(QMainWindow):
    graphUpdated = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        uic.loadUi('stock_analysis.ui', self)
        
        self.data_manager = DataManager()
        self.chart_manager = ChartManager(self.verticalLayout_2, self.verticalLayout_7, self.imagelabel_3)
        self.portfolio_optimizer = PortfolioOptimizer(self.textBrowser, self.verticalLayout_7)
        # Backtester 생성 시, layout 대신 chart_manager 인스턴스를 직접 전달합니다.
        self.backtester = Backtester(self.textBrowser, self.chart_manager)
        self.config_manager = ConfigManager()

        # WebEngineView 상태 관리를 위한 변수 초기화
        self.url_attempts = []
        self.current_attempt = 0
        self.error_detected = False

        # 자바스크립트 콘솔 메시지를 감지할 수 있도록 QWebEnginePage를 설정
        self.page = QWebEnginePage()
        self.webEngineView.setPage(self.page)
        self.page.javaScriptConsoleMessage = self.handle_js_console_message
        self.webEngineView.loadFinished.connect(self.handle_load_finished)
        
        self.connect_signals()
        self.initialize_ui()

        # 로그 리디렉션
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self._append_text(x))

    def connect_signals(self):
        # 버튼 연결
        self.btn_update1.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "kr"))
        self.btn_update2.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "us"))
        self.btn_update3.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "all"))
        self.btn_stop1.clicked.connect(lambda: self.data_manager.stop_update())
        self.btn_update4.clicked.connect(lambda: self.start_thread(self.data_manager.update_specific_stock, self.ent_stock.text()))
        self.ent_stock.returnPressed.connect(self.update_specific_stock)
        self.btn_search1.clicked.connect(lambda: self.start_thread(self.search_stock, "kr"))
        self.btn_search2.clicked.connect(lambda: self.start_thread(self.search_stock, "us"))
        self.btn_search3.clicked.connect(lambda: self.start_thread(self.search_stock, "all"))
        self.btn_stop2.clicked.connect(self.stop_search)
        self.btn_find.clicked.connect(self.find_stock)
        self.le_ent.returnPressed.connect(self.find_stock)
        self.BacktestingButton.clicked.connect(self.run_backtesting)
        self.optimize_button.clicked.connect(self.run_portfolio_optimization)

        # 설정 저장/불러오기 버튼
        self.SearchConditionInputButton.clicked.connect(self.save_search_condition)
        self.SearchConditionInputButton_2.clicked.connect(self.load_search_condition_1)
        self.SearchConditionInputButton_3.clicked.connect(self.load_search_condition_2)
        self.SearchConditionInputButton_4.clicked.connect(self.save_default_search_conditions)
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.buyConditionDefaultButton.clicked.connect(self.save_default_buy_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.save_default_sell_condition)

        # 리스트 위젯 아이템 클릭
        self.lb_search.itemClicked.connect(self.stock_list_item_clicked)
        self.lb_hold.itemClicked.connect(self.stock_list_item_clicked)
        self.lb_int.itemClicked.connect(self.stock_list_item_clicked)

        # 보유/관심 종목 추가/삭제
        self.btn_addhold.clicked.connect(lambda: self.add_stock_to_list('hold'))
        self.btn_addint.clicked.connect(lambda: self.add_stock_to_list('interest'))
        self.btn_del1.clicked.connect(lambda: self.remove_stock_from_list('hold'))
        self.btn_del2.clicked.connect(lambda: self.remove_stock_from_list('interest'))

    def initialize_ui(self):
        self.webEngineView.setUrl(QtCore.QUrl("https://m.stock.naver.com/"))
        self.dateEdit_start.setDate(QtCore.QDate(2023, 1, 1))

        # 설정 파일 로드
        self.load_stock_lists()
        self.lineEditBuyCondition.setText(self.config_manager.load_condition('buy_condition.txt'))
        self.lineEditSellCondition.setText(self.config_manager.load_condition('sell_condition.txt'))
        search_cond1, search_cond2 = self.config_manager.load_search_conditions()
        self.lineEditSearchCondition.setText(search_cond1)
        self.search_condition_text_1 = search_cond1
        self.search_condition_text_2 = search_cond2
        self.radioButton.setChecked(True)

    def start_thread(self, func, *args):
        Thread(target=func, args=args, daemon=True).start()

    def update_specific_stock(self):
        self.start_thread(self.data_manager.update_specific_stock, self.ent_stock.text())

    def search_stock(self, nation):
        self.lb_search.clear()
        self.data_manager.search_stock(nation, self.lineEditSearchCondition.text(), self.update_search_list)

    def stop_search(self):
        self.data_manager.stop_search()

    def update_search_list(self, company):
        self.lb_search.addItem(company)

    def find_stock(self):
        company = self.le_ent.text()
        df = self.data_manager.get_daily_price(company, "2022-01-01")
        if df is not None and not df.empty:
            self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)
        self.show_stock_info(company)

    def run_backtesting(self):
        company = self.lineEdit_stock.text()
        start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")
        buy_condition = self.lineEditBuyCondition.text()
        sell_condition = self.lineEditSellCondition.text()
        df = self.data_manager.get_daily_price(company, start_date)
        if df is not None and not df.empty:
            self.backtester.run_backtesting(df, company, start_date, buy_condition, sell_condition)

    def run_portfolio_optimization(self):
        stock_names = self.portfolio.text().split(',')
        stock_names = [name.strip() for name in stock_names if name.strip()]
        self.portfolio_optimizer.optimize_portfolio(stock_names)

    def save_search_condition(self):
        if self.radioButton.isChecked():
            self.search_condition_text_1 = self.lineEditSearchCondition.text()
            self.config_manager.save_condition('search_condition_1.txt', self.search_condition_text_1)
        else:
            self.search_condition_text_2 = self.lineEditSearchCondition.text()
            self.config_manager.save_condition('search_condition_2.txt', self.search_condition_text_2)
        print("탐색 조건 저장 완료")

    def load_search_condition_1(self):
        self.lineEditSearchCondition.setText(self.search_condition_text_1)

    def load_search_condition_2(self):
        self.lineEditSearchCondition.setText(self.search_condition_text_2)

    def save_default_search_conditions(self):
        self.search_condition_text_1, self.search_condition_text_2 = self.config_manager.save_default_search_conditions()
        self.lineEditSearchCondition.setText(self.search_condition_text_1)
        print("기본 탐색 조건 저장 완료")

    def save_buy_condition(self):
        self.config_manager.save_condition('buy_condition.txt', self.lineEditBuyCondition.text())
        print("매수 조건 저장 완료")

    def save_default_buy_condition(self):
        self.lineEditBuyCondition.setText(self.config_manager.save_default_buy_condition())
        print("기본 매수 조건 저장 완료")

    def save_sell_condition(self):
        self.config_manager.save_condition('sell_condition.txt', self.lineEditSellCondition.text())
        print("매도 조건 저장 완료")

    def save_default_sell_condition(self):
        self.lineEditSellCondition.setText(self.config_manager.save_default_sell_condition())
        print("기본 매도 조건 저장 완료")
        
    def stock_list_item_clicked(self, item):
        company = item.text()
        df = self.data_manager.get_daily_price(company, "2022-01-01")
        if df is not None and not df.empty:
            self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)
        self.show_stock_info(company)

    def show_stock_info(self, company):
        code, country = self.data_manager.get_stock_info(company)
        if code and country:
            self.url_attempts = self.data_manager.get_stock_urls(code, country)
            if self.url_attempts:
                self.current_attempt = 0
                self.error_detected = False
                print(f"Attempting to load URL: {self.url_attempts[self.current_attempt]}")
                self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))
            else:
                print(f"No valid URL could be generated for {company}.")
        else:
            print(f"Could not get stock info for {company}.")

    def handle_js_console_message(self, level, message, lineNumber, sourceID):
        # 409 Conflict 에러를 감지하여 다음 URL을 시도하도록 플래그 설정
        if "409" in message or "Request failed with status code 409" in message:
            print("Detected 409 Conflict, will try next URL.")
            self.error_detected = True

    def handle_load_finished(self, ok):
        # 페이지 로드가 실패했거나 409 에러가 감지된 경우
        if not ok or self.error_detected:
            self.current_attempt += 1
            if self.current_attempt < len(self.url_attempts):
                # 시도할 다음 URL이 남아있으면 로드
                print(f"Load failed. Attempting next URL: {self.url_attempts[self.current_attempt]}")
                self.error_detected = False  # 새 시도를 위해 플래그 초기화
                self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))
            else:
                print(f"All URL attempts failed for the current stock.")
        else:
            # 페이지 로드 성공
            print("Page loaded successfully.")

    def load_stock_lists(self):
        hold_stocks = self.config_manager.load_stock_list('stock_hold.txt')
        interest_stocks = self.config_manager.load_stock_list('stock_interest.txt')
        self.lb_hold.addItems(hold_stocks)
        self.lb_int.addItems(interest_stocks)

    def add_stock_to_list(self, list_type):
        selected_item = self.lb_search.currentItem()
        if selected_item:
            company = selected_item.text()
            if list_type == 'hold':
                self.lb_hold.addItem(company)
                self.config_manager.add_stock_to_list('stock_hold.txt', company)
            elif list_type == 'interest':
                self.lb_int.addItem(company)
                self.config_manager.add_stock_to_list('stock_interest.txt', company)

    def remove_stock_from_list(self, list_type):
        if list_type == 'hold':
            list_widget = self.lb_hold
            filename = 'stock_hold.txt'
        elif list_type == 'interest':
            list_widget = self.lb_int
            filename = 'stock_interest.txt'
        else:
            return

        selected_item = list_widget.currentItem()
        if selected_item:
            row = list_widget.row(selected_item)
            list_widget.takeItem(row)
            self.config_manager.remove_stock_from_list(filename, selected_item.text())

    def _append_text(self, msg):
        self.log_widget.moveCursor(QtGui.QTextCursor.End)
        self.log_widget.insertPlainText(msg)

