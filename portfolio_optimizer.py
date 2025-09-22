import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Qt 환경에 적합한 백엔드
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import DBUpdater_new

class PortfolioOptimizer:
    try:
        def __init__(self, text_browser, layout):
            self.text_browser = text_browser
            self.layout = layout
            self.mk = DBUpdater_new.MarketDB()
            self.canvas = None

        def optimize_portfolio(self, stock_list):
            df_port = pd.DataFrame()
            for s in stock_list:
                df_port[s] = self.mk.get_daily_price(s, '2022-01-01')['close']
            
            daily_ret = df_port.pct_change() 
            annual_ret = daily_ret.mean() * 252
            daily_cov = daily_ret.cov() 
            annual_cov = daily_cov * 252

            port_ret, port_risk, port_weights, sharpe_ratio = self.generate_portfolios(stock_list, annual_ret, annual_cov)

            portfolio = {'Returns': port_ret, 'Risk': port_risk, 'Sharpe': sharpe_ratio}
            for i, s in enumerate(stock_list): 
                portfolio[s] = [weight[i] for weight in port_weights]

            df_port = pd.DataFrame(portfolio)
            max_sharpe = df_port.loc[df_port['Sharpe'] == df_port['Sharpe'].max()]
            min_risk = df_port.loc[df_port['Risk'] == df_port['Risk'].min()]
            
            self.display_results(df_port, max_sharpe, min_risk)

        def generate_portfolios(self, stock_list, annual_ret, annual_cov):
            if len(stock_list) == 1:
                port_ret = [annual_ret[0]]
                port_risk = [np.sqrt(annual_cov.iloc[0, 0])]
                port_weights = [[1]]
                sharpe_ratio = [port_ret[0] / port_risk[0]]
            else:
                port_weights = np.random.random((20000, len(stock_list)))
                port_weights /= np.sum(port_weights, axis=1)[:, np.newaxis]
                port_ret = np.dot(port_weights, annual_ret)
                port_risk = np.sqrt(np.einsum('ij,ji->i', port_weights @ annual_cov, port_weights.T))
                sharpe_ratio = port_ret / port_risk
            return port_ret, port_risk, port_weights, sharpe_ratio

        def display_results(self, df_port, max_sharpe, min_risk):
            self.text_browser.clear()
            self.text_browser.setHtml(self.format_html_output(max_sharpe, "Max Sharpe Ratio") +
                                    '<br><br>' + 
                                    self.format_html_output(min_risk, "Min Risk"))
            self.plot_portfolio(df_port, max_sharpe, min_risk)

        def format_html_output(self, df, title):
            df_percent = df.copy()
            for col in df_percent.columns:
                if col not in ['Returns', 'Risk', 'Sharpe']:
                    df_percent[col] = df_percent[col].apply(lambda x: f"{x * 100:.2f}%")
                elif col == 'Returns':
                    df_percent[col] = f"{df_percent[col].iloc[0] * 100:.2f}%"
            df_percent['Risk'] = df_percent['Risk'].round(3)
            df_percent['Sharpe'] = df_percent['Sharpe'].round(3)
            return f'<b>{title}:</b>' + df_percent.to_html(index=False, border=0)

        def plot_portfolio(self, df_port, max_sharpe, min_risk):
            # 기존 레이아웃의 모든 위젯 제거 (백테스팅 캔버스 포함)
            while self.layout.count():
                item = self.layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            # Matplotlib Figure 상태 정리
            plt.close('all')

            # 기존 캔버스 참조 정리 (deleteLater() 중복 방지)
            self.canvas = None

            fig = Figure()
            ax = fig.add_subplot(111)
            cmap = plt.cm.viridis
            normalize = plt.Normalize(vmin=df_port['Sharpe'].min(), vmax=df_port['Sharpe'].max())
            colors = cmap(normalize(df_port['Sharpe'].values))

            ax.scatter(df_port['Risk'], df_port['Returns'], c=colors, edgecolors='k')
            ax.scatter(x=max_sharpe['Risk'], y=max_sharpe['Returns'], c='r', marker='*', s=300)
            ax.scatter(x=min_risk['Risk'], y=min_risk['Returns'], c='r', marker='X', s=200)
            ax.set_title('Portfolio Optimization')
            ax.set_xlabel('Risk')
            ax.set_ylabel('Expected Returns')

            self.canvas = FigureCanvas(fig)
            self.layout.addWidget(self.canvas)
            self.canvas.draw()
    except Exception as e:
        print(f"PortfolioOptimizer initialization error: {e}")