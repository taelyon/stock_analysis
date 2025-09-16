import backtrader as bt
import pandas as pd
from chart_manager import ChartManager

class Backtester:
    try:
        def __init__(self, text_browser, chart_manager):
            self.text_browser = text_browser
            # 외부에서 생성된 ChartManager 인스턴스를 주입받습니다.
            self.chart_manager = chart_manager

        def run_backtesting(self, df, company, start_date, buy_condition, sell_condition):
            self.text_browser.clear()
            
            cerebro = bt.Cerebro()
            cerebro.addstrategy(MyStrategy, self.text_browser, buy_condition, sell_condition)
            
            df['date'] = pd.to_datetime(df['date'])
            data = bt.feeds.PandasData(dataname=df, datetime='date')
            cerebro.adddata(data)
            
            initial_cash = 10000000
            cerebro.broker.setcash(initial_cash)
            cerebro.broker.setcommission(commission=0.0014)
            cerebro.addsizer(bt.sizers.PercentSizer, percents=90)

            self.text_browser.append(f'Initial Portfolio Value: {initial_cash:,.0f} KRW')
            cerebro.run()
            
            final_portfolio_value = cerebro.broker.getvalue()
            self.text_browser.append(f'Final Portfolio Value: {final_portfolio_value:,.0f} KRW')
            self.text_browser.append(f'Profit/Loss: {((final_portfolio_value - initial_cash) / initial_cash) * 100:.2f}%')

            # 주입받은 chart_manager를 사용하여 결과를 플롯합니다.
            self.chart_manager.plot_backtest_results(cerebro)
    except Exception as e:
        print(f"Backtester initialization error: {e}")

class MyStrategy(bt.Strategy):
    try:
        def __init__(self, text_browser, buy_condition, sell_condition):
            self.text_browser = text_browser
            self.buy_condition_str = buy_condition
            self.sell_condition_str = sell_condition
            self.order = None
            self.buyprice = None
            
            # 지표 설정
            self.rsi = bt.indicators.RSI(self.data.close, period=14)
            self.ema5 = bt.indicators.EMA(self.data.close, period=5)
            self.ema20 = bt.indicators.EMA(self.data.close, period=20)
            self.macdhist = bt.indicators.MACDHisto(self.data.close)
            
        def notify_order(self, order):
            if order.status in [order.Submitted, order.Accepted]:
                return
            if order.status in [order.Completed]:
                if order.isbuy():
                    self.log(f'BUY: Price {order.executed.price:,.0f}, Qty {order.executed.size:,.0f}')
                    self.buyprice = order.executed.price
                else:
                    # SOLVED: self.buyprice가 설정되지 않은 경우를 대비한 안전장치 추가
                    if self.buyprice is not None:
                        profit_ratio = ((order.executed.price - self.buyprice) / self.buyprice) * 100
                        self.log(f'SELL: Price {order.executed.price:,.0f}, Qty {order.executed.size:,.0f}, Profit {profit_ratio:.2f}%')
                    else:
                        self.log(f'SELL: Price {order.executed.price:,.0f}, Qty {order.executed.size:,.0f} (수익률 계산 불가)')
            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log(f'Order Canceled/Margin/Rejected: {order.info}')
            self.order = None

        def next(self):
            if not self.position:
                if self.buy_condition():
                    self.order = self.buy()
            else:
                if self.sell_condition():
                    self.order = self.sell()

        def buy_condition(self):
            try:
                return eval(self.buy_condition_str)
            except Exception as e:
                self.log(f"Error in buy condition: {e}")
                return False

        def sell_condition(self):
            try:
                return eval(self.sell_condition_str)
            except Exception as e:
                self.log(f"Error in sell condition: {e}")
                return False

        def log(self, txt, dt=None):
            dt = dt or self.datas[0].datetime.date(0)
            self.text_browser.append(f'[{dt.isoformat()}] {txt}')
    except Exception as e:
        print(f"MyStrategy initialization error: {e}")

