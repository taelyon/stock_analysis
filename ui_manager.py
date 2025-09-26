from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineProfile
from data_manager import DataManager
from chart_manager import ChartManager
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester
from config_manager import ConfigManager
# ==================== 수정된 코드 시작 ====================
# resource_path 함수를 import 합니다.
from utils import StdoutRedirect, resource_path
# ===================== 수정된 코드 끝 =====================
from stock_analysis_ui import Ui_MainWindow
from threading import Thread
import traceback

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.console_message_handler = None

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        if self.console_message_handler:
            self.console_message_handler(level, message, lineNumber, sourceId)


class UIManager(QtWidgets.QMainWindow, Ui_MainWindow):
    graphUpdated = QtCore.Signal(str)
    try:
        def __init__(self):
            super().__init__()
            self.setupUi(self)

            self.data_manager = DataManager()
            self.chart_manager = ChartManager(self.verticalLayout_2, self.verticalLayout_7, self.imagelabel_3)
            self.portfolio_optimizer = PortfolioOptimizer(self.textBrowser, self.verticalLayout_7)
            self.backtester = Backtester(self.textBrowser, self.chart_manager)
            self.config_manager = ConfigManager()

            self.url_attempts = []
            self.current_attempt = 0
            self.error_detected = False
            self.current_searched_stock = None
            self.current_searched_code = None
            self.current_searched_stock_formal_name = None
            self.render_failure_count = 0
            self.mobile_home_url = QtCore.QUrl("https://m.stock.naver.com/")

            self.max_render_failures = 3
            self.page = None
            self.mobile_profile = None
            self.webEngineView.loadFinished.connect(self.handle_load_finished)

            self.connect_signals()
            self.initialize_ui()

            self._stdout = StdoutRedirect()
            self._stdout.start()
            self._stdout.printOccur.connect(lambda x: self._append_text(x))

        def connect_signals(self):
            # (시그널 연결 코드는 변경 없음)
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
            self.lineEdit_stock.returnPressed.connect(self.run_backtesting)
            self.optimize_button.clicked.connect(self.run_portfolio_optimization)
            self.tabWidget.currentChanged.connect(self.on_tab_changed)

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
            self.webEngineView.renderProcessTerminated.connect(self.handle_render_process_terminated)

        def initialize_ui(self):
            self.ent_stock.setPlaceholderText("종목코드 또는 종목명")
            self.le_ent.setPlaceholderText("종목코드 또는 종목명 조회")
            self.lineEdit_stock.setPlaceholderText("백테스팅 할 종목")
            self.portfolio.setPlaceholderText("쉼표(,)로 종목 구분")
            self.lineEditSearchCondition.setPlaceholderText("예: (PER < 15) and (PBR < 1)")
            self.lineEditBuyCondition.setPlaceholderText("예: (c > o) and (v > 100000)")
            self.lineEditSellCondition.setPlaceholderText("예: (c < o)")

            try:
                # ==================== 수정된 코드 시작 ====================
                # 스타일시트 경로도 resource_path를 사용합니다.
                with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                # imagelabel_3에 이미지를 동적으로 설정합니다.
                pixmap = QtGui.QPixmap(resource_path("files/stock market data analysis program.jpg"))
                self.imagelabel_3.setPixmap(pixmap)
                # ===================== 수정된 코드 끝 =====================
            except FileNotFoundError:
                print("스타일시트 또는 이미지 파일을 찾을 수 없습니다.")
            except Exception as e:
                print(f"리소스 로딩 중 오류 발생: {e}")

            self._reset_mobile_profile(rebuild=True)
            settings = self.webEngineView.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

            self.webEngineView.setUrl(self.mobile_home_url)
            self.dateEdit_start.setDate(QtCore.QDate(2024, 1, 1))

            self.load_stock_lists()
            self.lineEditBuyCondition.setText(self.config_manager.load_condition('buy_condition.txt'))
            self.lineEditSellCondition.setText(self.config_manager.load_condition('sell_condition.txt'))
            search_cond1, search_cond2 = self.config_manager.load_search_conditions()
            self.lineEditSearchCondition.setText(search_cond1)
            self.search_condition_text_1 = search_cond1
            self.search_condition_text_2 = search_cond2
            self.radioButton.setChecked(True)
            self.update_portfolio_textbox()
        
        # (이하 나머지 코드는 변경 없음)
        def _create_mobile_profile(self):
            """모바일 페이지 로딩에 최적화된 QWebEngineProfile을 생성합니다."""
            profile = QWebEngineProfile(self)
            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
            profile.setHttpAcceptLanguage("ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7")

            # User-Agent를 최신 안드로이드 크롬 버전으로 변경합니다.
            new_user_agent = (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.7339.124 Mobile Safari/537.36"
            )
            profile.setHttpUserAgent(new_user_agent)

            return profile

        def _apply_profile_to_view(self, profile):
            """새로운 프로필을 웹뷰에 적용하고 관련 핸들러를 재연결합니다."""
            if hasattr(self, "page") and self.page is not None:
                try:
                    self.page.deleteLater()
                except RuntimeError:
                    pass

            # [FIX] 사용자 정의 WebEnginePage 클래스를 사용합니다.
            self.page = CustomWebEnginePage(profile, self)
            self.page.console_message_handler = self.handle_js_console_message
            self.webEngineView.setPage(self.page)


        def _reset_mobile_profile(self, rebuild=False):
            """모바일 페이지용 프로필을 초기화하거나 캐시를 정리합니다."""
            if rebuild or self.mobile_profile is None:
                if getattr(self, "mobile_profile", None) is not None:
                    try:
                        self.mobile_profile.deleteLater()
                    except RuntimeError:
                        pass
                self.mobile_profile = self._create_mobile_profile()
            else:
                self.mobile_profile.clearHttpCache()
                cookie_store = self.mobile_profile.cookieStore()
                if cookie_store is not None:
                    cookie_store.deleteAllCookies()

            self._apply_profile_to_view(self.mobile_profile)

        def handle_render_process_terminated(self, process, status):
            """웹페이지 렌더링 프로세스가 다운되면 자동으로 페이지를 다시 로드하는 함수입니다."""
            self.render_failure_count += 1
            print(
                f"WebEngine 렌더링 프로세스가 예기치 않게 종료되었습니다. 페이지를 다시 불러옵니다. "
                f"(재시도 {self.render_failure_count}/{self.max_render_failures})"
            )

            if self.render_failure_count < self.max_render_failures:
                self.webEngineView.reload()
            else:
                print("반복적인 크래시가 감지되어 모바일 기본 페이지로 전환합니다.")
                self.current_attempt = 0
                self.error_detected = False
                self.webEngineView.setUrl(self.mobile_home_url)

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

        def closeEvent(self, event):
            """Ensure WebEngine resources are released before the window closes."""
            try:
                if getattr(self, 'webEngineView', None) is not None:
                    self.webEngineView.setPage(None)
            except Exception:
                pass

            page = getattr(self, 'page', None)
            if page is not None:
                try:
                    page.deleteLater()
                except RuntimeError:
                    pass
                self.page = None

            profile = getattr(self, 'mobile_profile', None)
            if profile is not None:
                try:
                    cookie_store = profile.cookieStore()
                    if cookie_store is not None:
                        cookie_store.deleteAllCookies()
                except Exception:
                    pass
                try:
                    profile.deleteLater()
                except RuntimeError:
                    pass
                self.mobile_profile = None

            super().closeEvent(event)
        def run_portfolio_optimization(self):
            stock_names = self.portfolio.text().split(',')
            stock_names = [name.strip() for name in stock_names if name.strip()]
            start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")
            self.portfolio_optimizer.optimize_portfolio(stock_names, start_date)

        def on_tab_changed(self, index):
            backtesting_widget = getattr(self, 'tab_2', None)
            if backtesting_widget is None:
                return

            backtesting_index = self.tabWidget.indexOf(backtesting_widget)
            if index != backtesting_index:
                return

            company = getattr(self, 'current_searched_stock', None)
            if not company:
                for list_widget in (self.lb_search, self.lb_hold, self.lb_int):
                    current_item = list_widget.currentItem()
                    if current_item:
                        candidate = current_item.text().strip()
                        if candidate:
                            company = candidate
                            break
            if not company:
                return

            self.lineEdit_stock.setText(company)
            self.run_backtesting()
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
            # get_stock_info가 market, formal_name 정보도 반환하도록 수정
            code, country, market, formal_name = self.data_manager.get_stock_info(company)
            if code and country:
                self.current_searched_code = code
                self.current_searched_stock_formal_name = formal_name
                # get_stock_urls에 market 정보를 전달
                self.url_attempts = self.data_manager.get_stock_urls(code, country, market)
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
            network_error_signals = ["CORS", "NetworkError", "net::ERR", "Failed to load resource"]
            if any(keyword in message for keyword in network_error_signals):
                self.error_detected = True

        def handle_load_finished(self, ok):
            if not ok or self.error_detected:
                self.current_attempt += 1
                if self.current_attempt < len(self.url_attempts):
                    self.error_detected = False
                    print(f"페이지 로드 실패, 재시도 {self.current_attempt}/{len(self.url_attempts)}")
                    self.webEngineView.setUrl(QtCore.QUrl(self.url_attempts[self.current_attempt]))
                else:
                    print("모든 URL 시도 실패, 기본 페이지로 대체")
                    self.error_detected = False
                    self.webEngineView.setUrl(self.mobile_home_url)
                    self.current_attempt = 0 # 기본 페이지 로드 후 시도 횟수 초기화
                return

            # 페이지 로드가 성공적으로 완료된 후, 5초 뒤에 JS를 실행하여 '로딩중' 요소가 있는지 확인
            self.render_failure_count = 0
            QtCore.QTimer.singleShot(5000, lambda: self.page.runJavaScript("""
                (function() {
                    // '로딩중' 텍스트를 포함하는 모든 요소를 찾습니다.
                    const elements = document.body.innerText;
                    return elements.includes('로딩중') ? 'loading' : 'complete';
                })();
            """, self.on_js_complete))

        def on_js_complete(self, result):
            # 'loading' 상태이고, 재시도 횟수가 3회 미만일 경우
            if result == 'loading' and self.current_attempt < 3:
                self.current_attempt += 1
                print(f"부분 로드 감지, 재시도 {self.current_attempt}/3")
                self.webEngineView.reload() # 페이지 새로고침
            # 'complete' 상태이거나 재시도 횟수를 초과한 경우
            elif result == 'complete':
                if self.current_searched_stock_formal_name and self.current_searched_code:
                    print(f"{self.current_searched_stock_formal_name}({self.current_searched_code}) 조회가 완료되었습니다.")
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
                if not target_list.findItems(company_to_add, QtCore.Qt.MatchFlag.MatchExactly):
                    target_list.addItem(company_to_add)
                    self.config_manager.add_stock_to_list(filename, company_to_add)
                    if list_type == 'hold': # 보유 종목에 추가되면 포트폴리오 업데이트
                        self.update_portfolio_textbox()
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
                
                if list_type == 'hold': # 보유 종목에서 삭제되면 포트폴리오 업데이트
                    self.update_portfolio_textbox()
            else:
                list_name_map = {'hold': '보유', 'interest': '관심'}
                print(f"{list_name_map.get(list_type, '')} 목록에서 삭제할 항목이 선택되지 않았습니다.")

        def _append_text(self, msg):
            self.log_widget.moveCursor(QtGui.QTextCursor.MoveOperation.End)
            self.log_widget.insertPlainText(msg)

        def select_item_in_list(self, target_list_widget):
            selected_item = target_list_widget.currentItem()
            if selected_item:
                self.stock_list_item_clicked(selected_item)
            else:
                print(f"리스트에서 선택된 종목이 없습니다.")

        def update_portfolio_textbox(self):
            """보유 종목 리스트(lb_hold)의 내용을 포트폴리오 텍스트박스(portfolio)에 업데이트합니다."""
            # lb_hold 리스트 위젯의 모든 아이템을 가져옵니다.
            items = [self.lb_hold.item(i).text() for i in range(self.lb_hold.count())]
            # 쉼표로 구분된 하나의 문자열로 합칩니다.
            portfolio_text = ", ".join(items)
            # portfolio 텍스트박스에 설정합니다.
            self.portfolio.setText(portfolio_text)

    except Exception as e:
        print(f"UIManager 초기화 중 오류 발생: {e}")
        raise