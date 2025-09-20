from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineSettings, QWebEngineProfile
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

            self.btn_del1.clicked.connect(lambda: self.remove_stock_from_list('hold'))
            self.btn_del2.clicked.connect(lambda: self.remove_stock_from_list('interest'))

            self.btn.clicked.connect(lambda: self.select_item_in_list(self.lb_search))
            self.btn2.clicked.connect(lambda: self.select_item_in_list(self.lb_hold))
            self.btn3.clicked.connect(lambda: self.select_item_in_list(self.lb_int))
            self.btn_find.clicked.connect(self.find_stock)

            # 웹페이지 렌더링 프로세스가 비정상 종료되었을 때의 시그널을 연결합니다.
            self.webEngineView.renderProcessTerminated.connect(self.handle_render_process_terminated)

        def initialize_ui(self):
            # QWebEngineProfile 설정
            profile = QWebEngineProfile("myProfile", self)  # Create a new profile
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36"
            )

            # 기존 QWebEnginePage를 새로운 profile로 교체
            self.page = QWebEnginePage(profile, self.webEngineView)
            self.webEngineView.setPage(self.page)
            self.page.javaScriptConsoleMessage = self.handle_js_console_message
            self.webEngineView.loadFinished.connect(self.handle_load_finished)

            # QWebEngineView 리소스 최적화 설정
            settings = self.webEngineView.settings()
            settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)  # Optional, as needed

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

        def handle_render_process_terminated(self, process, status):
            """웹페이지 렌더링 프로세스가 다운되면 자동으로 페이지를 다시 로드하는 함수입니다."""
            print("WebEngine 렌더링 프로세스가 예기치 않게 종료되었습니다. 페이지를 새로고침합니다.")
            self.webEngineView.reload()

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

            if not company.strip():
                print("조회할 종목명을 입력해주세요.")
                return

            df = self.data_manager.get_daily_price(company)

            if df is not None and not df.empty:
                self.chart_manager.plot_stock_chart(df, company, self.search_condition_text_1, self.search_condition_text_2)

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
            source_list = item.listWidget()

            for list_widget in [self.lb_search, self.lb_hold, self.lb_int]:
                if list_widget is not source_list:
                    list_widget.clearSelection()

            company = item.text()
            try:
                df = self.data_manager.get_daily_price(company)

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
            print(f"JS Console: {level} - {message} at line {lineNumber}")
            if "409" in message or "CORS" in message or "NetworkError" in message:
                self.error_detected = True

        def handle_load_finished(self, ok):
            if not ok or self.error_detected:
                self.current_attempt += 1
                if self.current_attempt < len(self.url_attempts):
                    self.error_detected = False
                    print(f"페이지 로드 실패, 재시도 {self.current_attempt}/{len(self.url_attempts)}")
                    self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))
                else:
                    print("모든 URL 시도 실패, 데스크톱 버전으로 대체")
                    self.webEngineView.setUrl(QtCore.QUrl("https://finance.naver.com/"))
                    self.current_attempt = 0 # 데스크톱 버전 로드 후 시도 횟수 초기화
                return

            # 페이지 로드가 성공적으로 완료된 후, 5초 뒤에 JS를 실행하여 '로딩중' 요소가 있는지 확인
            QtCore.QTimer.singleShot(5000, lambda: self.page.runJavaScript("""
                (function() {
                    // '로딩중' 텍스트를 포함하는 모든 요소를 찾습니다.
                    const elements = document.body.innerText;
                    return elements.includes('로딩중') ? 'loading' : 'complete';
                })();
            """, self.on_js_complete))

        def on_js_complete(self, result):
            print(f"JS 실행 결과: {result}")
            # 'loading' 상태이고, 재시도 횟수가 3회 미만일 경우
            if result == 'loading' and self.current_attempt < 3:
                self.current_attempt += 1
                print(f"부분 로드 감지, 재시도 {self.current_attempt}/3")
                self.webEngineView.reload() # 페이지 새로고침
            # 'complete' 상태이거나 재시도 횟수를 초과한 경우
            elif result == 'complete':
                print("페이지 로드 완료")
                self.current_attempt = 0  # 성공했으므로 재시도 카운터를 초기화합니다.
            else: # 'loading' 이지만 재시도 횟수를 초과했거나, 예기치 않은 결과일 경우
                print("재시도를 중단합니다.")
                self.current_attempt = 0 # 더 이상 시도하지 않도록 카운터 초기화

        def load_stock_lists(self):
            hold_stocks = self.config_manager.load_stock_list('stock_hold.txt')
            interest_stocks = self.config_manager.load_stock_list('stock_interest.txt')
            self.lb_hold.addItems(hold_stocks)
            self.lb_int.addItems(interest_stocks)

        def add_stock_to_list(self, list_type):
            target_list = self.lb_hold if list_type == 'hold' else self.lb_int
            filename = f'stock_{list_type}.txt'

            company_to_add = self.current_searched_stock

            if company_to_add:
                if not target_list.findItems(company_to_add, QtCore.Qt.MatchExactly):
                    target_list.addItem(company_to_add)
                    self.config_manager.add_stock_to_list(filename, company_to_add)
                else:
                    print(f"'{company_to_add}'은(는) 이미 목록에 존재합니다.")
            else:
                print("추가할 종목을 먼저 클릭해주세요.")

        def remove_stock_from_list(self, list_type):
            list_widget = self.lb_hold if list_type == 'hold' else self.lb_int
            filename = f'stock_{list_type}.txt'

            selected_item = list_widget.currentItem()
            if selected_item:
                item_text = selected_item.text()

                row = list_widget.row(selected_item)
                list_widget.takeItem(row)

                if filename:
                    self.config_manager.remove_stock_from_list(filename, item_text)
            else:
                list_name_map = {'hold': '보유', 'interest': '관심'}
                print(f"{list_name_map.get(list_type, '')} 목록에서 삭제할 항목이 선택되지 않았습니다.")

        def _append_text(self, msg):
            self.log_widget.moveCursor(QtGui.QTextCursor.End)
            self.log_widget.insertPlainText(msg)

        def select_item_in_list(self, target_list_widget):
            selected_item = target_list_widget.currentItem()
            if selected_item:
                self.stock_list_item_clicked(selected_item)
            else:
                print(f"리스트에서 선택된 종목이 없습니다.")
    except Exception as e:
        print(f"UIManager 초기화 중 오류 발생: {e}")
        raise