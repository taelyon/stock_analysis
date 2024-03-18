from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

import backtrader as bt
import pandas as pd
from Investar import Analyzer

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Ensure shared OpenGL contexts
QtWidgets.QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

class MyApplication(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('stock.ui', self)
        self.company = '065350'
        self.start_date = '2022-01-01'
        self.initUI()

    def initUI(self):
        cerebro = self.setup_cerebro()
        self.display_portfolio_value(cerebro, 'Initial')
        cerebro.run()
        self.display_portfolio_value(cerebro, 'Final')
        self.display_graph(cerebro)

    def setup_cerebro(self):
        cerebro = bt.Cerebro()
        cerebro.addstrategy(MyStrategy, text_browser=self.textBrowser)
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
        figures = cerebro.plot(iplot=False, style='candlestick')
        figure = figures[0][0]
        canvas = FigureCanvas(figure)
        self.verticalLayout_7.addWidget(canvas)

class MyStrategy(bt.Strategy):
    def __init__(self, text_browser):
        self.text_browser = text_browser
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
        return ((self.rsi[-1] < 30 < self.rsi[0]) and (self.macdhist.macd[-1] < self.macdhist.macd[0])) or (self.macdhist.histo[-1] < 0 < self.macdhist.histo[0])

    def sell_condition(self):
        return ((self.ema5[-1] > self.ema10[-1]) and (self.ema5[0] < self.ema10[0]) and (self.macdhist.macd[-1] > self.macdhist.macd[0])) or (self.macdhist.histo[-1] > 0 > self.macdhist.histo[0])

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        log_text = f'[{dt.isoformat()}] {txt}'
        self.text_browser.append(log_text)

if __name__ == '__main__':
    app = QApplication([])
    window = MyApplication()
    window.show()
    app.exec_()

