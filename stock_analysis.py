import os
import re
import sys
import time
from threading import Thread
from datetime import datetime, timedelta
from io import BytesIO, StringIO

import backtrader as bt
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import warnings
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mplfinance.original_flavor import candlestick_ohlc
from PyQt5 import QtCore, QtGui, QtWidgets, uic, QtWebEngineWidgets
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QMainWindow, QApplication

import DBUpdater_new

matplotlib.use('Agg')

QtWidgets.QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class MyMainWindow(QMainWindow):
    graphUpdated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        uic.loadUi('stock_analysis.ui', self)

        self.codes = {}
        self.run = True

        self.connect_buttons()

        # 분석 화면 설정
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        # self.verticalLayout_2.addWidget(self.canvas)

        # 로그 화면 설정
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self._append_text(x))

        # 시그널 슬롯 처리
        self.graphUpdated.connect(self.update_graph_ui)

        # 데이터 콜렉터 초기화
        self.data_collector = DataCollector()

        self.load_treemap()

    # 포트폴리오 최적화 실행
    def run_portfolio_optimization(self):
        stock_names = self.portfolio.text().split(',')
        stock_names = [name.strip() for name in stock_names if name.strip()]

        portfolio_optimization = PortfolioOptimization(stock_names)
        result = portfolio_optimization.optimize_portfolio()

        if result is not None:
            df_port, max_sharpe, min_risk = result

            # 포맷팅된 데이터프레임 생성
            max_sharpe_percent = self.format_portfolio_df(max_sharpe)
            min_risk_percent = self.format_portfolio_df(min_risk)

            # HTML로 변환하여 텍스트 브라우저에 표시
            max_sharpe_html = max_sharpe_percent.to_html(index=False, border=0)
            min_risk_html = min_risk_percent.to_html(index=False, border=0)

            self.textBrowser.clear()
            max_sharpe_text = '<b>Max Sharpe Ratio:</b>' + max_sharpe_html
            min_risk_text = '<b>Min Risk:</b>' + min_risk_html
            self.textBrowser.setHtml(max_sharpe_text + '<br><br>' + min_risk_text)

            # 그래프 그리기
            self.plot_portfolio(df_port, max_sharpe, min_risk)

    # 데이터프레임 포맷팅 메서드
    def format_portfolio_df(self, df):
        df_percent = df.copy()
        for column in df_percent.columns:
            if column not in ['Returns', 'Risk', 'Sharpe']:
                df_percent[column] = df_percent[column].apply(lambda x: f"{x * 100:.2f}%")
            elif column == 'Returns':
                df_percent[column] = f"{df_percent[column].iloc[0] * 100:.2f}%"
            elif column in ['Risk', 'Sharpe']:
                df_percent[column] = df_percent[column].round(3)
        df_percent.insert(df_percent.columns.get_loc('Sharpe') + 1, ' ', '')
        return df_percent

    # 포트폴리오 그래프 그리기
    def plot_portfolio(self, df_port, max_sharpe, min_risk):
        fig = Figure()
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        sharpe_array = df_port['Sharpe'].values
        cmap = plt.cm.viridis
        normalize = plt.Normalize(vmin=min(sharpe_array), vmax=max(sharpe_array))
        colors = cmap(normalize(sharpe_array))

        ax.scatter(df_port['Risk'], df_port['Returns'], c=colors, edgecolors='k')
        ax.scatter(x=max_sharpe['Risk'], y=max_sharpe['Returns'], c='r', marker='*', s=300)
        ax.scatter(x=min_risk['Risk'], y=min_risk['Returns'], c='r', marker='X', s=200)
        ax.set_title('Portfolio Optimization')
        ax.set_xlabel('Risk')
        ax.set_ylabel('Expected Returns')

        # 기존 캔버스 제거
        if hasattr(self, 'canvas_back'):
            self.verticalLayout_7.removeWidget(self.canvas_back)
            self.canvas_back.figure.clf()
            self.canvas_back.close()

        self.canvas_back = canvas
        self.verticalLayout_7.addWidget(self.canvas_back)
        self.canvas_back.draw()

    # 그래프 UI 업데이트
    def update_graph_ui(self, source):
        try:
            if source == "show_graph":
                self.imagelabel_3.hide()
                self.verticalLayout_2.removeWidget(self.canvas)
                self.fig = plt.figure()
                self.canvas = FigureCanvas(self.fig)

                plt.rc("font", family="Malgun Gothic")
                plt.rcParams["axes.unicode_minus"] = False
                plt.clf()

                self.plot_stock_graph()
                self.verticalLayout_2.addWidget(self.canvas)
                self.canvas.draw()

            elif source == "display_graph":
                self.verticalLayout_7.addWidget(self.canvas_back)
                self.canvas_back.draw()
        except Exception as e:
            print(str(e))

    # 주식 그래프 그리기
    def plot_stock_graph(self):
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
        p1.plot(self.df.index, self.df["ENBOTTOM"], "k--")
        p1.fill_between(self.df.index, self.df["ENTOP"], self.df["ENBOTTOM"], color="0.93")
        candlestick_ohlc(
            p1, self.ohlc.values, width=0.6, colorup="red", colordown="blue"
        )
        p1.plot(self.df.index, self.df["ema5"], "m", alpha=0.7, label="EMA5")
        p1.plot(self.df.index, self.df["ema10"], color="limegreen", alpha=0.7, label="EMA10")
        p1.plot(self.df.index, self.df["ema20"], color="orange", alpha=0.7, label="EMA20")
        p1.plot(self.df.index, self.df["ema60"], color="cyan", alpha=0.7, label="EMA60")

        # 조건에 따른 마커 표시
        for i in range(len(self.df.close)):
            try:
                # 조건식 변환 및 평가
                if eval(self.transform_condition(self.search_condition_text_2, i)):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "r^",
                        markersize=8,
                        markeredgecolor="black"
                    )
                elif eval(self.transform_condition(self.search_condition_text_1, i)):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "y^",
                        markersize=8,
                        markeredgecolor="black"
                    )
                elif (
                    (self.df.ema5.values[i - 1] > self.df.ema10.values[i - 1]
                     and self.df.ema5.values[i] < self.df.ema10.values[i]
                     and self.df.signal.values[i - 1] > self.df.signal.values[i])
                    or (self.df.macdhist.values[i - 1] > 0 > self.df.macdhist.values[i])
                ):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "bv",
                        markersize=8,
                        markeredgecolor="black"
                    )
                elif (
                    (self.df.RSI.values[i - 1] > 70 > self.df.RSI.values[i]
                     and self.df.macd.values[i - 1] > self.df.macd.values[i])
                    or
                    (self.df.RSI.values[i] > 70 and self.df.close.values[i] < self.df.open.values[i]
                     and self.df.macd.values[i - 1] > self.df.macd.values[i])
                    or
                    (self.df.close.values[i - 1] > self.df.ENTOP.values[i - 1]
                     and self.df.close.values[i] < self.df.ENTOP.values[i]
                     and self.df.macd.values[i - 1] > self.df.macd.values[i])
                ):
                    p1.plot(
                        self.df.index.values[i],
                        self.df.low.values[i] * 0.98,
                        "gv",
                        markersize=8,
                        markeredgecolor="black"
                    )
            except Exception as e:
                print(f"Error plotting marker at index {i}: {e}")

        p1.legend(loc="best")
        plt.setp(p1.get_xticklabels(), visible=False)

        # 거래량 subplot
        p4 = plt.subplot2grid((9, 4), (4, 0), rowspan=1, colspan=4)
        p4.grid(axis="x")
        p4.bar(self.df.index, self.df["volume"], color="deeppink", alpha=0.5, label="VOL")
        plt.setp(p4.get_xticklabels(), visible=False)

        # RSI subplot
        p3 = plt.subplot2grid((9, 4), (5, 0), rowspan=2, colspan=4, sharex=p4)
        p3.grid()
        p3.plot(self.df.index, self.df["RSI_SIGNAL"], "blue", label="RSI_SIGNAL")
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

        # MACD subplot
        p2 = plt.subplot2grid((9, 4), (7, 0), rowspan=2, colspan=4, sharex=p4)
        p2.grid()
        p2.bar(self.df.index, self.df["macdhist"], color="m", label="MACD-Hist")
        p2.plot(self.df.index, self.df["macd"], color="c", label="MACD")
        p2.plot(self.df.index, self.df["signal"], "g--")
        p2.legend(loc="best")

        plt.subplots_adjust(hspace=0.05)

    # 조건식을 인덱스에 맞게 변환
    def transform_condition(self, condition_text, index):
        # '[-n]'을 '[i-n]'으로 변환
        condition = re.sub(
            r'\[-(\d+)\]',
            lambda x: f'[i-{int(x.group(1))}]',
            condition_text
        )
        # 'df'를 'self.df'로 변환
        condition = condition.replace('df', 'self.df')
        # 'i'를 현재 인덱스로 변환 (단, 독립된 'i'만 변환)
        condition = re.sub(r'\bi\b', str(index), condition)
        return condition

    # 검색 조건 저장
    def save_search_condition(self):
        if self.radioButton.isChecked():
            search_condition = self.lineEditSearchCondition.text()
            self.save_condition_to_file('files/search_condition_1.txt', search_condition)
            self.search_condition_text_1 = search_condition
            print("Search condition saved.")
        elif self.radioButton_2.isChecked():
            search_condition = self.lineEditSearchCondition.text()
            self.save_condition_to_file('files/search_condition_2.txt', search_condition)
            self.search_condition_text_2 = search_condition
            print("Search condition saved.")
        else:
            search_condition = self.lineEditSearchCondition.text() + " - No Option Selected"
            print("No option selected for search condition.")

        self.graphUpdated.emit("show_graph")

    # 조건을 파일에 저장하는 메서드
    def save_condition_to_file(self, filename, condition):
        with open(filename, 'w') as file:
            file.write(condition)

    # 검색 조건 불러오기 메서드 1
    def save_search_condition_1(self):
        self.load_condition_from_file('files/search_condition_1.txt', self.lineEditSearchCondition)
        print("상승주 탐색조건 불러오기")

    # 검색 조건 불러오기 메서드 2
    def save_search_condition_2(self):
        self.load_condition_from_file('files/search_condition_2.txt', self.lineEditSearchCondition)
        print("저가주 탐색조건 불러오기")

    # 조건을 파일에서 로드하는 메서드
    def load_condition_from_file(self, filename, line_edit):
        try:
            with open(filename, 'r') as file:
                condition = file.read().strip()
                line_edit.setText(condition)
                if 'search_condition_1' in filename:
                    self.search_condition_text_1 = condition
                elif 'search_condition_2' in filename:
                    self.search_condition_text_2 = condition
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    # 기본 탐색 조건 저장
    def save_search_default_condition(self):
        search_condition_1 = (
            '(df.RSI.values[-2] < 30 < df.RSI.values[-1] and df.macd.values[-2] < df.macd.values[-1]) '
            'or (df.macdhist.values[-2] < 0 < df.macdhist.values[-1])'
        )
        search_condition_2 = (
            '(df.open.values[-1] < df.ENBOTTOM.values[-1] or df.RSI.values[-1] < 30) and '
            '(df.macdhist.values[-2] < df.macdhist.values[-1]) and '
            '(df.close.values[-1] > df.open.values[-1])'
        )

        self.save_condition_to_file('files/search_condition_1.txt', search_condition_1)
        self.save_condition_to_file('files/search_condition_2.txt', search_condition_2)

        self.lineEditSearchCondition.setText(search_condition_1)
        self.search_condition_text_1 = search_condition_1
        self.search_condition_text_2 = search_condition_2

        print("탐색조건 초기화")
        self.graphUpdated.emit("show_graph")

    # 매수 조건 저장
    def save_buy_condition(self):
        buy_condition = self.lineEditBuyCondition.text()
        self.save_condition_to_file('files/buy_condition.txt', buy_condition)
        print("Buy condition saved.")

    # 기본 매수 조건 저장
    def save_buy_default_condition(self):
        buy_default_condition = (
            '((self.rsi[-1] < 30 < self.rsi[0]) and '
            '(self.macdhist.macd[-1] < self.macdhist.macd[0])) or '
            '(self.macdhist.histo[-1] < 0 < self.macdhist.histo[0])'
        )
        self.save_condition_to_file('files/buy_condition.txt', buy_default_condition)
        self.lineEditBuyCondition.setText(buy_default_condition)
        print("Buy default condition saved.")

    # 매도 조건 저장
    def save_sell_condition(self):
        sell_condition = self.lineEditSellCondition.text()
        self.save_condition_to_file('files/sell_condition.txt', sell_condition)
        print("Sell condition saved.")

    # 기본 매도 조건 저장
    def save_sell_default_condition(self):
        sell_default_condition = (
            '((self.ema5[-1] > self.ema20[-1]) and '
            '(self.ema5[0] < self.ema20[0]) and '
            '(self.macdhist.macd[-1] > self.macdhist.macd[0])) or '
            '(self.macdhist.histo[-1] > 0 > self.macdhist.histo[0])'
        )
        self.save_condition_to_file('files/sell_condition.txt', sell_default_condition)
        self.lineEditSellCondition.setText(sell_default_condition)
        print("Sell default condition saved.")

    # 백테스팅 시작
    def start_backtesting(self):
        try:
            self.textBrowser.clear()

            # 백테스팅 파라미터 설정
            self.company = self.lineEdit_stock.text()
            original_start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")

            # 인디케이터 초기화를 위한 시작 날짜 조정
            adjusted_start_date = self.dateEdit_start.date().addDays(-100).toString("yyyy-MM-dd")

            # 백테스팅 설정 및 실행
            cerebro = bt.Cerebro()
            cerebro.addstrategy(
                MyStrategy,
                self.textBrowser,
                self.lineEditBuyCondition,
                self.lineEditSellCondition
            )

            mk = DBUpdater_new.MarketDB()
            mk.get_comp_info()
            df = mk.get_daily_price(self.company, adjusted_start_date)
            df.date = pd.to_datetime(df.date)

            data = bt.feeds.PandasData(dataname=df, datetime='date')
            cerebro.adddata(data)
            initial_cash = 10000000
            cerebro.broker.setcash(initial_cash)
            cerebro.broker.setcommission(commission=0.0014)
            cerebro.addsizer(bt.sizers.PercentSizer, percents=90)

            # 초기 포트폴리오 가치 표시
            initial_portfolio_value = cerebro.broker.getvalue()
            initial_price = df['close'].iloc[0]
            self.textBrowser.append(f'Initial Portfolio Value : {initial_portfolio_value:,.0f} KRW')
            cerebro.run()

            # 최종 포트폴리오 가치 표시
            final_portfolio_value = cerebro.broker.getvalue()
            self.textBrowser.append(f'Final Portfolio Value : {final_portfolio_value:,.0f} KRW')
            self.textBrowser.append(f'자산투자수익률 : {((final_portfolio_value - initial_portfolio_value) / initial_portfolio_value) * 100:.2f}%')

            # 원래 시작 날짜 이후의 주가 수익률 표시
            df_filtered = df[df['date'] >= pd.to_datetime(original_start_date)]
            if not df_filtered.empty:
                initial_price = df_filtered['close'].iloc[0]
                final_price = df_filtered['close'].iloc[-1]
                self.textBrowser.append(f'최초 주가 : {initial_price:,.0f}, 최종 주가 : {final_price:,.0f}')
                self.textBrowser.append(f'단순주가수익률 : {((final_price - initial_price) / initial_price) * 100:.2f}%')

            self.display_graph(cerebro)

        except Exception as e:
            print(str(e))

    # 그래프 표시
    def display_graph(self, cerebro):
        try:
            # 기존 캔버스 제거
            if hasattr(self, 'canvas_back'):
                self.verticalLayout_7.removeWidget(self.canvas_back)
                self.canvas_back.figure.clf()
                self.canvas_back.close()

            # 새로운 그래프 생성
            figures = cerebro.plot(style='candlestick', barup='green', fmt_x_ticks='%Y-%m-%d')
            figure = figures[0][0]
            self.canvas_back = FigureCanvas(figure)
            self.graphUpdated.emit("display_graph")
        except Exception as e:
            print(f"Error displaying graph: {e}")

    # 로그에 텍스트 추가
    def _append_text(self, msg):
        self.log_widget.moveCursor(QtGui.QTextCursor.End)
        self.log_widget.insertPlainText(msg)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    # 트리맵 탭 관련 메서드 추가
    def load_treemap(self):
        try:
            df_top500 = self.data_collector.get_recent_sise()
            fig = self.data_collector.create_treemap(df_top500)
            
            # Plotly 그래프를 HTML로 변환
            html = fig.to_html(include_plotlyjs='cdn')
            
            # QWebEngineView에 HTML 로드
            self.webEngineViewTreemap.setHtml(html)
        except Exception as e:
            print(f"Error loading treemap: {e}")

    # 버튼 연결
    def connect_buttons(self):
        # 종목 업데이트 버튼 연결
        self.btn_update1.clicked.connect(lambda: self.start_thread(self.update_stocks, "kr"))
        self.btn_update2.clicked.connect(lambda: self.start_thread(self.update_stocks, "us"))
        self.btn_update3.clicked.connect(lambda: self.start_thread(self.update_stocks, "all"))
        self.btn_stop1.clicked.connect(lambda: self.update_stocks("stop"))
        self.btn_update4.clicked.connect(lambda: self.start_thread(self.update_specific_stock))
        self.ent_stock.returnPressed.connect(self.update_specific_stock)

        # 검색 조건 관련 버튼 연결
        self.SearchConditionInputButton.clicked.connect(self.save_search_condition)
        self.SearchConditionInputButton_2.clicked.connect(self.save_search_condition_1)
        self.SearchConditionInputButton_3.clicked.connect(self.save_search_condition_2)
        self.SearchConditionInputButton_4.clicked.connect(self.save_search_default_condition)
        self.radioButton.setChecked(True)

        # 종목 탐색 버튼 연결
        self.btn_search1.clicked.connect(lambda: self.start_thread(self.search_stock, "kr"))
        self.btn_search2.clicked.connect(lambda: self.start_thread(self.search_stock, "us"))
        self.btn_search3.clicked.connect(lambda: self.start_thread(self.search_stock, "all"))
        self.btn_stop2.clicked.connect(lambda: self.search_stock("stop"))

        # 기타 버튼 연결
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

        # 리스트 박스 초기화
        self.lb_search.addItems(self.load_companies_from_file("files/stock_search.txt"))
        self.lb_hold.addItems(self.load_companies_from_file("files/stock_hold.txt"))
        self.lb_int.addItems(self.load_companies_from_file("files/stock_interest.txt"))

        # 리스트 박스 아이템 클릭 시 이벤트 연결
        self.lb_hold.itemClicked.connect(self.btncmd2)
        self.lb_int.itemClicked.connect(self.btncmd3)
        self.lb_search.itemClicked.connect(self.btncmd)

        # 백테스팅 버튼 연결
        self.BacktestingButton.clicked.connect(self.start_backtesting)
        self.lineEdit_stock.returnPressed.connect(self.start_backtesting)
        self.portfolio.returnPressed.connect(self.run_portfolio_optimization)

        # 매수/매도 조건 버튼 연결
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.buyConditionDefaultButton.clicked.connect(self.save_buy_default_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)
        self.sellConditionDefaultButton.clicked.connect(self.save_sell_default_condition)

        # 최적화 버튼 연결
        self.optimize_button.clicked.connect(self.run_portfolio_optimization)

        # 트리맵 로드 버튼 연결 (UI에 btn_load_treemap 버튼이 있다고 가정)
        # self.btn_load_treemap.clicked.connect(self.load_treemap)

        # 조건 파일 로드
        self.load_conditions()

        # 보유 종목 포트폴리오 로드
        self.load_portfolio()

    # 조건 파일 로드 메서드
    def load_conditions(self):
        # 매수 조건 로드
        try:
            with open('files/buy_condition.txt', 'r') as file:
                buy_condition_text = file.read().strip()
                self.lineEditBuyCondition.setText(buy_condition_text)
        except Exception as e:
            print(f"Error reading buy_condition.txt: {e}")

        # 매도 조건 로드
        try:
            with open('files/sell_condition.txt', 'r') as file:
                sell_condition_text = file.read().strip()
                self.lineEditSellCondition.setText(sell_condition_text)
        except Exception as e:
            print(f"Error reading sell_condition.txt: {e}")

        # 검색 조건 로드
        try:
            with open('files/search_condition_1.txt', 'r') as file:
                self.search_condition_text_1 = file.read().strip()
                self.lineEditSearchCondition.setText(self.search_condition_text_1)
            with open('files/search_condition_2.txt', 'r') as file:
                self.search_condition_text_2 = file.read().strip()
        except Exception as e:
            print(f"Error reading search conditions: {e}")

    # 포트폴리오 로드 메서드
    def load_portfolio(self):
        try:
            with open('files/stock_hold.txt', 'r', encoding='utf-8') as file:
                stock_names = [line.strip() for line in file if line.strip()]
                stocks_string = ', '.join(stock_names)
                self.portfolio.setText(stocks_string)
        except Exception as e:
            print(f"Failed to load stock names: {e}")

    # 스레드 시작 메서드
    def start_thread(self, func, *args):
        Thread(target=func, args=args, daemon=True).start()

    # 파일에서 종목 리스트 로드
    def load_companies_from_file(self, filename):
        companies = []
        try:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf8") as f:
                    companies = [line.strip() for line in f if line]
        except Exception as e:
            print(f"Error loading companies from {filename}: {str(e)}")
        return companies

    # 종목 업데이트 메서드
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
            print(f"Error updating stocks: {str(e)}")

    # 특정 종목 가격 업데이트
    def update_stock_price(self, company, period):
        mk = DBUpdater_new.MarketDB()
        stock_list = mk.get_comp_info(company)

        val = stock_list[(stock_list['company'] == company) | (stock_list['code'] == company)]
        if val.empty:
            print(f"No data found for company: {company}")
            return

        code = val.iloc[0]['code']
        company = val.iloc[0]['company']

        db_updater = DBUpdater_new.DBUpdater()
        if val.iloc[0]['country'] == 'kr':
            df = db_updater.read_naver(code, period)
        elif val.iloc[0]['country'] == 'us':
            db_updater.ric_code()
            df = db_updater.read_yfinance(code, period)
        else:
            print(f"Unsupported country for company: {company}")
            df = None

        if df is not None:
            db_updater.replace_into_db(df, 0, code, company)

    # 특정 종목 업데이트 스레드
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
            print(f"Error updating a specific stock: {str(e)}")

    # 종목 탐색 메서드
    def search_stock(self, nation):
        self.clear_search_file()
        stock_list = self.prepare_stock_data(nation)
        self.analyze_and_save_results(stock_list)

    # 종목 데이터 준비
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

    # 분석 및 결과 저장
    def analyze_and_save_results(self, stock_list):
        for idx in range(len(stock_list)):
            if self.run:
                company = stock_list["company"].values[idx]
                mk = DBUpdater_new.MarketDB()
                mk.get_comp_info()
                df = mk.get_daily_price(company, "2022-01-01")

                self.process_stock_data(df)
                print(company)

                try:
                    search_condition_text = self.lineEditSearchCondition.text()
                    search_condition = eval(search_condition_text)

                    if search_condition:
                        self.lb_search.addItem(company)
                        self.write_to_search_file(company)
                except Exception as e:
                    print(str(e))

    # 주식 데이터 처리
    def process_stock_data(self, df):
        df.MA20 = df.close.rolling(window=20).mean()
        df.ENTOP = df.MA20 + df.MA20 * 0.1
        df['ENBOTTOM'] = df.MA20 - df.MA20 * 0.1
        df.U = df.close.diff().clip(lower=0)
        df.D = -df.close.diff().clip(upper=0)
        df.RS = (df.U.ewm(span=14, adjust=False).mean() / df.D.ewm(span=14, adjust=False).mean())
        df['RSI'] = 100 - (100 / (1 + df.RS))
        df["RSI_SIGNAL"] = df["RSI"].rolling(window=14).mean()

        ema_values = [5, 10, 20, 60, 130, 12, 26]
        for val in ema_values:
            df[f"ema{val}"] = df.close.ewm(span=val, adjust=False).mean()

        macd = df.ema12 - df.ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macdhist = macd - signal
        df = df.assign(
            macd=macd,
            signal=signal,
            macdhist=macdhist,
        ).dropna()
        df.index = pd.to_datetime(df.date)

    # 검색 파일 초기화
    def clear_search_file(self):
        with open("files/stock_search.txt", "w", encoding="utf8") as f:
            f.write("")

    # 검색 파일에 종목 추가
    def write_to_search_file(self, company):
        with open("files/stock_search.txt", "a", encoding="utf8") as f:
            f.write(f"{company}\n")

    # 종목 리스트 관리
    def manage_stock_list(self, action, listbox=None, filename=None, company=None):
        if action == "add":
            listbox.addItem(company)
            self.append_to_file(filename, company)
        elif action == "get":
            return listbox.currentItem().text()
        elif action == "update":
            self.write_list_to_file(filename, listbox)

    # 파일에 텍스트 추가
    def append_to_file(self, filename, text):
        with open(filename, "a", encoding="utf8") as f:
            f.write(f"{text}\n")

    # 리스트박스 내용을 파일에 쓰기
    def write_list_to_file(self, filename, listbox):
        with open(filename, "w", encoding="utf8") as f:
            for idx in range(listbox.count()):
                company = listbox.item(idx).text()
                f.write(f"{company}\n")

    # 검색 결과 리스트박스 버튼 이벤트
    def btncmd(self):
        try:
            company = self.lb_search.currentItem().text()
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")

    # 보유 리스트박스 버튼 이벤트
    def btncmd2(self):
        try:
            company = self.manage_stock_list("get", self.lb_hold)
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")

    # 관심 리스트박스 버튼 이벤트
    def btncmd3(self):
        try:
            company = self.manage_stock_list("get", self.lb_int)
            self.update_and_show_stock(company)
        except Exception as e:
            print(f"An error occurred: {e}")

    # 리스트박스 아이템 삭제 버튼 이벤트
    def btncmd_del1(self):
        try:
            self.lb_hold.takeItem(self.lb_hold.currentRow())
            self.manage_stock_list("update", self.lb_hold, "files/stock_hold.txt")
        except Exception as e:
            print(f"An error occurred: {e}")

    def btncmd_del2(self):
        try:
            self.lb_int.takeItem(self.lb_int.currentRow())
            self.manage_stock_list("update", self.lb_int, "files/stock_interest.txt")
        except Exception as e:
            print(f"An error occurred: {e}")

    # 종목 리스트 업데이트 및 그래프 표시
    def update_and_show_stock(self, company):
        self.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    # 관심/보유 리스트에 종목 추가 버튼
    def btn_addhold_clicked(self):
        selected_company = self.lb_search.currentItem().text()
        self.manage_stock_list(
            "add",
            self.lb_hold,
            "files/stock_hold.txt",
            selected_company
        )

    def btn_addint_clicked(self):
        selected_company = self.lb_search.currentItem().text()
        self.manage_stock_list(
            "add",
            self.lb_int,
            "files/stock_interest.txt",
            selected_company
        )

    # 종목 조회 메서드
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

    # 그래프 표시 메서드
    def show_graph(self, company):
        try:
            mk = DBUpdater_new.MarketDB()
            mk.get_comp_info(company)
            self.df = mk.get_daily_price(company, "2022-01-01")
            self.txt_company = company

            # 데이터 전처리
            self.process_show_graph_data()

            self.graphUpdated.emit("show_graph")
        except Exception as e:
            print(str(e))

    # 그래프 표시를 위한 데이터 전처리
    def process_show_graph_data(self):
        self.df["MA20"] = self.df["close"].rolling(window=20).mean()
        self.df["ENTOP"] = self.df["MA20"] + self.df["MA20"] * 0.1
        self.df["ENBOTTOM"] = self.df["MA20"] - self.df["MA20"] * 0.1

        self.df["RET20"] = (self.df["close"].pct_change(20) * 100).round(1)
        self.df["RET5"] = (self.df["close"].pct_change(5) * 100).round(1)
        self.df["RET1"] = (self.df["close"].pct_change(1) * 100).round(1)

        self.df.U = self.df.close.diff().clip(lower=0)
        self.df.D = -self.df.close.diff().clip(upper=0)
        self.df.RS = (self.df.U.ewm(span=14, adjust=False).mean() / self.df.D.ewm(span=14, adjust=False).mean())
        self.df['RSI'] = 100 - (100 / (1 + self.df.RS))
        self.df["RSI_SIGNAL"] = self.df["RSI"].rolling(window=14).mean()

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
        self.df = self.df.assign(fast_k=fast_k, slow_d=slow_d).dropna()

        self.df = self.df[-80:]
        self.ohlc = self.df[["number", "open", "high", "low", "close"]]

    # 주식 정보 표시
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

        if len(self.stocks) == 1:
            # 단일 종목 포트폴리오
            port_ret = [annual_ret[0]]
            port_risk = [np.sqrt(annual_cov.iloc[0, 0])]
            port_weights = [[1]]
            sharpe_ratio = [port_ret[0] / port_risk[0]]
        else:
            # 다중 종목 포트폴리오
            port_weights = np.random.random((20000, len(self.stocks)))
            port_weights /= np.sum(port_weights, axis=1)[:, np.newaxis]

            port_ret = np.dot(port_weights, annual_ret)
            port_risk = np.sqrt(np.einsum('ij,ji->i', port_weights @ annual_cov, port_weights.T))
            sharpe_ratio = port_ret / port_risk

        # 포트폴리오 데이터프레임 생성
        portfolio = {
            'Returns': port_ret,
            'Risk': port_risk,
            'Sharpe': sharpe_ratio
        }
        for i, s in enumerate(self.stocks):
            portfolio[s] = [weight[i] for weight in port_weights]

        self.df_port = pd.DataFrame(portfolio)
        self.df_port = self.df_port[['Returns', 'Risk', 'Sharpe'] + self.stocks]
        self.max_sharpe = self.df_port.loc[self.df_port['Sharpe'] == self.df_port['Sharpe'].max()]
        self.min_risk = self.df_port.loc[self.df_port['Risk'] == self.df_port['Risk'].min()]

        return self.df_port, self.max_sharpe, self.min_risk


