import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import re

class ChartManager:
    def __init__(self, chart_layout, backtest_layout, logo_widget):
        """생성자: 차트 레이아웃 설정 및 한글 폰트 적용"""
        # [FIX] 한글 폰트 깨짐 방지를 위한 설정
        try:
            plt.rcParams['font.family'] = 'Malgun Gothic'
            plt.rcParams['axes.unicode_minus'] = False  # 마이너스 부호 깨짐 방지
        except Exception as e:
            print(f"한글 폰트 설정 중 오류 발생: {e}")
            print("차트의 한글이 깨져 보일 수 있습니다. 'Malgun Gothic' 폰트 설치를 확인해주세요.")

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

        # 기존 캔버스 제거 및 새로 생성
        if self.canvas_main is not None:
            self.chart_layout.removeWidget(self.canvas_main)
            self.canvas_main.deleteLater()
            self.canvas_main = None
            self.fig_main = None

        # 새 Figure와 Canvas 생성
        self.fig_main = plt.figure()
        self.canvas_main = FigureCanvas(self.fig_main)
        self.chart_layout.addWidget(self.canvas_main)

        if df is None or df.empty:
            ax = self.fig_main.add_subplot(111)
            ax.text(0.5, 0.5, f"'{company}'의 차트 데이터를 표시할 수 없습니다.", 
                    horizontalalignment='center', verticalalignment='center')
            self.canvas_main.draw()
            return

        # 차트에 표시할 데이터를 최근 3개월(약 65 거래일)으로 제한합니다.
        df = df.iloc[-65:]

        if df.empty:
            ax = self.fig_main.add_subplot(111)
            ax.text(0.5, 0.5, f"'{company}'의 최근 3개월 데이터가 없습니다.",
                    horizontalalignment='center', verticalalignment='center')
            self.canvas_main.draw()
            return

        # 기존 플롯 로직
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
        day_str = df.index[-1].strftime('%Y-%m-%d') if not df.empty else 'N/A'
        close_price = df['close'].iloc[-1] if not df.empty else 0
        ret20 = df['RET20'].iloc[-1] if 'RET20' in df.columns and not df.empty else 'N/A'
        ret5 = df['RET5'].iloc[-1] if 'RET5' in df.columns and not df.empty else 'N/A'
        ret1 = df['RET1'].iloc[-1] if 'RET1' in df.columns and not df.empty else 'N/A'
        
        title = (
            f"{company} ({day_str}: {format(round(close_price, 2), ',')} )\n"
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
                # 조건식에서 df[-1]과 같은 상대적 인덱싱을 현재 행 기준으로 변환
                # 이 부분은 현재 구조에서는 복잡하므로, 탐색 조건식을 iloc 기반으로 작성하는 것을 권장합니다.
                # 현재 로직은 단순화를 위해 그대로 두지만, 복잡한 조건식에서 오류가 발생할 수 있습니다.
                if search_condition_1 and eval(search_condition_1, {}, {'df': df.iloc[:i+1]}):
                     ax.plot(df.index[i], df['low'].iloc[i] * 0.97, "y^", markersize=8, markeredgecolor="black")
                if search_condition_2 and eval(search_condition_2, {}, {'df': df.iloc[:i+1]}):
                     ax.plot(df.index[i], df['low'].iloc[i] * 0.97, "r^", markersize=8, markeredgecolor="black")
            except Exception as e:
                print(f"신호 조건 평가 중 오류 발생 (인덱스 {i}): {e}")
                pass

            if ((df['ema5'].iloc[i-1] > df['ema10'].iloc[i-1] and df['ema5'].iloc[i] < df['ema10'].iloc[i]) or
                (df['macdhist'].iloc[i-1] > 0 > df['macdhist'].iloc[i])):
                ax.plot(df.index[i], df['high'].iloc[i] * 1.03, "bv", markersize=8, markeredgecolor="black")
                
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
        """백테스팅 결과를 별도 창 없이 UI 내부에 플롯합니다."""
        # 기존 레이아웃의 모든 위젯 제거 (최적화 차트 포함)
        while self.backtest_layout.count():
            item = self.backtest_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Matplotlib Figure 상태 정리
        plt.close('all')

        # 기존 백테스팅 캔버스 참조 정리 (deleteLater() 중복 방지)
        self.canvas_backtest = None

        fig_backtest = None
        try:
            # iplot=False로 창 띄우기 방지
            figures = cerebro.plot(iplot=False, style='candlestick', barup='green', fmt_x_ticks='%Y-%m-%d')
            
            if not figures or not figures[0]:
                raise ValueError("결과 없음 (거래 미발생 등)")
            else:
                fig_backtest = figures[0][0]

        except Exception as e:
            print(f"백테스팅 결과 플롯 생성 중 오류: {e}")
            fig_backtest = plt.figure()
            ax = fig_backtest.add_subplot(111)
            ax.text(0.5, 0.5, f"백테스팅 결과를 표시할 수 없습니다.\n오류: {e}", 
                    horizontalalignment='center', verticalalignment='center', wrap=True)
        
        if fig_backtest:
            self.canvas_backtest = FigureCanvas(fig_backtest)
            self.backtest_layout.addWidget(self.canvas_backtest)
            self.canvas_backtest.draw()
        
        # canvas_main 상태 보호
        if self.canvas_main is not None:
            self.canvas_main.draw()  # 주식 차트 캔버스 갱신