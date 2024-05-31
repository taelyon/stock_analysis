from threading import Thread
import DBUpdater_new
import pandas as pd
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
import os
import time
import re
from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets, uic
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import *
import backtrader as bt
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('Agg')


QtWidgets.QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)

class MyMainWindow(QMainWindow):
    graphUpdated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        uic.loadUi('stock.ui', self)

        self.codes = {}
        self.run = True

        self.connect_buttons()

        # 분석 화면
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        # self.verticalLayout_2.addWidget(self.canvas)

        # 로그 화면
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self._append_text(x))

        # 시그널 슬롯 처리
        self.graphUpdated.connect(self.update_graph_ui)

    def run_portfolio_optimization(self):
        stock_names = self.portfolio.text().split(',')  # QLineEdit에서 종목명을 가져옵니다.
        stock_names = [name.strip() for name in stock_names if name.strip()]  # 공백 제거

        portfolio_optimization = PortfolioOptimization(stock_names)
        result = portfolio_optimization.optimize_portfolio()

        if result is not None:
            df_port, max_sharpe, min_risk = result

            max_sharpe_percent = max_sharpe.copy()  # 원본 데이터 수정 방지
            for column in max_sharpe_percent.columns:
                if column not in ['Returns', 'Risk', 'Sharpe']:
                    max_sharpe_percent[column] = max_sharpe_percent[column].apply(lambda x: f"{x * 100:.2f}%")  # 종목 비중을 % 형태로 변경
                elif column == 'Returns':
                    max_sharpe_percent[column] = f"{max_sharpe_percent[column].iloc[0] * 100:.2f}%"  # 수익률을 % 형태로 변경

            min_risk_percent = min_risk.copy()  # 원본 데이터 수정 방지
            for column in min_risk_percent.columns:
                if column not in ['Returns', 'Risk', 'Sharpe']:
                    min_risk_percent[column] = min_risk_percent[column].apply(lambda x: f"{x * 100:.2f}%")  # 종목 비중을 % 형태로 변경
                elif column == 'Returns':
                    min_risk_percent[column] = f"{min_risk_percent[column].iloc[0] * 100:.2f}%"  # 수익률을 % 형태로 변경

            # 'Risk'와 'Sharpe' 값의 포맷을 소숫점 네 번째 자리까지로 변경
            max_sharpe_percent['Risk'] = max_sharpe_percent['Risk'].round(3)
            max_sharpe_percent['Sharpe'] = max_sharpe_percent['Sharpe'].round(3)
            min_risk_percent['Risk'] = min_risk_percent['Risk'].round(3)
            min_risk_percent['Sharpe'] = min_risk_percent['Sharpe'].round(3)

            max_sharpe_percent.insert(max_sharpe_percent.columns.get_loc('Sharpe') + 1, ' ', '')  # max_sharpe에 빈 열 추가
            min_risk_percent.insert(min_risk_percent.columns.get_loc('Sharpe') + 1, ' ', '')  # min_risk에 빈 열 추가

            max_sharpe_html = max_sharpe_percent.to_html(index=False, border=0)
            min_risk_html = min_risk_percent.to_html(index=False, border=0)

            self.textBrowser.clear()  # 이전 출력 내용을 지웁니다.
            max_sharpe_text = '<b>Max Sharpe Ratio:</b>' + max_sharpe_html
            min_risk_text = '<b>Min Risk:</b>' + min_risk_html
            self.textBrowser.setHtml(max_sharpe_text + '<br>' '<br>'+ min_risk_text)
            
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
        try:
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
                title = (
                    f"{self.txt_company} ({day}: {format(round(self.df.close.values[-1], 2), ',')} )\n"
                    + f" 수익률: (20일 {self.df.RET20.values[-1]}%) "
                    + f"(5일 {self.df.RET5.values[-1]}%) "
                    + f"(1일 {self.df.RET1.values[-1]}%)"
                    + " / 이동평균: "
                    + f"(EMA5 {format(round(self.df.ema5.values[-1], 1), ',')}) "
                    + f"(EMA10 {format(round(self.df.ema10.values[-1], 1), ',')}) "
                    + f"(EMA20 {format(round(self.df.ema20.values[-1], 1), ',')})"
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
                    if eval(re.sub('df', 'self.df', re.sub(r'\[-(\d+)\]', lambda x: f'[i-{int(x.group(1)) - 1}]', self.search_condition_text_2))):
                        p1.plot(
                            self.df.index.values[i],
                            self.df.low.values[i] * 0.98,
                            "r^",
                            markersize=8,
                            markeredgecolor="black")
                    elif eval(re.sub('df', 'self.df', re.sub(r'\[-(\d+)\]', lambda x: f'[i-{int(x.group(1)) - 1}]', self.search_condition_text_1))): # 탐색조건식 반영
                        p1.plot(
                            self.df.index.values[i],
                            self.df.low.values[i] * 0.98,
                            "y^",
                            markersize=8,
                            markeredgecolor="black")
                    elif ((self.df.ema5.values[i - 1] > self.df.ema10.values[i - 1]
                            and self.df.ema5.values[i] < self.df.ema10.values[i]
                            and self.df.signal.values[i - 1] > self.df.signal.values[i])
                        or (self.df.macdhist.values[i - 1] > 0 > self.df.macdhist.values[i])):
                        p1.plot(
                            self.df.index.values[i],
                            self.df.low.values[i] * 0.98,
                            "bv",
                            markersize=8,
                            markeredgecolor="black")
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
                            markeredgecolor="black")

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
        except Exception as e:
            print(str(e))

    def save_search_condition(self):
        # 라디오버튼의 선택 상태 확인
        if self.radioButton.isChecked():
            search_condition_1 = self.lineEditSearchCondition.text()
            with open('files/search_condition_1.txt', 'w') as file:
                file.write(search_condition_1)
            print("Search condition saved.")
            self.search_condition_text_1 = search_condition_1
        elif self.radioButton_2.isChecked():
            search_condition_2 = self.lineEditSearchCondition.text()
            with open('files/search_condition_2.txt', 'w') as file:
                file.write(search_condition_2)
            print("Search condition saved.")
            self.search_condition_text_2 = search_condition_2
            
        else:
            search_condition = self.lineEditSearchCondition.text() + " - No Option Selected"
        self.graphUpdated.emit("show_graph")

    def save_search_condition_1(self):
        with open('files/search_condition_1.txt', 'r') as file:
            search_condition_1 = file.read().strip()
            self.lineEditSearchCondition.setText(search_condition_1)
        print("상승주 탐색조건 불러오기")

    def save_search_condition_2(self):
        with open('files/search_condition_2.txt', 'r') as file:
            search_condition_2 = file.read().strip()
            self.lineEditSearchCondition.setText(search_condition_2)
        print("저가주 탐색조건 불러오기")

    def save_search_default_condition(self):
        search_condition_1 = '(df.RSI.values[-2] < 30 < df.RSI.values[-1] and df.macd.values[-2] < df.macd.values[-1]) or (df.macdhist.values[-2] < 0 < df.macdhist.values[-1])'
        search_condition_2 = '(df.close.values[-1] < df.ENBOTTOM.values[-1] and df.RSI.values[-1] < 30) and (df.macd.values[-2] < df.macd.values[-1]) and (df.close.values[-1] > df.open.values[-1])'

        with open('files/search_condition_1.txt', 'w') as file:
            file.write(search_condition_1)
            self.lineEditSearchCondition.setText(search_condition_1)
        with open('files/search_condition_2.txt', 'w') as file:
            file.write(search_condition_2)
        print("탐색조건 초기화")
        self.search_condition_text_1 = search_condition_1
        self.search_condition_text_2 = search_condition_2
        self.graphUpdated.emit("show_graph")

    def save_buy_condition(self):
        buy_condition = self.lineEditBuyCondition.text()
        with open('files/buy_condition.txt', 'w') as file:
            file.write(buy_condition)
        print("Buy condition saved.")

    def save_buy_default_condition(self):
        buy_default_condition = '((self.rsi[-1] < 30 < self.rsi[0]) and (self.macdhist.macd[-1] < self.macdhist.macd[0])) or (self.macdhist.histo[-1] < 0 < self.macdhist.histo[0])'
        with open('files/buy_condition.txt', 'w') as file:
            file.write(buy_default_condition)
        with open('files/buy_condition.txt', 'r') as file:
            buy_condition_text = file.read().strip()
            self.lineEditBuyCondition.setText(buy_condition_text)
        print("Buy default condition saved.")

    def save_sell_condition(self):
        sell_condition = self.lineEditSellCondition.text()
        with open('files/sell_condition.txt', 'w') as file:
            file.write(sell_condition)
        print("Sell condition saved.")

    def save_sell_default_condition(self):
        sell_default_condition = '((self.ema5[-1] > self.ema20[-1]) and (self.ema5[0] < self.ema20[0]) and (self.macdhist.macd[-1] > self.macdhist.macd[0])) or (self.macdhist.histo[-1] > 0 > self.macdhist.histo[0])'
        with open('files/sell_condition.txt', 'w') as file:
            file.write(sell_default_condition)
        with open('files/sell_condition.txt', 'r') as file:
            sell_condition_text = file.read().strip()
            self.lineEditSellCondition.setText(sell_condition_text)
        print("Sell default condition saved.")

    def start_backtesting(self):
        try:
            self.textBrowser.clear()  # Clear the text browser content.

            # Set the backtesting parameters
            self.company = self.lineEdit_stock.text()
            original_start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")
            
            # Adjust start date for additional data to warm-up indicators (e.g., 100 days earlier)
            adjusted_start_date = self.dateEdit_start.date().addDays(-100).toString("yyyy-MM-dd")  # Assuming 100 days for indicator warm-up

            # Backtesting setup and execution
            cerebro = bt.Cerebro()
            cerebro.addstrategy(
                MyStrategy,
                self.textBrowser,
                self.lineEditBuyCondition,
                self.lineEditSellCondition)

            mk = DBUpdater_new.MarketDB()
            mk.get_comp_info()
            df = mk.get_daily_price(self.company, adjusted_start_date)  # Use adjusted start date
            df.date = pd.to_datetime(df.date)

            data = bt.feeds.PandasData(dataname=df, datetime='date')
            cerebro.adddata(data)
            initial_cash = 10000000
            cerebro.broker.setcash(initial_cash)
            cerebro.broker.setcommission(commission=0.0014)
            cerebro.addsizer(bt.sizers.PercentSizer, percents=90)

            # Display initial portfolio value
            initial_portfolio_value = cerebro.broker.getvalue()
            initial_price = df['close'].iloc[0]
            self.textBrowser.append(f'Initial Portfolio Value : {initial_portfolio_value:,.0f} KRW')
            cerebro.run()
            
            # Display final portfolio value
            final_portfolio_value = cerebro.broker.getvalue()
            self.textBrowser.append(f'Final Portfolio Value : {final_portfolio_value:,.0f} KRW')
            self.textBrowser.append(f'자산투자수익률 : {((final_portfolio_value - initial_portfolio_value) / initial_portfolio_value) * 100:.2f}%')

            # Display price return since the original start date
            df_filtered = df[df['date'] >= pd.to_datetime(original_start_date)]  # Filter to original start date
            if not df_filtered.empty:
                initial_price = df_filtered['close'].iloc[0]
                final_price = df_filtered['close'].iloc[-1]
                self.textBrowser.append(f'최초 주가 : {initial_price:,.0f}, 최종 주가 : {final_price:,.0f}')
                self.textBrowser.append(f'단순주가수익률 : {((final_price - initial_price) / initial_price) * 100:.2f}%')

            self.display_graph(cerebro)

        except Exception as e:
            print(str(e))


    def display_graph(self, cerebro):
        # 이전 그래프를 포함하는 Canvas를 제거
        if hasattr(self, 'canvas_back'):
            self.verticalLayout_7.removeWidget(self.canvas_back)
            self.canvas_back.figure.clf()
            self.canvas_back.close()

        # cerebro로부터 새로운 그래프를 생성합니다.
        figures = cerebro.plot(style='candlestick', barup='green', fmt_x_ticks='%Y-%m-%d')
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
        self.ent_stock.returnPressed.connect(self.update_specific_stock)
       
        self.SearchConditionInputButton.clicked.connect(self.save_search_condition)
        self.SearchConditionInputButton_2.clicked.connect(self.save_search_condition_1)
        self.SearchConditionInputButton_3.clicked.connect(self.save_search_condition_2)
        self.SearchConditionInputButton_4.clicked.connect(self.save_search_default_condition)
        self.radioButton.setChecked(True)
        
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
        self.le_ent.returnPressed.connect(self.find_stock)
        self.btn_addhold2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.lb_hold, "files/stock_hold.txt", self.le_ent.text()
            )
        )
        self.btn_addint2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.lb_int, "files/stock_interest.txt", self.le_ent.text()
            )
        )

         # 리스트 박스 아이템 클릭 시 이벤트 연결
        self.lb_hold.itemClicked.connect(self.btncmd2)
        self.lb_int.itemClicked.connect(self.btncmd3)
        self.lb_search.itemClicked.connect(self.btncmd)

        # Backtesting 버튼 클릭 시그널에 메서드 연결
        self.BacktestingButton.clicked.connect(self.start_backtesting)
        self.lineEdit_stock.returnPressed.connect(self.start_backtesting)
        self.portfolio.returnPressed.connect(self.run_portfolio_optimization)

        # 버튼 클릭 시그널에 메서드 연결
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.buyConditionDefaultButton.clicked.connect(self.save_buy_default_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.save_sell_default_condition)
        
        self.dateEdit_start.setDate(QtCore.QDate(2023, 1, 1))
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

        # 탐색 조건식
        try:
            with open('files/search_condition_1.txt', 'r') as file:
                self.search_condition_text_1 = file.read().strip()
                self.lineEditSearchCondition.setText(self.search_condition_text_1)
            with open('files/search_condition_2.txt', 'r') as file:
                self.search_condition_text_2 = file.read().strip()
        except Exception as e:
            print(f"Error reading sell_condition.txt: {e}")

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
                db_updater.update_daily_price(nation, 1)
            elif nation == "stop":
                db_updater.update_daily_price("stop")
        except FileNotFoundError as e:
            print(f"File not found: {str(e)}")
        except Exception as e:
            print(f"Error occurred while updating stocks: {str(e)}")

    def update_stock_price(self, company, period):

        mk = DBUpdater_new.MarketDB()
        stock_list = mk.get_comp_info(company)         

        val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]
        code = val.iloc[0]['code']
        company = val.iloc[0]['company']

        db_updater = DBUpdater_new.DBUpdater()
        if val.iloc[0]['country'] == 'kr':
            df = db_updater.read_naver(code, period)
        elif val.iloc[0]['country'] == 'us':
            db_updater.ric_code()
            df = db_updater.read_yfinance(code, period)
        # df = df.dropna()
        if df is not None:
            db_updater.replace_into_db(df, 0, code, company)

    def update_specific_stock(self):
        try:
            db_updater = DBUpdater_new.DBUpdater()
            company = self.ent_stock.text()
            if company == 'default':
                db_updater.init_db()
                db_updater.update_comp_info('all')
                db_updater.update_daily_price('all', 2)
            else:
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
        mk = DBUpdater_new.MarketDB()
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
                mk = DBUpdater_new.MarketDB()
                mk.get_comp_info()
                df = mk.get_daily_price(company, "2022-01-01")

                df.MA20 = df.close.rolling(window=20).mean()
                df.ENTOP = df.MA20 + df.MA20 * 0.1
                df['ENBOTTOM'] = df.MA20 - df.MA20 * 0.1
                df.U = df.close.diff().clip(lower=0)
                df.D = -df.close.diff().clip(upper=0)
                df.RS = (df.U.ewm(span=14, adjust=False).mean() / df.D.ewm(span=14, adjust=False).mean())
                df['RSI'] = 100 - (100 / (1 + df.RS))
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
                    search_condition_text = self.lineEditSearchCondition.text()
                    search_condition = eval(search_condition_text)

                    if search_condition:
                        self.lb_search.addItem(company)
                        self.write_to_search_file(company)
                except Exception as e:
                    print(str(e))

    def update_and_show_stock(self, company):
        self.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    def btncmd(self):
        try:
            company = self.lb_search.currentItem().text()
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")

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
        try:
            company = self.manage_stock_list("get", self.lb_hold)
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")

    def btncmd_del1(self):
        try:
            self.lb_hold.takeItem(self.lb_hold.currentRow())
            self.manage_stock_list("update", self.lb_hold, "files/stock_hold.txt")
        except Exception as e:
            print(f"An error occurred: {e}")

    def btncmd3(self):
        try:
            company = self.manage_stock_list("get", self.lb_int)
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")
            
    def btncmd_del2(self):
        try:
            self.lb_int.takeItem(self.lb_int.currentRow())
            self.manage_stock_list("update", self.lb_int, "files/stock_interest.txt")
        except Exception as e:
            print(f"An error occurred: {e}")
            
    def find_stock(self):
        try:
            company = self.le_ent.text()
            db_updater = DBUpdater_new.DBUpdater()
            db_updater.update_daily_price("stop")
            time.sleep(0.2)
            self.update_stock_price(company, 2)
            Thread(target=self.show_graph, args=(company,), daemon=True).start()
            self.show_info(company)
        except Exception as e:
            print(str(e))

    # 그래프

    def show_graph(self, company):    
        try:
            mk = DBUpdater_new.MarketDB()
            mk.get_comp_info(company)
            self.df = mk.get_daily_price(company, "2022-01-01")
            self.txt_company = company

            self.df["MA20"] = self.df["close"].rolling(window=20).mean()
            self.df["ENTOP"] = self.df["MA20"] + self.df["MA20"] * 0.1
            self.df["ENBOTTOM"] = self.df["MA20"] - self.df["MA20"] * 0.1

            self.df["RET20"] = ((self.df["close"].pct_change(20)) * 100).round(1)
            self.df["RET5"] = ((self.df["close"].pct_change(5)) * 100).round(1)
            self.df["RET1"] = ((self.df["close"].pct_change(1)) * 100).round(1)

            self.df.U = self.df.close.diff().clip(lower=0)
            self.df.D = -self.df.close.diff().clip(upper=0)
            self.df.RS = (self.df.U.ewm(span=14, adjust=False).mean() / self.df.D.ewm(span=14, adjust=False).mean())
            self.df['RSI'] = 100 - (100 / (1 + self.df.RS))

            ema_values = [5, 10, 20, 60, 130, 12, 26]
            for val in ema_values:
                self.df[f"ema{val}"] = self.df.close.ewm(span=val, adjust=False).mean()

            macd = self.df.ema12 - self.df.ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            macdhist = macd - signal
            self.df = self.df.assign(macd=macd, signal=signal, macdhist=macdhist)
            self.df.index = pd.to_datetime(self.df.date)
            self.df["number"] = self.df.index.map(mdates.date2num)

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
            mk = DBUpdater_new.MarketDB()
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

