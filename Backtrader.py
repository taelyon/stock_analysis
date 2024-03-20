from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

import backtrader as bt
import pandas as pd
from Investar import Analyzer

# import matplotlib
# matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Ensure shared OpenGL contexts
QtWidgets.QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

class MyApplication(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('stock.ui', self)
        # self.start_date = '2022-01-01'
        self.setupUi()

    def setupUi(self):
        # Backtesting 버튼 클릭 시그널에 메서드 연결
        self.BacktestingButton.clicked.connect(self.start_backtesting)

        # lineEdit_stock에서 엔터 키를 누를 때 start_backtesting 메서드를 호출
        self.lineEdit_stock.returnPressed.connect(self.start_backtesting)

        # 버튼 클릭 시그널에 메서드 연결
        self.buyConditionInputButton.clicked.connect(self.save_buy_condition)
        self.sellConditionInputButton.clicked.connect(self.save_sell_condition)

        self.dateEdit_start.setDate(QtCore.QDate(2022, 1, 1))

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
        # 이전 결과 및 로그를 지우는 코드
        self.textBrowser.clear()  # 텍스트 브라우저의 내용을 비웁니다.
          
        self.company = self.lineEdit_stock.text()
        self.start_date = self.dateEdit_start.date().toString("yyyy-MM-dd")

        # 백테스팅 설정 및 실행
        cerebro = self.setup_cerebro()
        self.display_portfolio_value(cerebro, 'Initial')
        cerebro.run()
        self.display_portfolio_value(cerebro, 'Final')

        self.display_graph(cerebro)

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

        self.verticalLayout_7.addWidget(self.canvas_back)
        self.canvas_back.draw()

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

if __name__ == '__main__':
    app = QApplication([])
    window = MyApplication()
    window.show()
    app.exec_()

