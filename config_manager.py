import os
from threading import Lock
from utils import resource_path

class ConfigManager:
    try:
        def __init__(self, config_dir='files'):
            if not os.path.isabs(config_dir):
                config_dir = resource_path(config_dir)
            self.config_dir = config_dir
            self.file_lock = Lock()
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir, exist_ok=True)

        def load_condition(self, filename):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                try:
                    with open(filepath, 'r') as f:
                        return f.read().strip()
                except FileNotFoundError:
                    return ""

        def save_condition(self, filename, condition):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                with open(filepath, 'w') as f:
                    f.write(condition)

        def load_search_conditions(self):
            cond1 = self.load_condition('search_condition_1.txt')
            cond2 = self.load_condition('search_condition_2.txt')
            return cond1, cond2

        def save_default_search_conditions(self):
            cond1 = '(df.RSI.values[-2] < 30 < df.RSI.values[-1] and df.macd.values[-2] < df.macd.values[-1])'
            cond2 = '(df.open.values[-1] < df.ENBOTTOM.values[-1] or df.RSI.values[-1] < 30)'
            self.save_condition('search_condition_1.txt', cond1)
            self.save_condition('search_condition_2.txt', cond2)
            return cond1, cond2

        def save_default_buy_condition(self):
            cond = '((self.rsi[-1] < 30 < self.rsi[0]) and (self.macdhist.macd[-1] < self.macdhist.macd[0]))'
            self.save_condition('buy_condition.txt', cond)
            return cond

        def save_default_sell_condition(self):
            cond = '((self.ema5[-1] > self.ema20[-1]) and (self.ema5[0] < self.ema20[0]))'
            self.save_condition('sell_condition.txt', cond)
            return cond
            
        def load_stock_list(self, filename):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return [line.strip() for line in f if line.strip()]
                except FileNotFoundError:
                    return []

        def save_stock_list(self, filename, stock_list):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                with open(filepath, 'w', encoding='utf-8') as f:
                    for stock in stock_list:
                        f.write(f"{stock}\n")

        def add_stock_to_list(self, filename, company):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(f"{company}\n")

        def remove_stock_from_list(self, filename, company_to_remove):
            filepath = os.path.join(self.config_dir, filename)           
            with self.file_lock:
                lines = []
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                except FileNotFoundError:
                    print(f"! 오류: 파일을 찾을 수 없습니다 - '{filepath}'")
                    return

                lines_to_keep = [
                    line for line in lines 
                    if line.strip() != company_to_remove.strip()
                ]                

                if len(lines) == len(lines_to_keep):
                    print("! 경고: 파일에서 일치하는 종목을 찾지 못해 아무것도 삭제되지 않았습니다.")
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.writelines(lines_to_keep)
                except Exception as e:
                    print(f"! 치명적 오류: 파일 쓰기 중 예외 발생 - {e}")
    except Exception as e:
        print(f"ConfigManager initialization error: {e}")