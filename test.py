import sys
from PyQt5 import QtWidgets, uic, QtWebEngineWidgets
from PyQt5.QtWidgets import QApplication
import backtrader as bt
from datetime import datetime
import pandas as pd
from Investar import Analyzer
import io
import contextlib
from PyQt5.QtCore import Qt


QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

class MyStrategy(bt.Strategy):
    def __init__(self):
        # Strategy setup remains unchanged
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.order = None
        self.buyprice = None
        self.buycomm = None        
        self.rsi = bt.indicators.RSI_SMA(self.data.close, period=14)
        self.ema5 = bt.indicators.EMA(self.data.close, period=5)
        self.ema10 = bt.indicators.EMA(self.data.close, period=10)
        self.macdhist = bt.indicators.MACDHisto(self.data.close)
        # Add other initialization parameters as required

    def notify_order(self, order):  # ①
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:  # ② 
            if order.isbuy():
                self.log(f'BUY  : 주가 {order.executed.price:,.0f}, '
                    f'수량 {order.executed.size:,.0f}, '
                    f'수수료 {order.executed.comm:,.0f}, '        
                    f'자산 {self.cerebro.broker.getvalue():,.0f}') 
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else: 
                self.log(f'SELL : 주가 {order.executed.price:,.0f}, '
                    f'수량 {order.executed.size:,.0f}, '
                    f'수수료 {order.executed.comm:,.0f}, '
                    f'자산 {self.cerebro.broker.getvalue():,.0f}') 
            self.bar_executed = len(self)
        elif order.status in [order.Canceled]:
            self.log('ORDER CANCELD')
        elif order.status in [order.Margin]:
            self.log('ORDER MARGIN')
        elif order.status in [order.Rejected]:
            self.log('ORDER REJECTED')
        self.order = None

    def next(self):
        if not self.position:
            if (self.rsi[-1] < 30 < self.rsi[0] and self.macdhist.macd[-1] < self.macdhist.macd[0]) or (self.macdhist.histo[-1] < 0 < self.macdhist.histo[0]):
                self.order = self.buy()
        else:
            if ((self.ema5[-1] > self.ema10[-1]) and (self.ema5[0] < self.ema10[0]) and (self.macdhist.macd[-1] > self.macdhist.macd[0])) or (self.macdhist.histo[-1]> 0 > self.macdhist.histo[0]):
                self.order = self.sell()

    def log(self, txt, dt=None):
        # Custom logging method to redirect output to Qt TextBrowser
        dt = self.datas[0].datetime.date(0)
        msg = f'[{dt.isoformat()}] {txt}'
        window.append_text(msg)  # Append text to the QTextBrowser in the UI

    # Other strategy methods remain unchanged

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        # Load the UI Page
        uic.loadUi('stock.ui', self)

    def append_text(self, txt):
        self.textBrowser.append(txt)  # Assuming 'textBrowser' is the QTextBrowser's name

    def run_backtrader(self):
        self.cerebro = bt.Cerebro()
        self.cerebro.addstrategy(MyStrategy)

        mk = Analyzer.MarketDB()
        df = mk.get_daily_price('065350', '2022-01-01')  # Example company and start date
        df.date = pd.to_datetime(df.date)
        data = bt.feeds.PandasData(dataname=df, datetime='date')

        self.cerebro.adddata(data)
        self.cerebro.broker.setcash(10000000)
        self.cerebro.broker.setcommission(commission=0.0014)
        self.cerebro.addsizer(bt.sizers.PercentSizer, percents=90)

        # Redirect stdout to capture strategy logs
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()

        # Run Backtrader
        self.cerebro.run()

        # Restore stdout
        sys.stdout = old_stdout
        self.append_text(mystdout.getvalue())  # Display captured output in QTextBrowser

        # Optionally, display final portfolio value
        final_value = f'Final Portfolio Value: {self.cerebro.broker.getvalue():,.0f} KRW'
        self.append_text(final_value)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.run_backtrader()  # Automatically run backtrader when starting the app
    sys.exit(app.exec_())
