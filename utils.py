import sys
from PyQt5.QtCore import QObject, pyqtSignal

class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, name="print")

    try:
        def __init__(self):
            super().__init__()
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr

        def start(self):
            sys.stdout = self
            sys.stderr = self

        def stop(self):
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr

        def write(self, message):
            self.printOccur.emit(message)

        def flush(self):
            pass
    except Exception as e:
        print(f"StdoutRedirect initialization error: {e}")