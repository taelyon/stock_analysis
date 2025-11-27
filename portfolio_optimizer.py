import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for Qt compatibility
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

        def optimize_portfolio(self, stock_list, start_date=None):
            if not stock_list:
                self.text_browser.clear()
                self.text_browser.append('No stocks provided for optimization.')
                return

            start_date = start_date or '2022-01-01'
            df_port = pd.DataFrame()
            skipped = []

            for symbol in stock_list:
                price_df = self.mk.get_daily_price(symbol, start_date)
                if price_df is None or price_df.empty or 'close' not in price_df:
                    skipped.append(symbol)
                    continue
                df_port[symbol] = price_df['close']

            if df_port.empty:
                self.text_browser.clear()
                self.text_browser.append('No price data available for the selected stocks and start date.')
                if skipped:
                    self.text_browser.append('Skipped symbols: ' + ', '.join(skipped))
                return

            available_stocks = list(df_port.columns)
            if skipped:
                self.text_browser.append('Skipped symbols: ' + ', '.join(skipped))

            daily_ret = df_port.pct_change().dropna()
            if daily_ret.empty:
                self.text_browser.append('Not enough price history after the selected start date to run optimization.')
                return

            annual_ret = daily_ret.mean() * 252
            daily_cov = daily_ret.cov()
            annual_cov = daily_cov * 252

            port_ret, port_risk, port_weights, sharpe_ratio = self.generate_portfolios(
                available_stocks, annual_ret, annual_cov
            )

            portfolio = {'Returns': port_ret, 'Risk': port_risk, 'Sharpe': sharpe_ratio}
            for idx, symbol in enumerate(available_stocks):
                portfolio[symbol] = [weight[idx] for weight in port_weights]

            results_df = pd.DataFrame(portfolio)
            max_sharpe = results_df.loc[results_df['Sharpe'] == results_df['Sharpe'].max()]
            min_risk = results_df.loc[results_df['Risk'] == results_df['Risk'].min()]

            self.display_results(results_df, max_sharpe, min_risk)

        def generate_portfolios(self, stock_list, annual_ret, annual_cov):
            if len(stock_list) == 1:
                port_ret = [annual_ret.iloc[0]]
                port_risk = [np.sqrt(annual_cov.iloc[0, 0])]
                port_weights = [[1.0]]
                sharpe_ratio = [port_ret[0] / port_risk[0] if port_risk[0] else 0.0]
            else:
                port_weights = np.random.random((20000, len(stock_list)))
                port_weights /= np.sum(port_weights, axis=1)[:, np.newaxis]
                port_ret = np.dot(port_weights, annual_ret)
                port_risk = np.sqrt(np.einsum('ij,ji->i', port_weights @ annual_cov, port_weights.T))
                sharpe_ratio = port_ret / port_risk
            return port_ret, port_risk, port_weights, sharpe_ratio

        def display_results(self, df_port, max_sharpe, min_risk):
            self.text_browser.clear()
            self.text_browser.setHtml(
                self.format_html_output(max_sharpe, 'Max Sharpe Ratio') +
                self.format_html_output(min_risk, 'Min Risk')
            )
            self.plot_portfolio(df_port, max_sharpe, min_risk)

        def format_html_output(self, df, title):
            if df.empty:
                return f"<b>{title}:</b> No Data"
                
            row = df.iloc[0]
            
            html = f"<h3 style='color: #ffffff; margin-bottom: 5px;'>{title}</h3>"
            html += "<table style='border-collapse: collapse; width: 100%; border: 1px solid #555; font-size: 12px; color: #ffffff; background-color: #333333;'>"
            
            # Header Row
            html += "<tr style='background-color: #444444; color: #ffffff;'>"
            metrics = ['Returns', 'Risk', 'Sharpe']
            
            # Metrics Headers
            for metric in metrics:
                if metric in row.index:
                    html += f"<th style='border: 1px solid #555; padding: 6px; text-align: center;'>{metric}</th>"
            
            # Stock Headers
            for idx in row.index:
                if idx not in metrics:
                    html += f"<th style='border: 1px solid #555; padding: 6px; text-align: center;'>{idx}</th>"
            html += "</tr>"
            
            # Value Row
            html += "<tr>"
            
            # Metrics Values
            for metric in metrics:
                if metric in row.index:
                    val = row[metric]
                    if metric == 'Returns':
                        val_str = f"{val * 100:.2f}%"
                    else:
                        val_str = f"{val:.4f}"
                    html += f"<td style='border: 1px solid #555; padding: 6px; text-align: center; color: #ffffff;'>{val_str}</td>"
            
            # Stock Values
            for idx in row.index:
                if idx not in metrics:
                    val = row[idx]
                    val_str = f"{val * 100:.2f}%"
                    html += f"<td style='border: 1px solid #555; padding: 6px; text-align: center; color: #ffffff;'>{val_str}</td>"
            html += "</tr>"
            
            html += "</table>"
            return html

        def plot_portfolio(self, df_port, max_sharpe, min_risk):
            while self.layout.count():
                item = self.layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            plt.close('all')
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
        print(f'PortfolioOptimizer initialization error: {e}')
