import os
import sys
from PySide6.QtCore import QObject, Signal

def resource_path(relative_path):
    """
    실행 환경(개발/배포)에 맞는 리소스 파일의 절대 경로를 반환합니다.
    PyInstaller로 패키징된 경우 임시 폴더(_MEIPASS)를 기준으로 경로를 설정합니다.
    """
    try:
        # PyInstaller는 임시 폴더를 생성하고 _MEIPASS에 경로를 저장합니다.
        base_path = sys._MEIPASS
    except AttributeError:
        # PyInstaller로 실행되지 않은 경우(개발 환경) 현재 파일의 경로를 사용합니다.
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


class StdoutRedirect(QObject):
    """
    표준 출력(stdout)과 표준 에러(stderr)를 Qt 시그널로 리디렉션하는 클래스입니다.
    GUI의 텍스트 위젯 등에 콘솔 출력을 표시할 때 사용됩니다.
    """
    # 'str' 타입을 인자로 받는 'printOccur'라는 이름의 시그널을 정의합니다.
    printOccur = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 기존의 표준 출력/에러 스트림을 저장해 둡니다.
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr

    def start(self):
        """리디렉션을 시작합니다."""
        sys.stdout = self
        sys.stderr = self

    def stop(self):
        """리디렉션을 중지하고 원래의 표준 출력/에러로 복원합니다."""
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr

    def write(self, text):
        """
        print() 함수 등이 호출될 때 실행되는 메서드입니다.
        메시지를 시그널로 보냅니다.
        """
        self.printOccur.emit(text)

    def flush(self):
        """
        스트림의 flush 메서드를 구현합니다. 여기서는 특별한 동작이 필요 없습니다.
        """
        pass