class PortfolioOptimization:
    def __init__(self, stock_list):
        self.mk = DBUpdater_new.MarketDB()
        self.mk.get_comp_info()
        self.stocks = stock_list
        self.df_port = pd.DataFrame()

    def optimize_portfolio(self):
        for s in self.stocks:
            self.df_port[s] = self.mk.get_daily_price(s, '2022-01-01')['close']
         
        daily_ret = self.df_port.pct_change() 
        annual_ret = daily_ret.mean() * 252
        daily_cov = daily_ret.cov() 
        annual_cov = daily_cov * 252

        port_ret = [] 
        port_risk = [] 
        port_weights = []
        sharpe_ratio = [] 

        # 단일 종목인 경우 처리
        if len(self.stocks) == 1:
            # 단일 종목이므로, 모든 포트폴리오는 동일하게 처리됩니다.
            port_ret = [annual_ret[0]]  # 단일 종목의 연간 수익
            port_risk = [np.sqrt(annual_cov.iloc[0, 0])]  # 단일 종목의 리스크
            port_weights = [[1]]  # 종목 비중은 100%
            sharpe_ratio = [port_ret[0] / port_risk[0]]  # 샤프 비율
        else:
            # 여러 종목인 경우 처리
            port_weights = np.random.random((20000, len(self.stocks)))
            port_weights /= np.sum(port_weights, axis=1)[:, np.newaxis]

            port_ret = np.dot(port_weights, annual_ret)
            port_risk = np.sqrt(np.einsum('ij,ji->i', port_weights @ annual_cov, port_weights.T))
            sharpe_ratio = port_ret / port_risk

        portfolio = {'Returns': port_ret, 'Risk': port_risk, 'Sharpe': sharpe_ratio}
        for i, s in enumerate(self.stocks): 
            portfolio[s] = [weight[i] for weight in port_weights]

        self.df_port = pd.DataFrame(portfolio) 
        self.df_port = self.df_port[['Returns', 'Risk', 'Sharpe'] + [s for s in self.stocks]]
        self.max_sharpe = self.df_port.loc[self.df_port['Sharpe'] == self.df_port['Sharpe'].max()]
        self.min_risk = self.df_port.loc[self.df_port['Risk'] == self.df_port['Risk'].min()]
        
        return self.df_port, self.max_sharpe, self.min_risk
       

