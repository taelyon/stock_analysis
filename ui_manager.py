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
import traceback

class UIManager(QMainWindow):
    graphUpdated = QtCore.pyqtSignal(str)
    try:
        def __init__(self):
            super().__init__()
            uic.loadUi('stock_analysis.ui', self)
            
            self.data_manager = DataManager()
            self.chart_manager = ChartManager(self.verticalLayout_2, self.verticalLayout_7, self.imagelabel_3)
            self.portfolio_optimizer = PortfolioOptimizer(self.textBrowser, self.verticalLayout_7)
            self.backtester = Backtester(self.textBrowser, self.chart_manager)
            self.config_manager = ConfigManager()

            self.url_attempts = []
            self.current_attempt = 0
            self.error_detected = False
            self.current_searched_stock = None

            self.page = QWebEnginePage()
            self.webEngineView.setPage(self.page)
            self.page.javaScriptConsoleMessage = self.handle_js_console_message
            self.webEngineView.loadFinished.connect(self.handle_load_finished)
            
            self.connect_signals()
            self.initialize_ui()

            self._stdout = StdoutRedirect()
            self._stdout.start()
            self._stdout.printOccur.connect(lambda x: self._append_text(x))

        def connect_signals(self):
            self.btn_update1.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "kr"))
            self.btn_update2.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "us"))
            self.btn_update3.clicked.connect(lambda: self.start_thread(self.data_manager.update_stocks, "all"))
            self.btn_stop1.clicked.connect(self.data_manager.stop_update)
            self.btn_update4.clicked.connect(self.update_specific_stock)
            self.ent_stock.returnPressed.connect(self.update_specific_stock)
            self.btn_search1.clicked.connect(lambda: self.start_thread(self.search_stock, "kr"))
            self.btn_search2.clicked.connect(lambda: self.start_thread(self.search_stock, "us"))
            self.btn_search3.clicked.connect(lambda: self.start_thread(self.search_stock, "all"))
            self.btn_stop2.clicked.connect(self.stop_search)
            self.btn_find.clicked.connect(self.find_stock)
            self.le_ent.returnPressed.connect(self.find_stock)
            self.BacktestingButton.clicked.connect(self.run_backtesting)
            self.optimize_button.clicked.connect(self.run_portfolio_optimization)

            self.SearchConditionInputButton.clicked.connect(self.save_search_condition)
            self.SearchConditionInputButton_2.clicked.connect(self.load_search_condition_1)
            self.SearchConditionInputButton_3.clicked.connect(self.load_search_condition_2)
            self.SearchConditionInputButton_4.clicked.connect(self.save_default_search_conditions)
            self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
            self.buyConditionDefaultButton.clicked.connect(self.save_default_buy_condition)
            self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
            self.sellConditionDefaultButton.clicked.connect(self.save_default_sell_condition)

            self.lb_search.itemClicked.connect(self.stock_list_item_clicked)
            self.lb_hold.itemClicked.connect(self.stock_list_item_clicked)
            self.lb_int.itemClicked.connect(self.stock_list_item_clicked)

            self.btn_addhold.clicked.connect(lambda: self.add_stock_to_list('hold'))
            self.btn_addhold1.clicked.connect(lambda: self.add_stock_to_list('hold'))
            self.btn_addhold2.clicked.connect(lambda: self.add_stock_to_list('hold'))
            self.btn_addint.clicked.connect(lambda: self.add_stock_to_list('interest'))
            self.btn_addint1.clicked.connect(lambda: self.add_stock_to_list('interest'))
            self.btn_addint2.clicked.connect(lambda: self.add_stock_to_list('interest'))

            # [MODIFIED] 삭제 버튼 기능 연결
            self.btn_del1.clicked.connect(lambda: self.remove_stock_from_list('hold'))
            self.btn_del2.clicked.connect(lambda: self.remove_stock_from_list('interest'))

            # 리스트 그룹들의 '선택' 버튼 기능 연결
            self.btn.clicked.connect(lambda: self.select_item_in_list(self.lb_search))
            self.btn2.clicked.connect(lambda: self.select_item_in_list(self.lb_hold))
            self.btn3.clicked.connect(lambda: self.select_item_in_list(self.lb_int))
            self.btn_find.clicked.connect(self.find_stock)

        def initialize_ui(self):
            self.webEngineView.setUrl(QtCore.QUrl("https://m.stock.naver.com/"))
            self.dateEdit_start.setDate(QtCore.QDate(2024, 1, 1))

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
            self.data_manager.run_search = False

        def update_search_list(self, company):
            self.lb_search.addItem(company)

        def find_stock(self):
            company = self.le_ent.text()
            
            # 입력값이 비어있는지 확인
            if not company.strip():
                print("조회할 종목명을 입력해주세요.")
                return

            df = self.data_manager.get_daily_price(company, "2024-01-01")
            
            if df is not None and not df.empty:
                self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)
            
            # show_stock_info는 DB에 종목이 성공적으로 추가된 후에만 호출되도록 df 조회 이후로 순서를 유지
            self.show_stock_info(company)
            self.current_searched_stock = company

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
            # 1. 클릭된 항목이 속한 리스트(source_list)를 확인합니다.
            source_list = item.listWidget()

            # 2. 프로그램에 있는 모든 리스트(lb_search, lb_hold, lb_int)를 확인하면서
            #    방금 클릭한 source_list가 아닌 다른 리스트들의 선택을 해제합니다.
            for list_widget in [self.lb_search, self.lb_hold, self.lb_int]:
                if list_widget is not source_list:
                    list_widget.clearSelection()

            # 3. 원래 함수가 하던 작업을 그대로 수행합니다.
            company = item.text()
            try:
                df = self.data_manager.get_daily_price(company, "2024-01-01")
                
                if df is not None and not df.empty:
                    self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)
                else:
                    print(f"'{company}'의 차트 데이터를 가져올 수 없습니다.")
                    self.chart_manager.plot_stock_chart(None, company, "", "")

                self.show_stock_info(company)
                self.current_searched_stock = company

            except Exception as e:
                print(f"종목 '{company}' 클릭 처리 중 오류 발생: {e}")

        def show_stock_info(self, company):
            code, country = self.data_manager.get_stock_info(company)
            if code and country:
                self.url_attempts = self.data_manager.get_stock_urls(code, country)
                if self.url_attempts:
                    self.current_attempt = 0
                    self.error_detected = False
                    self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))
                else:
                    print(f"URL을 생성할 수 없습니다: {company}")
            else:
                print(f"종목 정보를 가져올 수 없습니다: {company}")

        def handle_js_console_message(self, level, message, lineNumber, sourceID):
            if "409" in message or "Request failed with status code 409" in message:
                self.error_detected = True

        def handle_load_finished(self, ok):
            if not ok or self.error_detected:
                self.current_attempt += 1
                if self.current_attempt < len(self.url_attempts):
                    self.error_detected = False
                    self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))

        def load_stock_lists(self):
            hold_stocks = self.config_manager.load_stock_list('stock_hold.txt')
            interest_stocks = self.config_manager.load_stock_list('stock_interest.txt')
            self.lb_hold.addItems(hold_stocks)
            self.lb_int.addItems(interest_stocks)

        def add_stock_to_list(self, list_type):
            print(f"\n[버튼 클릭] '{list_type}' 목록 추가 버튼이 눌렸습니다.")
            
            # 버튼을 누르는 시점의 'current_searched_stock' 변수 값을 확인합니다.
            print(f"==> [상태 확인] 현재 'current_searched_stock' 변수의 값: '{self.current_searched_stock}'")

            target_list = self.lb_hold if list_type == 'hold' else self.lb_int
            filename = f'stock_{list_type}.txt'
            
            company_to_add = self.current_searched_stock

            if company_to_add:
                if not target_list.findItems(company_to_add, QtCore.Qt.MatchExactly):
                    target_list.addItem(company_to_add)
                    self.config_manager.add_stock_to_list(filename, company_to_add)
                    print(f"==> [작업 완료] '{company_to_add}'을(를) 목록에 성공적으로 추가했습니다.")
                else:
                    print(f"==> [작업 중단] '{company_to_add}'은(는) 이미 목록에 존재합니다.")
            else:
                print("==> [작업 중단] 추가할 종목에 대한 정보가 없습니다. 먼저 종목을 클릭해주세요.")

        def remove_stock_from_list(self, list_type):
            """지정된 리스트에서 선택된 아이템을 삭제하고, 과정을 로그로 출력합니다."""
            list_widget = None
            filename = None

            if list_type == 'hold':
                list_widget = self.lb_hold
                filename = 'stock_hold.txt'
            elif list_type == 'interest':
                list_widget = self.lb_int
                filename = 'stock_interest.txt'
            
            if list_widget:
                selected_item = list_widget.currentItem()
                if selected_item:
                    item_text = selected_item.text()
                    
                    row = list_widget.row(selected_item)
                    list_widget.takeItem(row)
                    
                    if filename:
                        self.config_manager.remove_stock_from_list(filename, item_text)
                    else:
                        print("! 오류: 파일명이 지정되지 않았습니다.")
                else:
                    list_name_map = {'hold': '보유', 'interest': '관심'}
                    print(f"! 경고: {list_name_map.get(list_type, '')} 목록에서 삭제할 항목이 선택되지 않았습니다.")

        def _append_text(self, msg):
            self.log_widget.moveCursor(QtGui.QTextCursor.End)
            self.log_widget.insertPlainText(msg)

        def select_item_in_list(self, target_list_widget):
            """주어진 리스트 위젯에서 현재 선택된 아이템에 대한 클릭 이벤트를 트리거합니다."""
            selected_item = target_list_widget.currentItem()
            if selected_item:
                self.stock_list_item_clicked(selected_item)
            else:
                print(f"리스트에서 선택된 종목이 없습니다.")
    except Exception as e:
        print(f"UIManager 초기화 중 오류 발생: {e}")
        raise

