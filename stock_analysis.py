from threading import Thread
from Investar import DBUpdater_new, Analyzer
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import *
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from gui import MainWindow, StdoutRedirect

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)


class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.codes = {}
        self.run = True

        self.ui = MainWindow()
        self.ui.setupUi(self)
        self.connect_buttons()
        chromedriver_autoinstaller.install()

        # 분석 화면
        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.ui.verticalLayout_2.addWidget(self.canvas)

        # 로그 화면
        self._stdout = StdoutRedirect()
        self._stdout.start()
        self._stdout.printOccur.connect(lambda x: self.ui._append_text(x))

    def connect_buttons(self):
        # 종목 업데이트

        self.ui.btn_update1.clicked.connect(lambda: self.start_thread(self.update_stocks, "kr"))
        self.ui.btn_update2.clicked.connect(lambda: self.start_thread(self.update_stocks, "us"))
        self.ui.btn_update3.clicked.connect(lambda: self.start_thread(self.update_stocks, "all"))
        self.ui.btn_stop1.clicked.connect(lambda: self.update_stocks("stop"))
        self.ui.btn_update4.clicked.connect(lambda: self.start_thread(self.update_specific_stock))


        # 종목 탐색

        self.ui.btn_search1.clicked.connect(lambda: self.start_thread(self.search_stock, "kr"))
        self.ui.btn_search2.clicked.connect(lambda: self.start_thread(self.search_stock, "us"))
        self.ui.btn_search3.clicked.connect(lambda: self.start_thread(self.search_stock, "all"))
        self.ui.btn_stop2.clicked.connect(lambda: self.search_stock("stop"))

        self.ui.btn.clicked.connect(self.btncmd)
        self.ui.btn_addhold.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.ui.lb_hold,
                "files/stock_hold.txt",
                self.ui.lb_search.currentItem().text(),
            )
        )
        self.ui.btn_addint.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.ui.lb_int,
                "files/stock_interest.txt",
                self.ui.lb_search.currentItem().text(),
            )
        )

        self.ui.lb_search.addItems(self.load_companies_from_file("files/stock_search.txt"))

        # 보유 종목

        self.ui.lb_hold.addItems(self.load_companies_from_file("files/stock_hold.txt"))

        self.ui.btn2.clicked.connect(self.btncmd2)
        self.ui.btn_del1.clicked.connect(self.btncmd_del1)
        self.ui.btn_addint1.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.ui.lb_int,
                "files/stock_interest.txt",
                self.ui.lb_hold.currentItem().text(),
            )
        )

        # 관심 종목

        self.ui.lb_int.addItems(self.load_companies_from_file("files/stock_interest.txt"))

        self.ui.btn3.clicked.connect(self.btncmd3)
        self.ui.btn_del2.clicked.connect(self.btncmd_del2)
        self.ui.btn_addhold1.clicked.connect(
            lambda: self.manage_stock_list(
                "add",
                self.ui.lb_hold,
                "files/stock_hold.txt",
                self.ui.lb_int.currentItem().text(),
            )
        )

        # 종목 조회
        self.ui.btn_find.clicked.connect(self.find_stock)
        self.ui.btn_addhold2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.ui.lb_hold, "files/stock_hold.txt", self.ui.ent.text()
            )
        )
        self.ui.btn_addint2.clicked.connect(
            lambda: self.manage_stock_list(
                "add", self.ui.lb_int, "files/stock_interest.txt", self.ui.ent.text()
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
            company = self.ui.ent_stock.text()
            if self.ui.btn_period1.isChecked():
                self.update_stock_price(company, 1)
            elif self.ui.btn_period2.isChecked():
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
            self.ui.lb_search.clear()
        elif nation == "all":
            self.run = True
            self.ui.lb_search.clear()
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
                        and df.close.values[-1] > df.open.values[-1]
                    ) or (df.close.values[-1] < df.ENBOTTOM.values[-1]
                    and df.close.values[-1] > df.open.values[-1]):
                        self.ui.lb_search.addItem(company)
                        self.write_to_search_file(company)
                except Exception as e:
                    print(str(e))

    def update_and_show_stock(self, company):
        self.update_stock_price(company, 1)
        Thread(target=self.show_graph, args=(company,), daemon=True).start()
        self.show_info(company)

    def btncmd(self):
        company = self.ui.lb_search.currentItem().text()
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
        company = self.manage_stock_list("get", self.ui.lb_hold)
        self.update_and_show_stock(company)

    def btncmd_del1(self):
        self.ui.lb_hold.takeItem(self.ui.lb_hold.currentRow())
        self.manage_stock_list("update", self.ui.lb_hold, "files/stock_hold.txt")

    def btncmd3(self):
        company = self.manage_stock_list("get", self.ui.lb_int)
        self.update_and_show_stock(company)

    def btncmd_del2(self):
        self.ui.lb_int.takeItem(self.ui.lb_int.currentRow())
        self.manage_stock_list("update", self.ui.lb_int, "files/stock_interest.txt")

    def find_stock(self):
        company = self.ui.ent.text()
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
            df = mk.get_daily_price(company, "2022-01-01")

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
                df[f"ema{val}"] = df.close.ewm(span=val, adjust=False).mean()

            macd = df.ema12 - df.ema26
            signal = macd.ewm(span=9, adjust=False).mean()
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
                elif (df.RSI.values[i - 1] < 30 < df.RSI.values[i] and df.macd.values[i-1] < df.macd.values[i]) or (
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

                self.ui.webEngineView.load(QtCore.QUrl(stock_url))

        except Exception as e:
            print(f"Error in show_info: {str(e)}")


    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MyMainWindow()
    mainWindow.show()
    sys.exit(app.exec_())