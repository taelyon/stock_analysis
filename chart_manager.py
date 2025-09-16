import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import re

class ChartManager:
    def __init__(self, chart_layout, backtest_layout, logo_widget):
        self.chart_layout = chart_layout
        self.backtest_layout = backtest_layout
        self.logo_widget = logo_widget

        if self.chart_layout is not None:
            self.fig_main = plt.figure()
            self.canvas_main = FigureCanvas(self.fig_main)
            self.chart_layout.addWidget(self.canvas_main)

        # 백테스팅 결과를 표시할 Canvas 위젯을 초기에 None으로 설정
        self.canvas_backtest = None


    def plot_stock_chart(self, df, company, search_condition_1, search_condition_2):
        if self.logo_widget:
            self.logo_widget.hide()

        if df is None or df.empty:
            self.fig_main.clear()
            ax = self.fig_main.add_subplot(111)
            ax.text(0.5, 0.5, f"'{company}'의 차트 데이터를 표시할 수 없습니다.", 
                    horizontalalignment='center', verticalalignment='center')
            self.canvas_main.draw()
            return
            
        # 차트에 표시할 데이터를 최근 3개월(약 65 거래일)으로 제한합니다.
        # 보조지표 계산은 전체 기간 데이터로 이루어지므로 정확도가 유지됩니다.
        df = df.iloc[-65:]

        if df.empty:
            self.fig_main.clear()
            ax = self.fig_main.add_subplot(111)
            ax.text(0.5, 0.5, f"'{company}'의 최근 3개월 데이터가 없습니다.",
                    horizontalalignment='center', verticalalignment='center')
            self.canvas_main.draw()
            return

        self.fig_main.clear()
        
        p1 = plt.subplot2grid((9, 4), (0, 0), rowspan=4, colspan=4)
        p4 = plt.subplot2grid((9, 4), (4, 0), rowspan=1, colspan=4, sharex=p1)
        p3 = plt.subplot2grid((9, 4), (5, 0), rowspan=2, colspan=4, sharex=p1)
        p2 = plt.subplot2grid((9, 4), (7, 0), rowspan=2, colspan=4, sharex=p1)

        self.plot_main_chart(p1, df, company, search_condition_1, search_condition_2)
        self.plot_volume_chart(p4, df)
        self.plot_rsi_chart(p3, df)
        self.plot_macd_chart(p2, df)
        
        plt.setp(p1.get_xticklabels(), visible=False)
        plt.setp(p3.get_xticklabels(), visible=False)
        plt.setp(p4.get_xticklabels(), visible=False)

        plt.subplots_adjust(hspace=0.05)
        self.canvas_main.draw()

    def plot_main_chart(self, ax, df, company, search_condition_1, search_condition_2):
        day = str(df.date.values[-1]) if 'date' in df.columns and not df.empty else 'N/A'
        close_price = df.close.values[-1] if 'close' in df.columns and not df.empty else 0
        ret20 = df.RET20.values[-1] if 'RET20' in df.columns and not df.empty else 'N/A'
        ret5 = df.RET5.values[-1] if 'RET5' in df.columns and not df.empty else 'N/A'
        ret1 = df.RET1.values[-1] if 'RET1' in df.columns and not df.empty else 'N/A'
        
        title = (
            f"{company} ({day}: {format(round(close_price, 2), ',')} )\n"
            + f" 수익률: (20일 {ret20}%) "
            + f"(5일 {ret5}%) "
            + f"(1일 {ret1}%)"
        )
        ax.set_title(title)
        ax.grid(True)
        
        korean_colors = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='black', volume='gray')
        korean_style = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=korean_colors, gridcolor='gray', gridstyle='--', facecolor='white', edgecolor='black')
        mpf.plot(df, type='candle', ax=ax, style=korean_style, show_nontrading=True)
        
        ax.plot(df.index, df["ema5"], "m", alpha=0.7, label="EMA5")
        ax.plot(df.index, df["ema10"], color="limegreen", alpha=0.7, label="EMA10")
        ax.plot(df.index, df["ema20"], color="orange", alpha=0.7, label="EMA20")
        ax.plot(df.index, df["Bollinger_Upper"], "b--")
        ax.plot(df.index, df["Bollinger_Lower"], "b--")
        
        self.plot_signals(ax, df, search_condition_1, search_condition_2)
        ax.legend(loc="best")

    def plot_signals(self, ax, df, search_condition_1, search_condition_2):
        for i in range(1, len(df.close)):
            try:
                if search_condition_1 and eval(re.sub('df', 'df', re.sub(r'\[-(\d+)\]', lambda x: f'[i-{int(x.group(1)) - 1}]', search_condition_1))):
                    ax.plot(df.index.values[i], df.low.values[i] * 0.97, "y^", markersize=8, markeredgecolor="black")
                if search_condition_2 and eval(re.sub('df', 'df', re.sub(r'\[-(\d+)\]', lambda x: f'[i-{int(x.group(1)) - 1}]', search_condition_2))):
                    ax.plot(df.index.values[i], df.low.values[i] * 0.97, "r^", markersize=8, markeredgecolor="black")
            except Exception as e:
                print(f"Error evaluating signal condition at index {i}: {e}")

            if ((df.ema5.values[i - 1] > df.ema10.values[i - 1] and df.ema5.values[i] < df.ema10.values[i]) or
                (df.macdhist.values[i - 1] > 0 > df.macdhist.values[i])):
                ax.plot(df.index.values[i], df.high.values[i] * 1.03, "bv", markersize=8, markeredgecolor="black")
                
    def plot_volume_chart(self, ax, df):
        ax.bar(df.index, df["volume"], color="deeppink", alpha=0.5, label="VOL")
        ax.grid(axis="x")

    def plot_rsi_chart(self, ax, df):
        ax.plot(df.index, df["RSI_SIGNAL"], "blue", label="RSI_SIGNAL")
        ax.plot(df.index, df["RSI"], color="red", label="RSI")
        ax.fill_between(df.index, df["RSI"], 70, where=df["RSI"] >= 70, facecolor="red", alpha=0.3)
        ax.fill_between(df.index, df["RSI"], 30, where=df["RSI"] <= 30, facecolor="blue", alpha=0.3)
        ax.set_yticks([0, 20, 30, 70, 80, 100])
        ax.grid()
        ax.legend(loc="best")

    def plot_macd_chart(self, ax, df):
        ax.bar(df.index, df["macdhist"], color="m", label="MACD-Hist")
        ax.plot(df.index, df["macd"], color="c", label="MACD")
        ax.plot(df.index, df["signal"], "g--")
        ax.grid()
        ax.legend(loc="best")

    def plot_backtest_results(self, cerebro):
        # 레이아웃에 있는 모든 위젯을 제거하여 깨끗한 상태에서 시작합니다.
        for i in reversed(range(self.backtest_layout.count())): 
            widget = self.backtest_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        fig_backtest = None
        try:
            # cerebro.plot() 호출
            figures = cerebro.plot(style='candlestick', barup='green', fmt_x_ticks='%Y-%m-%d')
            
            if not figures or not figures[0]:
                raise ValueError("결과 없음 (거래 미발생 등)")
            else:
                # 성공적으로 플롯을 생성한 경우, 해당 Figure를 사용
                fig_backtest = figures[0][0]

        except Exception as e:
            # 플롯 생성 중 오류가 발생했거나 결과가 없는 경우, 오류 메시지를 담은 새 Figure를 생성
            print(f"Error plotting backtest results: {e}")
            fig_backtest = plt.figure()
            ax = fig_backtest.add_subplot(111)
            ax.text(0.5, 0.5, f"백테스팅 결과를 표시할 수 없습니다.\n오류: {e}", 
                    horizontalalignment='center', verticalalignment='center', wrap=True)
        
        # 준비된 Figure(성공 결과 또는 오류 메시지)로 새 Canvas를 만들어 레이아웃에 추가
        if fig_backtest:
            self.canvas_backtest = FigureCanvas(fig_backtest)
            self.backtest_layout.addWidget(self.canvas_backtest)
            self.canvas_backtest.draw()

