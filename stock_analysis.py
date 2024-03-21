from threading import Thread
from Investar import DBUpdater_new, Analyzer
import pandas as pd
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets, uic
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import *
import backtrader as bt
from matplotlib.figure import Figure


QtWidgets.QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)

class PortfolioOptimization:
    def __init__(self, stock_list):
        self.mk = Analyzer.MarketDB()
        self.stocks = stock_list
        self.df_port = pd.DataFrame()
        # self.optimize_portfolio()

    def optimize_portfolio(self):
        for s in self.stocks:
            self.df_port[s] = self.mk.get_daily_price(s, '2022-01-01')['close']
         
        daily_ret = self.df_port.pct_change(fill_method=None) 
        annual_ret = daily_ret.mean() * 252
        daily_cov = daily_ret.cov() 
        annual_cov = daily_cov * 252

        port_ret = [] 
        port_risk = [] 
        port_weights = []
        sharpe_ratio = [] 

        for _ in range(20000): 
            weights = np.random.random(len(self.stocks)) 
            weights /= np.sum(weights)

            returns = np.dot(weights, annual_ret) 
            risk = np.sqrt(np.dot(weights.T, np.dot(annual_cov, weights))) 
            port_ret.append(returns) 
            port_risk.append(risk) 
            port_weights.append(weights)
            sharpe_ratio.append(returns/risk)

        portfolio = {'Returns': port_ret, 'Risk': port_risk, 'Sharpe': sharpe_ratio}
        for i, s in enumerate(self.stocks): 
            portfolio[s] = [weight[i] for weight in port_weights]

        self.df_port = pd.DataFrame(portfolio) 
        self.df_port = self.df_port[['Returns', 'Risk', 'Sharpe'] + [s for s in self.stocks]]
        self.max_sharpe = self.df_port.loc[self.df_port['Sharpe'] == self.df_port['Sharpe'].max()]  # ③
        self.min_risk = self.df_port.loc[self.df_port['Risk'] == self.df_port['Risk'].min()]  # ④
        
        return self.df_port, self.max_sharpe, self.min_risk
       

class MyStrategy(bt.Strategy):
    def __init__(self, text_browser, lineEditBuyCondition, lineEditSellCondition):
        self.text_browser = text_browser
        self.lineEditBuy = lineEditBuyCondition
        self.lineEditSell = lineEditSellCondition  # QLineEdit 위젯 전달

        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.order = None
        self.set_indicators()

    def set_indicators(self):
        self.rsi = bt.indicators.RSI_SMA(self.data.close, period=14)
        self.ema5 = bt.indicators.EMA(self.data.close, period=5)
        self.ema10 = bt.indicators.EMA(self.data.close, period=10)
        self.macdhist = bt.indicators.MACDHisto(self.data.close)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed: 
            action = 'BUY' if order.isbuy() else 'SELL'
            self.log(f'{action} : 주가 {order.executed.price:,.0f}, '
                     f'수량 {order.executed.size:,.0f}, '
                     f'수수료 {order.executed.comm:,.0f}, '
                     f'자산 {self.broker.getvalue():,.0f}')
            if order.isbuy():
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            self.bar_executed = len(self)
        elif order.status == order.Canceled:
            self.log('ORDER CANCELED')
        elif order.status == order.Margin:
            self.log('ORDER MARGIN')
        elif order.status == order.Rejected:
            self.log('ORDER REJECTED')
        self.order = None

    def next(self):
        if not self.position:
            if self.buy_condition():
                self.order = self.buy()
        else:
            if self.sell_condition():
                self.order = self.sell()

    def buy_condition(self):
        condition_text = self.lineEditBuy.text()
        return eval(condition_text)

    def sell_condition(self):
        condition_text = self.lineEditSell.text()
        # 안전한 방법으로 문자열을 조건으로 변환 (여기서는 예시로 eval 사용)
        return eval(condition_text)

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        log_text = f'[{dt.isoformat()}] {txt}'
        self.text_browser.append(log_text)

