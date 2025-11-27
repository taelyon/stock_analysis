import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from ui_manager import MainWindow

def signal_handler(sig, frame):
    print("\n프로그램이 사용자에 의해 중단되었습니다.")
    if QApplication.instance():
        QApplication.instance().quit()
    else:
        sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # QWebEngineView를 사용하기 위해 애플리케이션 생성 전에
    # OpenGL 컨텍스트 공유 속성을 설정합니다.
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        app = QApplication(sys.argv)
        
        # Python 인터프리터가 시그널을 처리할 수 있도록 타이머 설정
        timer = QTimer()
        timer.start(100)
        timer.timeout.connect(lambda: None)
        
        mainWindow = MainWindow()
        mainWindow.showMaximized()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Application initialization error: {e}")