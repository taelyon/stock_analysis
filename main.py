import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui_manager import UIManager

if __name__ == "__main__":
    # QWebEngineView를 사용하기 위해 애플리케이션 생성 전에
    # OpenGL 컨텍스트 공유 속성을 설정합니다.
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        app = QApplication(sys.argv)
        mainWindow = UIManager()
        mainWindow.showMaximized()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Application initialization error: {e}")