class MyMainWindow(QMainWindow):
    graphUpdated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        uic.loadUi('stock.ui', self)

        self.codes = {}
        self.run = True

        # self.setupUi()
        self.connect_buttons()

        # 분석 화면
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        # self.verticalLayout_2.addWidget(self.canvas)

        # 로그 화면
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self._append_text(x))

        # Backtesting 버튼 클릭 시그널에 메서드 연결
        self.BacktestingButton.clicked.connect(self.start_backtesting)
        self.lineEdit_stock.returnPressed.connect(self.start_backtesting)

        # 버튼 클릭 시그널에 메서드 연결
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)

        self.dateEdit_start.setDate(QtCore.QDate(2022, 1, 1))

        self.optimize_button.clicked.connect(self.run_portfolio_optimization)

        # buy_condition.txt 파일에서 조건을 로드하여 QLineEdit에 설정
        try:
            with open('files/buy_condition.txt', 'r') as file:
                buy_condition_text = file.read().strip()
                self.lineEditBuyCondition.setText(buy_condition_text)
        except Exception as e:
            print(f"Error reading buy_condition.txt: {e}")

        # sell_condition.txt 파일에서 조건을 로드하여 QLineEdit에 설정
        try:
            with open('files/sell_condition.txt', 'r') as file:
                sell_condition_text = file.read().strip()
                self.lineEditSellCondition.setText(sell_condition_text)
        except Exception as e:
            print(f"Error reading sell_condition.txt: {e}")

        try:
            with open('files/stock_hold.txt', 'r', encoding='utf-8') as file:
                stock_names = [line.strip() for line in file if line.strip()]
                # 주식명을 쉼표로 연결합니다.
                stocks_string = ', '.join(stock_names)
                # QLineEdit에 설정합니다.
                self.portfolio.setText(stocks_string)
        except Exception as e:
            print(f"Failed to load stock names: {e}")

        # 시그널 슬롯 처리
        self.graphUpdated.connect(self.update_graph_ui)

    def run_portfolio_optimization(self):
        stock_names = self.portfolio.text().split(',')  # QLineEdit에서 종목명을 가져옵니다.
        stock_names = [name.strip() for name in stock_names if name.strip()]  # 공백 제거

        portfolio_optimization = PortfolioOptimization(stock_names)

        result = portfolio_optimization.optimize_portfolio()  # 변경된 부분
        if result is not None:
            df_port, max_sharpe, min_risk = result

            self.textBrowser.clear()  # 이전 출력 내용을 지웁니다.
            max_sharpe_text = 'Max Sharpe Ratio:\n' + max_sharpe.to_string(index=False)
            min_risk_text = '\nMin Risk:\n' + min_risk.to_string(index=False)
            self.textBrowser.append(max_sharpe_text + '\n' + min_risk_text)
            
            fig = Figure()
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)

            # 데이터로부터 색상 배열 생성
            sharpe_array = df_port['Sharpe'].values
            cmap = plt.cm.viridis
            normalize = plt.Normalize(vmin=min(sharpe_array), vmax=max(sharpe_array))
            colors = cmap(normalize(sharpe_array))

            # # 그래프 그리기
            ax.scatter(df_port['Risk'], df_port['Returns'], c=colors, edgecolors='k')
            ax.scatter(x=max_sharpe['Risk'], y=max_sharpe['Returns'], c='r', marker='*', s=300)
            ax.scatter(x=min_risk['Risk'], y=min_risk['Returns'], c='r', marker='X', s=200)
            ax.set_title('Portfolio Optimization')
            ax.set_xlabel('Risk')
            ax.set_ylabel('Expected Returns')

            # # verticalLayout_7에 그래프 추가
            if hasattr(self, 'canvas_back'):
                self.verticalLayout_7.removeWidget(self.canvas_back)
                self.canvas_back.figure.clf()
                self.canvas_back.close()
            self.canvas_back = canvas  # 캔버스를 클래스 변수로 저장
            self.verticalLayout_7.addWidget(self.canvas_back)
            self.canvas_back.draw()

    def update_graph_ui(self, source):

        if source == "show_graph":
            # self.verticalLayout_2.removeWidget(self.imagelabel_3)
            self.imagelabel_3.hide()
            self.verticalLayout_2.removeWidget(self.canvas)
            self.fig = plt.figure()
            self.canvas = FigureCanvas(self.fig)

            plt.rc("font", family="Malgun Gothic")
            plt.rcParams["axes.unicode_minus"] = False
            plt.clf()

            p1 = plt.subplot2grid((9, 4), (0, 0), rowspan=4, colspan=4)
            p1.grid()
            day = str(self.df.date.values[-1])
            title = (self.txt_company+" ("+day+ " : "+ str(self.df.close.values[-1])+ ")"+"\n"
                + " 수익률: "+ "(20일 "+ str(self.df.RET20.values[-1])+ "%) "
                + "(5일 "+ str(self.df.RET5.values[-1])+ "%) "
                + "(1일 "+ str(self.df.RET1.values[-1])+ "%)"
                + " / 이동평균: "+"(EMA5 " + str(round(self.df.ema5.values[-1],1))+") "
                + "(EMA10 " + str(round(self.df.ema10.values[-1],1))+") "
                + "(EMA20 " + str(round(self.df.ema20.values[-1],1))+") "
            )
            p1.set_title(title)
            # p1.plot(self.df.index, self.df['upper'], 'r--')
            # p1.plot(self.df.index, self.df['lower'], 'c--')
            # p1.plot(self.df.index, self.df['ENTOP'], 'r--')
            p1.plot(self.df.index, self.df["ENBOTTOM"], "k--")
            p1.fill_between(self.df.index, self.df["ENTOP"], self.df["ENBOTTOM"], color="0.93")
            candlestick_ohlc(
                p1, self.ohlc.values, width=0.6, colorup="red", colordown="blue"
            )
            p1.plot(self.df.index, self.df["ema5"], "m", alpha=0.7, label="EMA5")
            p1.plot(self.df.index, self.df["ema10"], color="limegreen", alpha=0.7, label="EMA10")
            p1.plot(self.df.index, self.df["ema20"], color="orange", alpha=0.7, label="EMA20")
            # p1.plot(self.df.index, self.df['ema130'], color='black', alpha=0.7, label='EMA130')
            for i in range(len(self.df.close)):            
                if (
                    (
                        self.df.close.values[i] < self.df.ENBOTTOM.values[i]
                        and self.df.RSI.values[i] < 30
                    )
                    and (self.df.macd.values[i - 1] < self.df.macd.values[i])
                    and (self.df.close.values[i] > self.df.open.values[i])
                ):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "r^",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif (self.df.RSI.values[i - 1] < 30 < self.df.RSI.values[i] and self.df.macd.values[i-1] < self.df.macd.values[i]) or (
                        self.df.macdhist.values[i - 1] < 0 < self.df.macdhist.values[i]
                ):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "y^",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif ((self.df.ema5.values[i - 1] > self.df.ema10.values[i - 1]
                        and self.df.ema5.values[i] < self.df.ema10.values[i]
                        and self.df.macd.values[i - 1] > self.df.macd.values[i])
                    or (self.df.macdhist.values[i - 1] > 0 > self.df.macdhist.values[i])
                ):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "bv",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif (
                    (self.df.RSI.values[i - 1] > 70 > self.df.RSI.values[i]
                        and self.df.macd.values[i - 1] > self.df.macd.values[i])
                    or (
                        self.df.RSI.values[i] > 70
                    and self.df.macd.values[i - 1] > self.df.macd.values[i]
                    and (self.df.close.values[i] < self.df.open.values[i])
                ) or (
                    (self.df.close.values[i - 1] > self.df.ENTOP.values[i - 1]
                        and self.df.close.values[i] < self.df.ENTOP.values[i])
                    and (self.df.macd.values[i - 1] > self.df.macd.values[i])
                )):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "gv",
                        markersize=8,
                        markeredgecolor="black",
                    )

            # plt2 = p1.twinx()
            # plt2.bar(self.df.index, self.df['volume'], color='deeppink', alpha=0.5, label='VOL')
            # plt2.set_ylim(0, max(self.df.volume * 5))
            p1.legend(loc="best")
            plt.setp(p1.get_xticklabels(), visible=False)

            p4 = plt.subplot2grid((9, 4), (4, 0), rowspan=1, colspan=4)
            p4.grid(axis="x")
            p4.bar(self.df.index, self.df["volume"], color="deeppink", alpha=0.5, label="VOL")
            plt.setp(p4.get_xticklabels(), visible=False)

            p3 = plt.subplot2grid((9, 4), (5, 0), rowspan=2, colspan=4, sharex=p4)
            p3.grid()
            # p3.plot(self.df.index, self.df['fast_k'], color='c', label='%K')
            p3.plot(self.df.index, self.df["slow_d"], "c--", label="%D")
            p3.plot(self.df.index, self.df["RSI"], color="red", label="RSI")
            p3.fill_between(
                self.df.index,
                self.df["RSI"],
                70,
                where=self.df["RSI"] >= 70,
                facecolor="red",
                alpha=0.3,
            )
            p3.fill_between(
                self.df.index,
                self.df["RSI"],
                30,
                where=self.df["RSI"] <= 30,
                facecolor="blue",
                alpha=0.3,
            )
            p3.set_yticks([0, 20, 30, 70, 80, 100])
            p3.legend(loc="best")
            plt.setp(p3.get_xticklabels(), visible=False)

            p2 = plt.subplot2grid((9, 4), (7, 0), rowspan=2, colspan=4, sharex=p4)
            p2.grid()
            p2.bar(self.df.index, self.df["macdhist"], color="m", label="MACD-Hist")
            p2.plot(self.df.index, self.df["macd"], color="c", label="MACD")
            p2.plot(self.df.index, self.df["signal"], "g--")
            p2.legend(loc="best")

            plt.subplots_adjust(hspace=0.05)
            
            self.verticalLayout_2.addWidget(self.canvas)
            self.canvas.draw()

        elif source == "display_graph":

            self.verticalLayout_7.addWidget(self.canvas_back)
            self.canvas_back.draw()

    def save_buy_condition(self):
        buy_condition = self.lineEditBuyCondition.text()
        with open('files/buy_condition.txt', 'w') as file:
            file.write(buy_condition)
        print("Buy condition saved.")

    def save_sell_condition(self):
        sell_condition = self.lineEditSellCondition.text()
        with open('files/sell_condition.txt', 'w') as file:
            file.write(sell_condition)
        print("Sell condition saved.")

    def start_backtesting(self):
        try:
            self.textBrowser.clear()  # 텍스트 브라우저의 내용을 비웁니다.
            
            self.company = self.lineEdit_stock.text()
            self.start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")

            # 백테스팅 설정 및 실행
            cerebro = self.setup_cerebro()
            self.display_portfolio_value(cerebro, 'Initial')
            cerebro.run()
            self.display_portfolio_value(cerebro, 'Final')

            self.display_graph(cerebro)
        except Exception as e:
            print(str(e))

    def setup_cerebro(self):
        cerebro = bt.Cerebro()
        cerebro.addstrategy(MyStrategy, self.textBrowser, self.lineEditBuyCondition, self.lineEditSellCondition)
        df = self.fetch_stock_data()
        data = bt.feeds.PandasData(dataname=df, datetime='date')
        cerebro.adddata(data)
        cerebro.broker.setcash(10000000)
        cerebro.broker.setcommission(commission=0.0014)
        cerebro.addsizer(bt.sizers.PercentSizer, percents=90)
        return cerebro

    def fetch_stock_data(self):
        mk = Analyzer.MarketDB()
        df = mk.get_daily_price(self.company, self.start_date)
        df.date = pd.to_datetime(df.date)
        return df

    def display_portfolio_value(self, cerebro, timing):
        value = f'{cerebro.broker.getvalue():,.0f} KRW'
        self.textBrowser.append(f'{timing} Portfolio Value : {value}')

    def display_graph(self, cerebro):
        # 이전 그래프를 포함하는 Canvas를 제거
        if hasattr(self, 'canvas_back'):
            self.verticalLayout_7.removeWidget(self.canvas_back)
            self.canvas_back.figure.clf()
            self.canvas_back.close()

        # cerebro로부터 새로운 그래프를 생성합니다.
        figures = cerebro.plot(style='candlestick')
        figure = figures[0][0]
        self.canvas_back = FigureCanvas(figure)
        self.graphUpdated.emit("display_graph")

    def _append_text(self, msg):
        self.log_widget.moveCursor(QtGui.QTextCursor.End)
        self.log_widget.insertPlainText(msg)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    def connect_buttons(self):
        # 종목 업데이트

        self.btn_update1.clicked.connect(lambda: self.start_thread(self.update_stocks, "kr"))
        self.btn_update2.clicked.connect(lambda: self.start_thread(self.update_stocks, "us"))
        self.btn_update3.clicked.connect(lambda: self.start_thread(self.update_stocks, "all"))
        self.btn_stop1.clicked.connect(lambda: self.update_stocks("stop"))
        self.btn_update4.clicked.connect(lambda: self.start_thread(self.update_specific_stock))


        # 종목 탐색

        self.btn_search1.clicked.connect(lambda: self.start_thread(self.search_stock, "kr"))
        self.btn_search2.clicked.connect(lambda: self.start_thread(self.search_stock, "us"))
        self.btn_search3.clicked.connect(lambda: self.start_thread(self.search_stock, "all"))
        self.btn_stop2.clicked.connect(lambda: self.search_stock("stop"))

        self.btn.clicked.connect(self.btncmd)
        self.btn_addhold.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.lb_hold,
                "files/stock_hold.txt",
                self.lb_search.currentItem().text(),
            )
        )
        self.btn_addint.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.lb_int,
                "files/stock_interest.txt",
                self.lb_search.currentItem().text(),
            )
        )

        self.lb_search.addItems(self.load_companies_from_file("files/stock_search.txt"))

        # 보유 종목

        self.lb_hold.addItems(self.load_companies_from_file("files/stock_hold.txt"))

        self.btn2.clicked.connect(self.btncmd2)
        self.btn_del1.clicked.connect(self.btncmd_del1)
        self.btn_addint1.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.lb_int,
                "files/stock_interest.txt",
                self.lb_hold.currentItem().text(),
            )
        )

        # 관심 종목

        self.lb_int.addItems(self.load_companies_from_file("files/stock_interest.txt"))

        self.btn3.clicked.connect(self.btncmd3)
        self.btn_del2.clicked.connect(self.btncmd_del2)
        self.btn_addhold1.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.lb_hold,
                "files/stock_hold.txt",
                self.lb_int.currentItem().text(),
            )
        )

        # 종목 조회
        self.btn_find.clicked.connect(self.find_stock)
        self.btn_addhold2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.lb_hold, "files/stock_hold.txt", self.ent.text()
            )
        )
        self.btn_addint2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.lb_int, "files/stock_interest.txt", self.ent.text()
            )
        )

    def start_thread(self, func, *args):
        Thread(target=func, args=args, daemon=True).start()

    def load_companies_from_file(self, filename):
        companies = []
        try:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf8") as f:
                    companies = [line.strip() for line in f if line]
        except Exception as e:
            print(f"Error occurred while loading companies from file: {str(e)}")
        return companies

    # 종목 업데이트
    def update_stocks(self, nation):
        try:
            db_updater = DBUpdater_new.DBUpdater()
            if nation in ["kr", "us", "all"]:
                db_updater.update_comp_info(nation)
                db_updater.update_daily_price(nation)
            elif nation == "stop":
                db_updater.update_daily_price("stop")
        except FileNotFoundError as e:
            print(f"File not found: {str(e)}")
        except Exception as e:
            print(f"Error occurred while updating stocks: {str(e)}")

    def update_stock_price(self, company, period):
        mk = Analyzer.MarketDB()
        stk = mk.get_comp_info()
        val = stk[(stk['company'] == company) | (stk['code'] == company)]
        code = val.iloc[0]['code']
        company = val.iloc[0]['company']

        db_updater = DBUpdater_new.DBUpdater()
        if val.iloc[0]['country'] == 'kr':
            df = db_updater.read_naver(code, period)
        elif val.iloc[0]['country'] == 'us':
            db_updater.ric_code()
            df = db_updater.read_yfinance(code, period)
        # df = df.dropna()
        db_updater.replace_into_db(df, 0, code, company)

    def update_specific_stock(self):
        try:
            company = self.ent_stock.text()
            if self.btn_period1.isChecked():
                self.update_stock_price(company, 1)
            elif self.btn_period2.isChecked():
                self.update_stock_price(company, 2)
        except FileNotFoundError as e:
            print(f"File not found: {str(e)}")
        except Exception as e:
            print(f"Error occurred while updating a specific stock: {str(e)}")

    # 종목 탐색
    def clear_search_file(self):
        with open("files/stock_search.txt", "w", encoding="utf8") as f:
            f.write("")

    def write_to_search_file(self, company):
        with open("files/stock_search.txt", "a", encoding="utf8") as f:
            f.write(f"{company}\n")

    def search_stock(self, nation):
        self.clear_search_file()
        stock_list = self.prepare_stock_data(nation)
        self.analyze_and_save_results(stock_list)

    def prepare_stock_data(self, nation):
        mk = Analyzer.MarketDB()
        stock_list = mk.get_comp_info()
        stock_list["len_code"] = stock_list.code.str.len()

        if nation in ["us", "kr"]:
            self.run = True
            idx = (
                stock_list[stock_list.len_code == 6].index
                if nation == "us"
                else stock_list[stock_list.len_code < 6].index
            )
            stock_list = stock_list.drop(idx)
            self.lb_search.clear()
        elif nation == "all":
            self.run = True
            self.lb_search.clear()
        elif nation == "stop":
            self.run = False

        return stock_list

    def analyze_and_save_results(self, stock_list):
        for idx in range(len(stock_list)):
            if self.run:
                company = stock_list["company"].values[idx]
                mk = Analyzer.MarketDB()
                df = mk.get_daily_price(company, "2022-01-01")

                df.MA20 = df.close.rolling(window=20).mean()
                df.ENTOP = df.MA20 + df.MA20 * 0.1
                df['ENBOTTOM'] = df.MA20 - df.MA20 * 0.1
                df.U = df.close.diff().clip(lower=0)
                df.D = -df.close.diff().clip(upper=0)
                df.RS = (df.U.rolling(window=14).mean() / df.D.rolling(window=14).mean())
                df['RSI'] = 100 - 100 / (1 + df.RS)
                df = df.dropna()

                ema12 = df.close.ewm(span=12, adjust=False).mean()
                ema26 = df.close.ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9, adjust=False).mean()
                macdhist = macd - signal
                df = df.assign(ema12=ema12,
                    ema26=ema26,
                    macd=macd,
                    signal=signal,
                    macdhist=macdhist,
                ).dropna()
                df.index = pd.to_datetime(df.date)

                # ndays_high = df.high.rolling(window=14, min_periods=1).max()
                # ndays_low = df.low.rolling(window=14, min_periods=1).min()
                # fast_k = (df.close - ndays_low) / (ndays_high - ndays_low) * 100
                # slow_d = fast_k.rolling(window=3).mean()
                # df = df.assign(fast_k=fast_k, slow_d=slow_d).dropna()

                print(company)

                try:
                    if (
                        df.RSI.values[-1] < 30
                        and df.macdhist.values[-1] > df.macdhist.values[-2]
                        and df.macd.values[-1] > df.macd.values[-2]
                        and df.close.values[-1] > df.open.values[-1] and (df.volume.values[-2:] > 10000).any()) or (df.close.values[-1] < df.ENBOTTOM.values[-1] and df.close.values[-1] > df.open.values[-1] and (df.volume.values[-2:] > 10000).any()):
                        self.lb_search.addItem(company)
                        self.write_to_search_file(company)
                except Exception as e:
                    print(str(e))

    def update_and_show_stock(self, company):
        self.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    def btncmd(self):
        company = self.lb_search.currentItem().text()
        self.update_and_show_stock(company)

    def manage_stock_list(self, action, listbox=None, filename=None, company=None):
        if action == "add":
            listbox.addItem(company)
            self.append_to_file(filename, company)
        elif action == "get":
            return listbox.currentItem().text()
        elif action == "update":
            self.write_list_to_file(filename, listbox)

    def append_to_file(self, filename, text):
        with open(filename, "a", encoding="utf8") as f:
            f.write("%s\n" % text)

    def write_list_to_file(self, filename, listbox):
        with open(filename, "w", encoding="utf8") as f:
            for idx in range(listbox.count()):
                company = listbox.item(idx).text()
                f.write("%s\n" % company)

    def btncmd2(self):
        company = self.manage_stock_list("get", self.lb_hold)
        self.update_and_show_stock(company)

    def btncmd_del1(self):
        self.lb_hold.takeItem(self.lb_hold.currentRow())
        self.manage_stock_list("update", self.lb_hold, "files/stock_hold.txt")

    def btncmd3(self):
        company = self.manage_stock_list("get", self.lb_int)
        self.update_and_show_stock(company)

    def btncmd_del2(self):
        self.lb_int.takeItem(self.lb_int.currentRow())
        self.manage_stock_list("update", self.lb_int, "files/stock_interest.txt")

    def find_stock(self):
        company = self.ent.text()
        db_updater = DBUpdater_new.DBUpdater()
        db_updater.update_daily_price("stop")
        time.sleep(0.2)
        self.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    # 그래프

    def show_graph(self, company):    
        try:
            mk = Analyzer.MarketDB()
            self.df = mk.get_daily_price(company, "2022-01-01")
            self.txt_company = company

            self.df["MA20"] = self.df["close"].rolling(window=20).mean()
            self.df["ENTOP"] = self.df["MA20"] + self.df["MA20"] * 0.1
            self.df["ENBOTTOM"] = self.df["MA20"] - self.df["MA20"] * 0.1

            self.df["RET20"] = ((self.df["close"].pct_change(20)) * 100).round(1)
            self.df["RET5"] = ((self.df["close"].pct_change(5)) * 100).round(1)
            self.df["RET1"] = ((self.df["close"].pct_change(1)) * 100).round(1)

            self.df["U"] = self.df["close"].diff().clip(lower=0)
            self.df["D"] = -self.df["close"].diff().clip(upper=0)
            self.df["RS"] = self.df.U.rolling(window=14).mean() / self.df.D.rolling(window=14).mean()
            self.df["RSI"] = 100 - 100 / (1 + self.df["RS"])

            ema_values = [5, 10, 20, 60, 130, 12, 26]
            for val in ema_values:
                self.df[f"ema{val}"] = self.df.close.ewm(span=val, adjust=False).mean()

            macd = self.df.ema12 - self.df.ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            macdhist = macd - signal
            self.df = self.df.assign(macd=macd, signal=signal, macdhist=macdhist)
            self.df["number"] = self.df.index.map(mdates.date2num)
            self.df.index = pd.to_datetime(self.df.date)

            ndays_high = self.df.high.rolling(window=14, min_periods=1).max()
            ndays_low = self.df.low.rolling(window=14, min_periods=1).min()
            fast_k = (self.df.close - ndays_low) / (ndays_high - ndays_low) * 100
            slow_d = fast_k.rolling(window=3).mean()
            self.df = self.df.assign(fast_k=fast_k, slow_d=slow_d)
            self.df = self.df[-80:]
            self.ohlc = self.df[["number", "open", "high", "low", "close"]]
            # self.df['len_code'] = self.df.code.str.len()          

            self.graphUpdated.emit("show_graph")

        except Exception as e:
            print(str(e))

    # 주식 정보
    def show_info(self, company):
        try:
            mk = Analyzer.MarketDB()
            stock_list = mk.get_comp_info()
            val = stock_list[(stock_list["company"] == company) | (stock_list["code"] == company)]

            if not val.empty:
                country = val.iloc[0]["country"]
                code = val.iloc[0]["code"]

                if country == "kr":
                    stock_url = f"https://m.stock.naver.com/domestic/stock/{code}/total"
                elif country == "us":
                    db_updater = DBUpdater_new.DBUpdater()
                    ric_code = db_updater.ric_code()
                    ric = ric_code[ric_code["code"] == code]
                    if not ric.empty:
                        ric_val = ric.iloc[0]["ric"]
                        stock_url = f"https://m.stock.naver.com/worldstock/stock/{ric_val}/total"
                    else:
                        raise ValueError(f"No RIC code found for US company: {company}")
                else:
                    raise ValueError(f"Unsupported country for company: {company}")

                self.webEngineView.load(QtCore.QUrl(stock_url))

        except Exception as e:
            print(f"Error in show_info: {str(e)}")

class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, str, name="print")

    def __init__(self):
        super().__init__()
        # sys.stdout 및 sys.stderr의 원래 상태를 저장합니다.
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def stop(self):
        # stdout과 stderr를 원래의 객체로 복원합니다.
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def start(self):
        # stdout과 stderr를 이 객체의 메서드로 대체합니다.
        sys.stdout = self
        sys.stderr = self

    def write(self, message):
        # 색상을 구분하지 않고 모든 메시지를 기본 색상으로 처리합니다.
        # 필요에 따라 여기서 메시지의 종류(표준 출력 또는 에러)에 따라 색상을 지정할 수 있습니다.
        self.printOccur.emit(message, "black")

    def flush(self):
        # flush 메서드가 호출될 때 특별히 수행할 작업이 없는 경우, 이를 빈 메서드로 두어 호환성을 유지합니다.
        pass

    
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MyMainWindow()
    mainWindow.show()
    sys.exit(app.exec_())