class MyStrategy(bt.Strategy):
    def __init__(self, text_browser, lineEditBuyCondition, lineEditSellCondition):
        self.text_browser = text_browser
        self.lineEditBuy = lineEditBuyCondition
        self.lineEditSell = lineEditSellCondition  # QLineEdit 위젯 전달

        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.initial_cash = self.broker.getvalue()
        self.initial_price = self.dataclose[0]  # 최초 주가
        self.set_indicators()

    def set_indicators(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.ema5 = bt.indicators.EMA(self.data.close, period=5)
        self.ema10 = bt.indicators.EMA(self.data.close, period=10)
        self.ema20 = bt.indicators.EMA(self.data.close, period=20)
        self.ema60 = bt.indicators.EMA(self.data.close, period=60)
        self.macdhist = bt.indicators.MACDHisto(self.data.close)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY  : 주가 {order.executed.price:,.0f}, '
                         f'수량 {order.executed.size:,.0f}, '
                         f'수수료 {order.executed.comm:,.0f}, '
                         f'자산 {self.broker.getvalue():,.0f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                # Sell 이벤트 발생 시, 구매 대비 수익률 계산
                profit_ratio = ((order.executed.price - self.buyprice) / self.buyprice) * 100
                self.log(f'SELL : 주가 {order.executed.price:,.0f}, '
                         f'수량 {order.executed.size:,.0f}, '
                         f'수수료 {order.executed.comm:,.0f}, '
                         f'자산 {self.broker.getvalue():,.0f}, '
                         f'수익률 {profit_ratio:.2f}%')  # 수익률 출력
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'ORDER {order.Status}: {order.info}')
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
    mainWindow.showMaximized()
    # mainWindow.show()
    sys.exit(app.exec_())
