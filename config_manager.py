import os
from threading import Lock

class ConfigManager:
    try:
        def __init__(self, config_dir='files'):
            self.config_dir = config_dir
            self.file_lock = Lock()
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)

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

        def add_stock_to_list(self, filename, company):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(f"{company}\n")

        def remove_stock_from_list(self, filename, company_to_remove):
            filepath = os.path.join(self.config_dir, filename)
            with self.file_lock:
                lines = self.load_stock_list(filename)
                lines = [line for line in lines if line != company_to_remove]
                with open(filepath, 'w', encoding='utf-8') as f:
                    for line in lines:
                        f.write(f"{line}\n")
    except Exception as e:
        print(f"ConfigManager initialization error: {e}")