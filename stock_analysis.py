from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from threading import Thread
from Investar import DBUpdater_new
from Investar import Analyzer
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
import os
import time
from PyQt5.QtWidgets import QMainWindow, QApplication, QShortcut
from PyQt5.QtCore import *
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
import logging

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.codes = {}
        self.run = True

        self.connect_buttons()
        chromedriver_autoinstaller.install()

        # 분석 화면
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.verticalLayout_2.addWidget(self.canvas)

        # 로그 화면
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self._append_text(x))

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

    def update_specific_stock(self):
        try:
            db_updater = DBUpdater_new.DBUpdater()
            company = self.ent_stock.text()
            if self.btn_period1.isChecked():
                db_updater.update_stock_price(company, 1)
            elif self.btn_period2.isChecked():
                db_updater.update_stock_price(company, 2)
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
                len_code = stock_list["len_code"].values[idx]
                mk = Analyzer.MarketDB()
                df = mk.get_daily_price(company, "2020-07-01")

                df["MA20"] = df["close"].rolling(window=20).mean()
                df["ENTOP"] = df["MA20"] + df["MA20"] * 0.1
                df["ENBOTTOM"] = df["MA20"] - df["MA20"] * 0.1
                # df['stddev'] = df['close'].rolling(window=20).std()
                # df['upper'] = df['MA20'] + (df['stddev'] * 2)
                # df['lower'] = df['MA20'] - (df['stddev'] * 2)
                df["VOL5"] = df["volume"].rolling(window=5).mean()
                # df['value'] = df['close'] * df['volume']
                # df['RET20'] = round(((df['close'] - df['close'].shift(20)) / df['close'].shift(20)) * 100, 1)
                # df['RET5'] = round(((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100, 1)
                # df['RET1'] = round(((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * 100, 1)
                df["U"] = df["close"].diff().clip(lower=0)
                df["D"] = -df["close"].diff().clip(upper=0)
                df["RS"] = (
                    df.U.rolling(window=14).mean() / df.D.rolling(window=14).mean()
                )
                df["RSI"] = 100 - 100 / (1 + df["RS"])
                df = df.dropna()

                ema5 = df.close.ewm(span=5).mean()
                ema10 = df.close.ewm(span=10).mean()
                ema20 = df.close.ewm(span=20).mean()
                ema60 = df.close.ewm(span=60).mean()
                ema130 = df.close.ewm(span=130).mean()
                ema12 = df.close.ewm(span=12).mean()
                ema26 = df.close.ewm(span=26).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9).mean()
                macdhist = macd - signal
                df = df.assign(
                    ema5=ema5,
                    ema10=ema10,
                    ema20=ema20,
                    ema130=ema130,
                    ema60=ema60,
                    ema12=ema12,
                    ema26=ema26,
                    macd=macd,
                    signal=signal,
                    macdhist=macdhist,
                ).dropna()
                df.index = pd.to_datetime(df.date)

                ndays_high = df.high.rolling(window=14, min_periods=1).max()
                ndays_low = df.low.rolling(window=14, min_periods=1).min()
                fast_k = (df.close - ndays_low) / (ndays_high - ndays_low) * 100
                slow_d = fast_k.rolling(window=3).mean()
                df = df.assign(fast_k=fast_k, slow_d=slow_d).dropna()

                print(company)

                try:
                    if (
                        df.RSI.values[-1] < 30
                        and df.macdhist.values[-1] > df.macdhist.values[-2]
                        and df.macd.values[-1] > df.macd.values[-2]
                        and df.close.values[-1] > df.open.values[-1]
                    ) or (df.close.values[-1] < df.ENBOTTOM.values[-1]
                    and df.close.values[-1] > df.open.values[-1]):
                        self.lb_search.addItem(company)
                        self.write_to_search_file(company)
                except Exception as e:
                    print(str(e))

    def update_and_show_stock(self, company):
        db_updater = DBUpdater_new.DBUpdater()
        db_updater.update_stock_price(company, 1)
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
        db_updater = DBUpdater_new.DBUpdater()
        db_updater.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    # 그래프
    def show_graph(self, company):
        try:
            mk = Analyzer.MarketDB()
            df = mk.get_daily_price(company, "2021-01-01")

            df["MA20"] = df["close"].rolling(window=20).mean()
            df["ENTOP"] = df["MA20"] + df["MA20"] * 0.1
            df["ENBOTTOM"] = df["MA20"] - df["MA20"] * 0.1

            df["RET20"] = ((df["close"].pct_change(20)) * 100).round(1)
            df["RET5"] = ((df["close"].pct_change(5)) * 100).round(1)
            df["RET1"] = ((df["close"].pct_change(1)) * 100).round(1)

            df["U"] = df["close"].diff().clip(lower=0)
            df["D"] = -df["close"].diff().clip(upper=0)
            df["RS"] = df.U.rolling(window=14).mean() / df.D.rolling(window=14).mean()
            df["RSI"] = 100 - 100 / (1 + df["RS"])

            ema_values = [5, 10, 20, 60, 130, 12, 26]
            for val in ema_values:
                df[f"ema{val}"] = df.close.ewm(span=val).mean()

            macd = df.ema12 - df.ema26
            signal = macd.ewm(span=9).mean()
            macdhist = macd - signal
            df = df.assign(macd=macd, signal=signal, macdhist=macdhist)
            df["number"] = df.index.map(mdates.date2num)
            df.index = pd.to_datetime(df.date)

            ndays_high = df.high.rolling(window=14, min_periods=1).max()
            ndays_low = df.low.rolling(window=14, min_periods=1).min()
            fast_k = (df.close - ndays_low) / (ndays_high - ndays_low) * 100
            slow_d = fast_k.rolling(window=3).mean()
            df = df.assign(fast_k=fast_k, slow_d=slow_d)
            df = df[-80:]
            ohlc = df[["number", "open", "high", "low", "close"]]
            # df['len_code'] = df.code.str.len()

            plt.rc("font", family="Malgun Gothic")
            plt.rcParams["axes.unicode_minus"] = False
            plt.clf()

            p1 = plt.subplot2grid((9, 4), (0, 0), rowspan=4, colspan=4)
            p1.grid()
            day = str(df.date.values[-1])
            title = (company+" ("+day+ " : "+ str(df.close.values[-1])+ ")"+"\n"
                + " 수익률: "+ "(20일 "+ str(df.RET20.values[-1])+ "%) "
                + "(5일 "+ str(df.RET5.values[-1])+ "%) "
                + "(1일 "+ str(df.RET1.values[-1])+ "%)"
                + " / 이동평균: "+"(EMA5 " + str(round(df.ema5.values[-1],1))+") "
                + "(EMA10 " + str(round(df.ema10.values[-1],1))+") "
                + "(EMA20 " + str(round(df.ema20.values[-1],1))+") "
            )
            p1.set_title(title)
            # p1.plot(df.index, df['upper'], 'r--')
            # p1.plot(df.index, df['lower'], 'c--')
            # p1.plot(df.index, df['ENTOP'], 'r--')
            p1.plot(df.index, df["ENBOTTOM"], "k--")
            p1.fill_between(df.index, df["ENTOP"], df["ENBOTTOM"], color="0.93")
            candlestick_ohlc(
                p1, ohlc.values, width=0.6, colorup="red", colordown="blue"
            )
            p1.plot(df.index, df["ema5"], "m", alpha=0.7, label="EMA5")
            p1.plot(df.index, df["ema10"], color="limegreen", alpha=0.7, label="EMA10")
            p1.plot(df.index, df["ema20"], color="orange", alpha=0.7, label="EMA20")
            # p1.plot(df.index, df['ema130'], color='black', alpha=0.7, label='EMA130')

            for i in range(len(df.close)):
                if (
                    (
                        df.close.values[i] < df.ENBOTTOM.values[i]
                        and df.RSI.values[i] < 30
                    )
                    and (df.macd.values[i - 1] < df.macd.values[i])
                    and (df.close.values[i] > df.open.values[i])
                ):
                    p1.plot(
                        df.index.values[i],
                        df.low.values[i] * 0.98,
                        "r^",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif (df.RSI.values[i - 1] < 30 < df.RSI.values[i]) or (
                        df.macdhist.values[i - 1] < 0 < df.macdhist.values[i]
                ):
                    p1.plot(
                        df.index.values[i],
                        df.low.values[i] * 0.98,
                        "y^",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif ((df.ema5.values[i - 1] > df.ema10.values[i - 1]
                        and df.ema5.values[i] < df.ema10.values[i]
                        and df.macd.values[i - 1] > df.macd.values[i])
                    or (df.macdhist.values[i - 1] > 0 > df.macdhist.values[i])
                ):
                    p1.plot(
                        df.index.values[i],
                        df.low.values[i] * 0.98,
                        "bv",
                        markersize=8,
                        markeredgecolor="black",
                    )
                elif (
                    (df.RSI.values[i - 1] > 70 > df.RSI.values[i]
                     and df.macd.values[i - 1] > df.macd.values[i])
                    or (
                        df.RSI.values[i] > 70
                    and df.macd.values[i - 1] > df.macd.values[i]
                    and (df.close.values[i] < df.open.values[i])
                ) or (
                    (df.close.values[i - 1] > df.ENTOP.values[i - 1]
                        and df.close.values[i] < df.ENTOP.values[i])
                    and (df.macd.values[i - 1] > df.macd.values[i])
                )):
                    p1.plot(
                        df.index.values[i],
                        df.low.values[i] * 0.98,
                        "gv",
                        markersize=8,
                        markeredgecolor="black",
                    )

            # plt2 = p1.twinx()
            # plt2.bar(df.index, df['volume'], color='deeppink', alpha=0.5, label='VOL')
            # plt2.set_ylim(0, max(df.volume * 5))
            p1.legend(loc="best")
            plt.setp(p1.get_xticklabels(), visible=False)

            p4 = plt.subplot2grid((9, 4), (4, 0), rowspan=1, colspan=4)
            p4.grid(axis="x")
            p4.bar(df.index, df["volume"], color="deeppink", alpha=0.5, label="VOL")
            plt.setp(p4.get_xticklabels(), visible=False)

            p3 = plt.subplot2grid((9, 4), (5, 0), rowspan=2, colspan=4, sharex=p4)
            p3.grid()
            # p3.plot(df.index, df['fast_k'], color='c', label='%K')
            p3.plot(df.index, df["slow_d"], "c--", label="%D")
            p3.plot(df.index, df["RSI"], color="red", label="RSI")
            p3.fill_between(
                df.index,
                df["RSI"],
                70,
                where=df["RSI"] >= 70,
                facecolor="red",
                alpha=0.3,
            )
            p3.fill_between(
                df.index,
                df["RSI"],
                30,
                where=df["RSI"] <= 30,
                facecolor="blue",
                alpha=0.3,
            )
            p3.set_yticks([0, 20, 30, 70, 80, 100])
            p3.legend(loc="best")
            plt.setp(p3.get_xticklabels(), visible=False)

            p2 = plt.subplot2grid((9, 4), (7, 0), rowspan=2, colspan=4, sharex=p4)
            p2.grid()
            p2.bar(df.index, df["macdhist"], color="m", label="MACD-Hist")
            p2.plot(df.index, df["macd"], color="c", label="MACD")
            p2.plot(df.index, df["signal"], "g--")
            p2.legend(loc="best")

            plt.subplots_adjust(hspace=0.05)

            self.canvas.draw()

        except Exception as e:
            print(str(e))

    # 주식 정보
    def show_info(self, company):
        try:
            mk = Analyzer.MarketDB()
            stock_list = mk.get_comp_info()
            db_updater = DBUpdater_new.DBUpdater()
            ric_code = db_updater.ric_code()
            val = stock_list[
                (stock_list["company"] == company) | (stock_list["code"] == company)
            ]
            if not val.empty:
                if val.iloc[0]["country"] == "kr":
                    company = val.iloc[0]["code"]
                    stock_url = (
                        f"https://m.stock.naver.com/domestic/stock/{company}/total"
                    )
                elif val.iloc[0]["country"] == "us":
                    code = val.iloc[0]["code"]
                    ric = ric_code[ric_code["code"] == code]
                    if not ric.empty:
                        company = ric.iloc[0]["ric"]
                        stock_url = f"https://m.stock.naver.com/worldstock/stock/{company}/total"

                # chromedriver_autoinstaller.install()
                options = webdriver.ChromeOptions()
                options.add_argument("headless")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                service = Service("chromedriver")
                service.creationflags = 0x08000000
                self.driver = webdriver.Chrome(service=service, options=options)
                self.webEngineView.load(QUrl(stock_url))
                # self.driver.quit()

        except Exception as e:
            print(str(e))
        finally:
            if hasattr(self, "driver"):
                self.driver.close()

    # 로그 화면
    def _append_text(self, msg):
        self.log_widget.moveCursor(QtGui.QTextCursor.End)
        self.log_widget.insertPlainText(msg)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)


    # 프로그램 UI
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1900, 990)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.frame_control = QtWidgets.QFrame(self.centralwidget)
        self.frame_control.setGeometry(QtCore.QRect(0, 0, 200, 991))
        self.frame_control.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.frame_control.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_control.setObjectName("frame_control")

        # 종목 업데이트
        self.groupBox_update = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_update.setGeometry(QtCore.QRect(10, 10, 181, 111))
        self.groupBox_update.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_update.setObjectName("groupBox_update")

        self.verticalLayoutWidget = QtWidgets.QWidget(self.groupBox_update)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 14, 161, 91))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")

        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")

        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setSpacing(1)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")

        self.btn_update1 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update1.setObjectName("btn_update1")
        self.horizontalLayout_5.addWidget(self.btn_update1)

        self.btn_update2 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update2.setObjectName("btn_update2")
        self.horizontalLayout_5.addWidget(self.btn_update2)

        self.btn_update3 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update3.setObjectName("btn_update3")
        self.horizontalLayout_5.addWidget(self.btn_update3)

        self.btn_stop1 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_stop1.setObjectName("btn_stop1")
        self.horizontalLayout_5.addWidget(self.btn_stop1)

        self.verticalLayout.addLayout(self.horizontalLayout_5)
        self.ent_stock = QtWidgets.QLineEdit(self.verticalLayoutWidget)
        self.ent_stock.setObjectName("ent_stock")
        self.verticalLayout.addWidget(self.ent_stock)

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setSpacing(20)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        self.btn_period1 = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.btn_period1.setObjectName("btn_period1")
        self.btn_period1.setChecked(True)

        self.horizontalLayout_2.addWidget(self.btn_period1)
        self.btn_period2 = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.btn_period2.setObjectName("btn_period2")
        self.horizontalLayout_2.addWidget(self.btn_period2)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.btn_update4 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update4.setObjectName("btn_update4")
        self.verticalLayout.addWidget(self.btn_update4)

        # 보유 종목
        self.groupBox_hold = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_hold.setGeometry(QtCore.QRect(10, 440, 181, 221))
        self.groupBox_hold.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_hold.setObjectName("groupBox_hold")

        self.verticalLayoutWidget_3 = QtWidgets.QWidget(self.groupBox_hold)
        self.verticalLayoutWidget_3.setGeometry(QtCore.QRect(10, 14, 161, 201))
        self.verticalLayoutWidget_3.setObjectName("verticalLayoutWidget_3")

        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_3)
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")

        self.lb_hold = QtWidgets.QListWidget(self.verticalLayoutWidget_3)
        self.lb_hold.setObjectName("lb_hold")
        self.verticalLayout_5.addWidget(self.lb_hold)

        self.horizontalLayout_10 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_10.setSpacing(0)
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")

        self.btn2 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        # self.btn2.setIconSize(QtCore.QSize(16, 16))
        self.btn2.setObjectName("btn2")
        self.horizontalLayout_10.addWidget(self.btn2)

        self.btn_del1 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.btn_del1.setObjectName("btn_del1")
        self.horizontalLayout_10.addWidget(self.btn_del1)

        self.btn_addint1 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.btn_addint1.setObjectName("btn_addint1")
        self.horizontalLayout_10.addWidget(self.btn_addint1)

        self.verticalLayout_5.addLayout(self.horizontalLayout_10)

        # 관심 종목
        self.groupBox_int = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_int.setGeometry(QtCore.QRect(10, 670, 181, 221))
        self.groupBox_int.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_int.setObjectName("groupBox_int")

        self.verticalLayoutWidget_4 = QtWidgets.QWidget(self.groupBox_int)
        self.verticalLayoutWidget_4.setGeometry(QtCore.QRect(10, 14, 161, 201))
        self.verticalLayoutWidget_4.setObjectName("verticalLayoutWidget_4")

        self.verticalLayout_6 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_4)
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_6.setObjectName("verticalLayout_6")

        self.lb_int = QtWidgets.QListWidget(self.verticalLayoutWidget_4)
        self.lb_int.setObjectName("lb_int")
        self.verticalLayout_6.addWidget(self.lb_int)

        self.horizontalLayout_11 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_11.setSpacing(0)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")

        self.btn3 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn3.setIconSize(QtCore.QSize(16, 16))
        self.btn3.setObjectName("btn3")
        self.horizontalLayout_11.addWidget(self.btn3)

        self.btn_del2 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn_del2.setObjectName("btn_del2")
        self.horizontalLayout_11.addWidget(self.btn_del2)

        self.btn_addhold1 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn_addhold1.setObjectName("btn_addhold1")
        self.horizontalLayout_11.addWidget(self.btn_addhold1)

        self.verticalLayout_6.addLayout(self.horizontalLayout_11)

        # 종목 조회
        self.groupBox_find = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_find.setGeometry(QtCore.QRect(10, 900, 181, 71))
        self.groupBox_find.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_find.setObjectName("groupBox_find")

        self.verticalLayoutWidget_5 = QtWidgets.QWidget(self.groupBox_find)
        self.verticalLayoutWidget_5.setGeometry(QtCore.QRect(10, 14, 161, 51))
        self.verticalLayoutWidget_5.setObjectName("verticalLayoutWidget_5")

        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_5)
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_7.setSpacing(0)
        self.verticalLayout_7.setObjectName("verticalLayout_7")

        self.ent = QtWidgets.QLineEdit(self.verticalLayoutWidget_5)
        self.ent.setObjectName("ent")
        self.verticalLayout_7.addWidget(self.ent)

        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")

        self.btn_find = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_find.setIconSize(QtCore.QSize(16, 16))
        self.btn_find.setObjectName("btn_find")
        self.horizontalLayout_4.addWidget(self.btn_find)

        self.btn_addhold2 = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_addhold2.setObjectName("btn_addhold2")
        self.horizontalLayout_4.addWidget(self.btn_addhold2)

        self.btn_addint2 = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_addint2.setObjectName("btn_addint2")
        self.horizontalLayout_4.addWidget(self.btn_addint2)

        self.verticalLayout_7.addLayout(self.horizontalLayout_4)

        # 종목 탐색
        self.groupBox_search = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_search.setGeometry(QtCore.QRect(10, 130, 181, 301))
        self.groupBox_search.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_search.setObjectName("groupBox_search")

        self.verticalLayoutWidget_2 = QtWidgets.QWidget(self.groupBox_search)
        self.verticalLayoutWidget_2.setGeometry(QtCore.QRect(10, 14, 161, 281))
        self.verticalLayoutWidget_2.setObjectName("verticalLayoutWidget_2")

        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")

        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")

        self.btn_search1 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search1.setObjectName("btn_search1")
        self.horizontalLayout_3.addWidget(self.btn_search1)

        self.btn_search2 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search2.setObjectName("btn_search2")
        self.horizontalLayout_3.addWidget(self.btn_search2)

        self.btn_search3 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search3.setObjectName("btn_search3")
        self.horizontalLayout_3.addWidget(self.btn_search3)

        self.btn_stop2 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_stop2.setObjectName("btn_stop2")
        self.horizontalLayout_3.addWidget(self.btn_stop2)

        self.verticalLayout_4.addLayout(self.horizontalLayout_3)
        self.lb_search = QtWidgets.QListWidget(self.verticalLayoutWidget_2)
        self.lb_search.setObjectName("lb_search")
        self.verticalLayout_4.addWidget(self.lb_search)

        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")

        self.btn = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        # self.btn.setIconSize(QtCore.QSize(16, 16))
        self.btn.setObjectName("btn")
        self.horizontalLayout_6.addWidget(self.btn)

        self.btn_addhold = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_addhold.setObjectName("btn_addhold")
        self.horizontalLayout_6.addWidget(self.btn_addhold)

        self.btn_addint = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_addint.setObjectName("btn_addint")
        self.horizontalLayout_6.addWidget(self.btn_addint)

        self.verticalLayout_4.addLayout(self.horizontalLayout_6)

        # 그래프
        self.frame_plot = QtWidgets.QFrame(self.centralwidget)
        self.frame_plot.setGeometry(QtCore.QRect(200, 0, 1000, 900))
        self.frame_plot.setFrameShadow(QtWidgets.QFrame.Raised)

        self.frame_plot.setObjectName("frame_plot")
        self.verticalLayoutWidget_6 = QtWidgets.QWidget(self.frame_plot)
        self.verticalLayoutWidget_6.setGeometry(QtCore.QRect(0, 0, 991, 891))
        self.verticalLayoutWidget_6.setObjectName("verticalLayoutWidget_6")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_6)
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        # 정보 화면
        self.frame_info = QtWidgets.QFrame(self.centralwidget)
        self.frame_info.setGeometry(QtCore.QRect(1200, 0, 701, 901))
        self.frame_info.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_info.setObjectName("frame_info")

        self.webEngineView = QtWebEngineWidgets.QWebEngineView(self.frame_info)
        self.webEngineView.setGeometry(QtCore.QRect(0, 0, 701, 891))
        self.webEngineView.setUrl(QtCore.QUrl("https://m.stock.naver.com/index.html#/"))
        self.webEngineView.setObjectName("webEngineView")

        # 로그
        self.frame_log = QtWidgets.QFrame(self.centralwidget)
        self.frame_log.setGeometry(QtCore.QRect(200, 900, 1701, 91))
        self.frame_log.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_log.setObjectName("frame_log")

        self.log_widget = QtWidgets.QTextBrowser(self.frame_log)
        self.log_widget.setGeometry(QtCore.QRect(0, 0, 1701, 90))
        self.log_widget.setObjectName("log_widget")

        MainWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        # 프린트
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self)
        shortcut.activated.connect(self.print)

    def print(self):
        printer = QPrinter()
        printer.setPageOrientation(QtGui.QPageLayout.Landscape)
        painter = QtGui.QPainter()
        painter.begin(printer)
        screen = self.grab()
        painter.drawPixmap(10, 10, screen)
        painter.end()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "증권 데이터 분석 v2.0"))
        self.groupBox_update.setTitle(_translate("MainWindow", "종목 업데이트"))
        self.btn_update1.setText(_translate("MainWindow", "한국"))
        self.btn_update2.setText(_translate("MainWindow", "미국"))
        self.btn_update3.setText(_translate("MainWindow", "전체"))
        self.btn_stop1.setText(_translate("MainWindow", "중단"))
        self.btn_period1.setText(_translate("MainWindow", "최근"))
        self.btn_period2.setText(_translate("MainWindow", "장기"))
        self.btn_update4.setText(_translate("MainWindow", "업데이트"))
        self.groupBox_hold.setTitle(_translate("MainWindow", "보유 종목"))
        self.btn2.setText(_translate("MainWindow", "선택"))
        self.btn_del1.setText(_translate("MainWindow", "삭제"))
        self.btn_addint1.setText(_translate("MainWindow", "관심"))

        self.groupBox_int.setTitle(_translate("MainWindow", "관심 종목"))
        self.btn3.setText(_translate("MainWindow", "선택"))
        self.btn_del2.setText(_translate("MainWindow", "삭제"))
        self.btn_addhold1.setText(_translate("MainWindow", "보유"))

        self.groupBox_find.setTitle(_translate("MainWindow", "종목 조회"))
        self.btn_find.setText(_translate("MainWindow", "선택"))
        self.btn_addhold2.setText(_translate("MainWindow", "보유"))
        self.btn_addint2.setText(_translate("MainWindow", "관심"))
        self.groupBox_search.setTitle(_translate("MainWindow", "종목 탐색"))
        self.btn_search1.setText(_translate("MainWindow", "한국"))
        self.btn_search2.setText(_translate("MainWindow", "미국"))
        self.btn_search3.setText(_translate("MainWindow", "전체"))
        self.btn_stop2.setText(_translate("MainWindow", "중단"))
        self.btn.setText(_translate("MainWindow", "선택"))
        self.btn_addhold.setText(_translate("MainWindow", "보유"))
        self.btn_addint.setText(_translate("MainWindow", "관심"))


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
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