class MyStrategy(bt.Strategy):
    def __init__(self, text_browser, lineEditBuyCondition, lineEditSellCondition):
        self.text_browser = text_browser
        self.lineEditBuy = lineEditBuyCondition
        self.lineEditSell = lineEditSellCondition

        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.initial_cash = self.broker.getvalue()
        self.final_price = self.dataclose[0]
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
                self.log(
                    f'BUY  : 주가 {order.executed.price:,.0f}, '
                    f'수량 {order.executed.size:,.0f}, '
                    f'수수료 {order.executed.comm:,.0f}, '
                    f'자산 {self.broker.getvalue():,.0f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                # 매도 시 수익률 계산
                profit_ratio = ((order.executed.price - self.buyprice) / self.buyprice) * 100
                self.log(
                    f'SELL : 주가 {order.executed.price:,.0f}, '
                    f'수량 {order.executed.size:,.0f}, '
                    f'수수료 {order.executed.comm:,.0f}, '
                    f'자산 {self.broker.getvalue():,.0f}, '
                    f'수익률 {profit_ratio:.2f}%'
                )
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
        try:
            return eval(condition_text)
        except Exception as e:
            self.log(f"Buy condition eval error: {e}")
            return False

    def sell_condition(self):
        condition_text = self.lineEditSell.text()
        try:
            return eval(condition_text)
        except Exception as e:
            self.log(f"Sell condition eval error: {e}")
            return False

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        log_text = f'[{dt.isoformat()}] {txt}'
        self.text_browser.append(log_text)


class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, str, name="print")

    def __init__(self):
        super().__init__()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def stop(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def start(self):
        sys.stdout = self
        sys.stderr = self

    def write(self, message):
        self.printOccur.emit(message, "black")

    def flush(self):
        pass

class DataCollector:
    def __init__(self):
        pass

    def industry_classification(self):
        result = []
        url = 'https://blog.naver.com/PostView.naver?blogId=taelyon&logNo=223507138478'
        req = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=True)
        soup = BeautifulSoup(req.text, features="lxml")
        box_type_l = soup.find("div", {"class": "se-table-container"})
        type_2 = box_type_l.find("table", {"class": "se-table-content"})
        tbody = type_2.find("tbody")
        trs = tbody.findAll("tr")
        stockInfos = []
        for tr in trs:
            try:
                tds = tr.findAll("td")
                industry = tds[0].text[1:-1]
                class_id = tds[1].text[1:-1]
                stockInfo = {"업종": industry, "분류": class_id}
                stockInfos.append(stockInfo)
            except Exception as e:
                pass
        list = stockInfos
        result += list

        df_industry = pd.DataFrame(result)
        df_industry = df_industry.drop(df_industry.index[0])
        return df_industry

    # 코스피 시세 정보 수집 함수
    def krx_sise_kospi(self, date_str):
        gen_req_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
        query_str_parms = {
            'locale': 'ko_KR',
            'mktId': 'STK',
            'trdDd': date_str,
            'money': '1',
            'csvxls_isNo': 'false',
            'name': 'fileDown',
            'url': 'dbms/MDC/STAT/standard/MDCSTAT03901'
        }
        headers = {
            'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020506',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
        }

        r = requests.get(gen_req_url, query_str_parms, headers=headers)
        gen_req_url = 'http://data.krx.co.kr/comm/fileDn/download_excel/download.cmd'
        form_data = {
            'code': r.content
        }

        r = requests.post(gen_req_url, form_data, headers=headers)

        df_sise = pd.read_excel(BytesIO(r.content), engine='openpyxl')
        return df_sise

    # 코스닥 시세 정보 수집 함수
    def krx_sise_kosdaq(self, date_str):
        gen_req_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
        query_str_parms = {
            'locale': 'ko_KR',
            'mktId': 'KSQ',
            'segTpCd': 'ALL',
            'trdDd': date_str,
            'money': '1',
            'csvxls_isNo': 'false',
            'name': 'fileDown',
            'url': 'dbms/MDC/STAT/standard/MDCSTAT03901'
        }
        headers = {
            'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020506',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
        }

        r = requests.get(gen_req_url, query_str_parms, headers=headers)
        gen_req_url = 'http://data.krx.co.kr/comm/fileDn/download_excel/download.cmd'
        form_data = {
            'code': r.content
        }

        r = requests.post(gen_req_url, form_data, headers=headers)

        df_sise = pd.read_excel(BytesIO(r.content), engine='openpyxl')
        return df_sise

    # 최근 거래일의 코스피/코스닥 시세 정보 수집
    def get_recent_sise(self):
        date = datetime.today()
        while True:
            date_str = date.strftime('%Y%m%d')
            df_sise_kospi = self.krx_sise_kospi(date_str)
            df_sise_kosdaq = self.krx_sise_kosdaq(date_str)

            if (df_sise_kospi['종가'].apply(pd.to_numeric, errors='coerce').notnull().all() and
                df_sise_kosdaq['종가'].apply(pd.to_numeric, errors='coerce').notnull().all()):
                break
            date -= timedelta(days=1)

        df_sise_kospi = df_sise_kospi[['종목코드', '종목명', '등락률', '시가총액']]
        df_sise_kosdaq = df_sise_kosdaq[['종목코드', '종목명', '등락률', '시가총액']]
        df_combined = pd.concat([df_sise_kospi, df_sise_kosdaq])

        # 종목 정보 수집
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        response = requests.get(url)
        response.encoding = 'euc-kr'  # 또는 'cp949'
        df_info = pd.read_html(StringIO(response.text))[0]
        df_info = df_info[['종목코드', '업종']]
        df_info['종목코드'] = df_info['종목코드'].apply(lambda x: f'{x:06d}')

        df_merged = pd.merge(df_combined, df_info, on='종목코드')

        df_industry = self.industry_classification()

        df_final = pd.merge(df_merged, df_industry, on='업종', how='left')

        # 시가총액이 가장 큰 상위 500개 종목 추출
        df_top500 = df_final.sort_values(by='시가총액', ascending=False).head(500).reset_index(drop=True)

        return df_top500

    # 트리맵 생성 함수
    def create_treemap(self, df_top500):
        # Define custom color scale
        color_scale = [
            (0.0, "rgb(246,53,56)"),
            (0.16, "rgb(191,65,68)"),
            (0.33, "rgb(139,67,78)"),
            (0.5, "rgb(63,71,84)"),
            (0.66, "rgb(52,118,80)"),
            (0.83, "rgb(49,158,79)"),
            (1.0, "rgb(48,191,86)")
        ]

        fig = px.treemap(
            df_top500,
            path=['분류', '종목명'],
            values='시가총액',
            color='등락률',
            color_continuous_scale=color_scale,
            range_color=[-2.5, 2.5],
            custom_data=['등락률'],
            # width=1921, height=971,
        )
        fig.update_traces(
            texttemplate='<b>%{label}</b><br>%{customdata[0]:.2f}%',
            textposition='middle center',
            marker_line=dict(color='gray'),
            textfont=dict(color='white'),
            hovertemplate='<b>%{label}</b><br>시가총액: %{value}<br>등락률: %{customdata[0]:.2f}%<extra></extra>'
        )
        fig.update_layout(coloraxis_showscale=False)
        return fig

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MyMainWindow()
    mainWindow.showMaximized()
    # mainWindow.show()
    sys.exit(app.exec_())
