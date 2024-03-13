from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import QPrinter
import sys


class MainWindow(QMainWindow):
    # All your GUI setup and event handlers here
    def __init__(self):
        super().__init__()
        self.setupUi(self)

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1900, 990)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.frame_control = QtWidgets.QFrame(self.centralwidget)
        self.frame_control.setGeometry(QtCore.QRect(0, 0, 200, 991))
        self.frame_control.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.frame_control.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_control.setObjectName("frame_control")

        # 종목 업데이트
        self.groupBox_update = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_update.setGeometry(QtCore.QRect(10, 10, 181, 111))
        self.groupBox_update.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_update.setObjectName("groupBox_update")

        self.verticalLayoutWidget = QtWidgets.QWidget(self.groupBox_update)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 14, 161, 91))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")

        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")

        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setSpacing(1)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")

        self.btn_update1 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update1.setObjectName("btn_update1")
        self.horizontalLayout_5.addWidget(self.btn_update1)

        self.btn_update2 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update2.setObjectName("btn_update2")
        self.horizontalLayout_5.addWidget(self.btn_update2)

        self.btn_update3 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update3.setObjectName("btn_update3")
        self.horizontalLayout_5.addWidget(self.btn_update3)

        self.btn_stop1 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_stop1.setObjectName("btn_stop1")
        self.horizontalLayout_5.addWidget(self.btn_stop1)

        self.verticalLayout.addLayout(self.horizontalLayout_5)
        self.ent_stock = QtWidgets.QLineEdit(self.verticalLayoutWidget)
        self.ent_stock.setObjectName("ent_stock")
        self.verticalLayout.addWidget(self.ent_stock)

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setSpacing(20)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        self.btn_period1 = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.btn_period1.setObjectName("btn_period1")
        self.btn_period1.setChecked(True)

        self.horizontalLayout_2.addWidget(self.btn_period1)
        self.btn_period2 = QtWidgets.QRadioButton(self.verticalLayoutWidget)
        self.btn_period2.setObjectName("btn_period2")
        self.horizontalLayout_2.addWidget(self.btn_period2)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.btn_update4 = QtWidgets.QPushButton(self.verticalLayoutWidget)
        self.btn_update4.setObjectName("btn_update4")
        self.verticalLayout.addWidget(self.btn_update4)

        # 보유 종목
        self.groupBox_hold = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_hold.setGeometry(QtCore.QRect(10, 440, 181, 221))
        self.groupBox_hold.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_hold.setObjectName("groupBox_hold")

        self.verticalLayoutWidget_3 = QtWidgets.QWidget(self.groupBox_hold)
        self.verticalLayoutWidget_3.setGeometry(QtCore.QRect(10, 14, 161, 201))
        self.verticalLayoutWidget_3.setObjectName("verticalLayoutWidget_3")

        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_3)
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")

        self.lb_hold = QtWidgets.QListWidget(self.verticalLayoutWidget_3)
        self.lb_hold.setObjectName("lb_hold")
        self.verticalLayout_5.addWidget(self.lb_hold)

        self.horizontalLayout_10 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_10.setSpacing(0)
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")

        self.btn2 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        # self.btn2.setIconSize(QtCore.QSize(16, 16))
        self.btn2.setObjectName("btn2")
        self.horizontalLayout_10.addWidget(self.btn2)

        self.btn_del1 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.btn_del1.setObjectName("btn_del1")
        self.horizontalLayout_10.addWidget(self.btn_del1)

        self.btn_addint1 = QtWidgets.QPushButton(self.verticalLayoutWidget_3)
        self.btn_addint1.setObjectName("btn_addint1")
        self.horizontalLayout_10.addWidget(self.btn_addint1)

        self.verticalLayout_5.addLayout(self.horizontalLayout_10)

        # 관심 종목
        self.groupBox_int = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_int.setGeometry(QtCore.QRect(10, 670, 181, 221))
        self.groupBox_int.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_int.setObjectName("groupBox_int")

        self.verticalLayoutWidget_4 = QtWidgets.QWidget(self.groupBox_int)
        self.verticalLayoutWidget_4.setGeometry(QtCore.QRect(10, 14, 161, 201))
        self.verticalLayoutWidget_4.setObjectName("verticalLayoutWidget_4")

        self.verticalLayout_6 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_4)
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_6.setObjectName("verticalLayout_6")

        self.lb_int = QtWidgets.QListWidget(self.verticalLayoutWidget_4)
        self.lb_int.setObjectName("lb_int")
        self.verticalLayout_6.addWidget(self.lb_int)

        self.horizontalLayout_11 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_11.setSpacing(0)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")

        self.btn3 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn3.setIconSize(QtCore.QSize(16, 16))
        self.btn3.setObjectName("btn3")
        self.horizontalLayout_11.addWidget(self.btn3)

        self.btn_del2 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn_del2.setObjectName("btn_del2")
        self.horizontalLayout_11.addWidget(self.btn_del2)

        self.btn_addhold1 = QtWidgets.QPushButton(self.verticalLayoutWidget_4)
        self.btn_addhold1.setObjectName("btn_addhold1")
        self.horizontalLayout_11.addWidget(self.btn_addhold1)

        self.verticalLayout_6.addLayout(self.horizontalLayout_11)

        # 종목 조회
        self.groupBox_find = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_find.setGeometry(QtCore.QRect(10, 900, 181, 71))
        self.groupBox_find.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_find.setObjectName("groupBox_find")

        self.verticalLayoutWidget_5 = QtWidgets.QWidget(self.groupBox_find)
        self.verticalLayoutWidget_5.setGeometry(QtCore.QRect(10, 14, 161, 51))
        self.verticalLayoutWidget_5.setObjectName("verticalLayoutWidget_5")

        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_5)
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_7.setSpacing(0)
        self.verticalLayout_7.setObjectName("verticalLayout_7")

        self.ent = QtWidgets.QLineEdit(self.verticalLayoutWidget_5)
        self.ent.setObjectName("ent")
        self.verticalLayout_7.addWidget(self.ent)

        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")

        self.btn_find = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_find.setIconSize(QtCore.QSize(16, 16))
        self.btn_find.setObjectName("btn_find")
        self.horizontalLayout_4.addWidget(self.btn_find)

        self.btn_addhold2 = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_addhold2.setObjectName("btn_addhold2")
        self.horizontalLayout_4.addWidget(self.btn_addhold2)

        self.btn_addint2 = QtWidgets.QPushButton(self.verticalLayoutWidget_5)
        self.btn_addint2.setObjectName("btn_addint2")
        self.horizontalLayout_4.addWidget(self.btn_addint2)

        self.verticalLayout_7.addLayout(self.horizontalLayout_4)

        # 종목 탐색
        self.groupBox_search = QtWidgets.QGroupBox(self.frame_control)
        self.groupBox_search.setGeometry(QtCore.QRect(10, 130, 181, 301))
        self.groupBox_search.setAlignment(QtCore.Qt.AlignCenter)
        self.groupBox_search.setObjectName("groupBox_search")

        self.verticalLayoutWidget_2 = QtWidgets.QWidget(self.groupBox_search)
        self.verticalLayoutWidget_2.setGeometry(QtCore.QRect(10, 14, 161, 281))
        self.verticalLayoutWidget_2.setObjectName("verticalLayoutWidget_2")

        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")

        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")

        self.btn_search1 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search1.setObjectName("btn_search1")
        self.horizontalLayout_3.addWidget(self.btn_search1)

        self.btn_search2 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search2.setObjectName("btn_search2")
        self.horizontalLayout_3.addWidget(self.btn_search2)

        self.btn_search3 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_search3.setObjectName("btn_search3")
        self.horizontalLayout_3.addWidget(self.btn_search3)

        self.btn_stop2 = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_stop2.setObjectName("btn_stop2")
        self.horizontalLayout_3.addWidget(self.btn_stop2)

        self.verticalLayout_4.addLayout(self.horizontalLayout_3)
        self.lb_search = QtWidgets.QListWidget(self.verticalLayoutWidget_2)
        self.lb_search.setObjectName("lb_search")
        self.verticalLayout_4.addWidget(self.lb_search)

        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")

        self.btn = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        # self.btn.setIconSize(QtCore.QSize(16, 16))
        self.btn.setObjectName("btn")
        self.horizontalLayout_6.addWidget(self.btn)

        self.btn_addhold = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_addhold.setObjectName("btn_addhold")
        self.horizontalLayout_6.addWidget(self.btn_addhold)

        self.btn_addint = QtWidgets.QPushButton(self.verticalLayoutWidget_2)
        self.btn_addint.setObjectName("btn_addint")
        self.horizontalLayout_6.addWidget(self.btn_addint)

        self.verticalLayout_4.addLayout(self.horizontalLayout_6)

        # 그래프
        self.frame_plot = QtWidgets.QFrame(self.centralwidget)
        self.frame_plot.setGeometry(QtCore.QRect(200, 0, 1000, 900))
        self.frame_plot.setFrameShadow(QtWidgets.QFrame.Raised)

        self.frame_plot.setObjectName("frame_plot")
        self.verticalLayoutWidget_6 = QtWidgets.QWidget(self.frame_plot)
        self.verticalLayoutWidget_6.setGeometry(QtCore.QRect(0, 0, 991, 891))
        self.verticalLayoutWidget_6.setObjectName("verticalLayoutWidget_6")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_6)
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        # 정보 화면
        self.frame_info = QtWidgets.QFrame(self.centralwidget)
        self.frame_info.setGeometry(QtCore.QRect(1200, 0, 701, 901))
        self.frame_info.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_info.setObjectName("frame_info")

        self.webEngineView = QtWebEngineWidgets.QWebEngineView(self.frame_info)
        self.webEngineView.setGeometry(QtCore.QRect(0, 0, 701, 891))
        self.webEngineView.setUrl(QtCore.QUrl("https://m.stock.naver.com/index.html#/"))
        self.webEngineView.setObjectName("webEngineView")

        # 로그
        self.frame_log = QtWidgets.QFrame(self.centralwidget)
        self.frame_log.setGeometry(QtCore.QRect(200, 900, 1701, 91))
        self.frame_log.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_log.setObjectName("frame_log")

        self.log_widget = QtWidgets.QTextBrowser(self.frame_log)
        self.log_widget.setGeometry(QtCore.QRect(0, 0, 1701, 90))
        self.log_widget.setObjectName("log_widget")

        MainWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        # 프린트
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+P"), self)
        shortcut.activated.connect(self.print)

        # 로그 화면
    def _append_text(self, msg):
        self.log_widget.moveCursor(QtGui.QTextCursor.End)
        self.log_widget.insertPlainText(msg)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    def print(self):
        printer = QPrinter()
        printer.setPageOrientation(QtGui.QPageLayout.Landscape)
        painter = QtGui.QPainter()
        painter.begin(printer)
        screen = self.grab()
        painter.drawPixmap(10, 10, screen)
        painter.end()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "증권 데이터 분석 v2.0"))
        self.groupBox_update.setTitle(_translate("MainWindow", "종목 업데이트"))
        self.btn_update1.setText(_translate("MainWindow", "한국"))
        self.btn_update2.setText(_translate("MainWindow", "미국"))
        self.btn_update3.setText(_translate("MainWindow", "전체"))
        self.btn_stop1.setText(_translate("MainWindow", "중단"))
        self.btn_period1.setText(_translate("MainWindow", "최근"))
        self.btn_period2.setText(_translate("MainWindow", "장기"))
        self.btn_update4.setText(_translate("MainWindow", "업데이트"))
        self.groupBox_hold.setTitle(_translate("MainWindow", "보유 종목"))
        self.btn2.setText(_translate("MainWindow", "선택"))
        self.btn_del1.setText(_translate("MainWindow", "삭제"))
        self.btn_addint1.setText(_translate("MainWindow", "관심"))

        self.groupBox_int.setTitle(_translate("MainWindow", "관심 종목"))
        self.btn3.setText(_translate("MainWindow", "선택"))
        self.btn_del2.setText(_translate("MainWindow", "삭제"))
        self.btn_addhold1.setText(_translate("MainWindow", "보유"))

        self.groupBox_find.setTitle(_translate("MainWindow", "종목 조회"))
        self.btn_find.setText(_translate("MainWindow", "선택"))
        self.btn_addhold2.setText(_translate("MainWindow", "보유"))
        self.btn_addint2.setText(_translate("MainWindow", "관심"))
        self.groupBox_search.setTitle(_translate("MainWindow", "종목 탐색"))
        self.btn_search1.setText(_translate("MainWindow", "한국"))
        self.btn_search2.setText(_translate("MainWindow", "미국"))
        self.btn_search3.setText(_translate("MainWindow", "전체"))
        self.btn_stop2.setText(_translate("MainWindow", "중단"))
        self.btn.setText(_translate("MainWindow", "선택"))
        self.btn_addhold.setText(_translate("MainWindow", "보유"))
        self.btn_addint.setText(_translate("MainWindow", "관심"))


class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, str, name="print")

    def __init__(self):
        super().__init__()
        # sys.stdout 및 sys.stderr의 원래 상태를 저장합니다.
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def stop(self):
        # stdout과 stderr를 원래의 객체로 복원합니다.
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def start(self):
        # stdout과 stderr를 이 객체의 메서드로 대체합니다.
        sys.stdout = self
        sys.stderr = self

    def write(self, message):
        # 색상을 구분하지 않고 모든 메시지를 기본 색상으로 처리합니다.
        # 필요에 따라 여기서 메시지의 종류(표준 출력 또는 에러)에 따라 색상을 지정할 수 있습니다.
        self.printOccur.emit(message, "black")

    def flush(self):
        # flush 메서드가 호출될 때 특별히 수행할 작업이 없는 경우, 이를 빈 메서드로 두어 호환성을 유지합니다.
        pass