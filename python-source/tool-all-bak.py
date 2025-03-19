import subprocess
import sys
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, \
    QPushButton, QTreeWidget, QTreeWidgetItem, QScrollArea, QLabel, QSplitter, QLineEdit, QInputDialog, QDialog, \
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QShortcut, QCheckBox, QToolButton, QTextEdit, QComboBox, \
    QColorDialog
from PyQt5.QtCore import QMetaObject, Q_ARG, pyqtSlot, Qt, QTimer, QPoint, QThread, pyqtSignal, QRect, QSettings, \
    QObject, QSize, QLocale
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPixmap, QKeySequence, QIcon, QGuiApplication, \
    QFontMetrics, QTextBlockFormat, QCursor
import json
import os
from selenium.webdriver import Firefox, Chrome
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.service import Service as ChromeService
import threading
import time
from selenium.common.exceptions import WebDriverException
from pynput import keyboard as pynput_keyboard
import tempfile
from mss import mss, tools
import datetime
import shutil
import zipfile
import copy
import logging
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, message="sipPyTypeDict() is deprecated")

print("Current LD_LIBRARY_PATH:", os.environ.get("LD_LIBRARY_PATH"))

# 设置日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

# 获取用户主目录
user_home = os.path.expanduser('~')

# 创建日志目录
log_dir = os.path.join(user_home, '.auto-test-recorder', 'logs')
os.makedirs(log_dir, exist_ok=True)

# 设置日志文件路径
log_file = os.path.join(log_dir, 'app.log')

# 配置日志处理器
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2)
file_handler.setFormatter(logging.Formatter(log_format, date_format))

# 配置日志记录器
logger = logging.getLogger('AutoTestRecorder')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# 替换现有的print语句
logger.info(f"Python version: {sys.version}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Current PATH: {os.environ.get('PATH', '')}")
logger.info(f"Current working directory: {os.getcwd()}")

try:
    from pynput import keyboard
except ImportError as e:
    logger.error(f"Failed to import pynput: {e}")
    logger.critical("Error: Failed to import pynput. Please check the log file for details.")
    sys.exit(1)


def check_mitmproxy():
    # 首先检查打包的 mitmdump
    packaged_mitmdump = "/usr/share/auto-test-recorder/mitmdump"
    if os.path.exists(packaged_mitmdump):
        mitmdump_path = packaged_mitmdump
    else:
        # 如果打包的 mitmdump 不存在，则尝试在 PATH 中查找
        mitmdump_path = shutil.which('mitmdump')

    if not mitmdump_path:
        logger.error("错误：未找到 mitmdump。请确保程序正确安装。")
        return False

    try:
        result = subprocess.run([mitmdump_path, "--version"], check=True, capture_output=True, text=True)
        logger.info(f"找到 mitmdump: {mitmdump_path}")
        logger.info(f"mitmdump 版本: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"错误：mitmdump 运行失败。错误信息：{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"错误：运行 mitmdump 时发生异常：{str(e)}")
        return False


# 在主程序开始时调用此函数
if not check_mitmproxy():
    logger.critical("mitmproxy 检查失败，程序将退出。")
    sys.exit(1)


def get_app_path():
    if getattr(sys, 'frozen', False):
        # 如果是打包后的应用程序
        return os.path.dirname(sys.executable)
    else:
        # 如果是在开发环境中运行
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    if os.path.exists('/usr/share/auto-test-recorder/'):
        # 如果程序已安装
        base_path = '/usr/share/auto-test-recorder/'
    else:
        # 如果在本地运行
        base_path = get_app_path()
    return os.path.join(base_path, relative_path)


def get_user_data_path(relative_path):
    user_data_dir = os.path.join(os.path.expanduser('~'), '.auto-test-recorder')
    os.makedirs(user_data_dir, exist_ok=True)
    return os.path.join(user_data_dir, relative_path)


def load_file(file_path):
    abs_path = get_resource_path(file_path)
    if os.path.isfile(abs_path):
        return abs_path
    raise FileNotFoundError(f"File not found: {file_path}")


class CustomInputDialog(QDialog):
    def __init__(self, parent=None, title="Bug 描述", label="输入你的Bug描述:"):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)

        self.label = QLabel(label)
        layout.addWidget(self.label)

        self.text_edit = QTextEdit(self)
        layout.addWidget(self.text_edit)

        self.ok_button = QPushButton("确定", self)
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def get_input(self):
        return self.text_edit.toPlainText()


# noinspection PyUnresolvedReferences
class HotkeyListener(QThread):
    hotkey_pressed = pyqtSignal()
    prev_case_signal = pyqtSignal()
    next_case_signal = pyqtSignal()
    prev_function_signal = pyqtSignal()
    next_function_signal = pyqtSignal()
    toggle_tested_signal = pyqtSignal()  # 新增信号

    def __init__(self, settings):
        super().__init__()
        self.prev_case_hotkey = settings.value("prev_case_hotkey", "f1")
        self.next_case_hotkey = settings.value("next_case_hotkey", "f2")
        self.toggle_tested_hotkey = settings.value("toggle_tested_hotkey", "f3")  # 新增快捷键设置
        self.screenshot_hotkey = settings.value("screenshot_hotkey", "f4")
        self.prev_function_hotkey = settings.value("prev_function_hotkey", "f5")
        self.next_function_hotkey = settings.value("next_function_hotkey", "f6")

    def run(self):
        def on_press(key):
            try:
                if key == pynput_keyboard.Key[self.screenshot_hotkey]:
                    self.hotkey_pressed.emit()
                elif key == pynput_keyboard.Key[self.prev_case_hotkey]:
                    self.prev_case_signal.emit()
                elif key == pynput_keyboard.Key[self.next_case_hotkey]:
                    self.next_case_signal.emit()
                elif key == pynput_keyboard.Key[self.toggle_tested_hotkey]:  # 监听新快捷键
                    self.toggle_tested_signal.emit()
                elif key == pynput_keyboard.Key[self.prev_function_hotkey]:
                    self.prev_function_signal.emit()
                elif key == pynput_keyboard.Key[self.next_function_hotkey]:
                    self.next_function_signal.emit()
            except AttributeError:
                pass

        with pynput_keyboard.Listener(on_press=on_press) as listener:
            listener.join()


class TestStatusWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("状态信息")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setGeometry(50, 0, 400, 800)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")

        layout = QVBoxLayout(self)

        self.status_label = QLabel("当前测试状态:")
        self.module_case_label = QLabel("模块: - | 用例: -")
        self.remaining_label = QLabel("剩余: -")

        layout.addWidget(self.status_label)
        layout.addWidget(self.module_case_label)
        layout.addWidget(self.remaining_label)

        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(2)
        self.steps_table.setHorizontalHeaderLabels(["步骤", "预期"])
        self.steps_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.steps_table.setStyleSheet("""
            QTableWidget {
                background-color: #f0f0f0;
                alternate-background-color: #e0e0e0;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #c0c0c0;
                color: #333;
            }
        """)

        layout.addWidget(self.steps_table)

        if parent:
            self.set_position_near_parent()

    def set_position_near_parent(self):
        parent_geom = self.parent().geometry()
        self.setGeometry(parent_geom.right() + 10, parent_geom.y(), 400, parent_geom.height())

    def update_status(self, status, is_tested):
        tested_status = "已测试" if is_tested else "未测试"
        self.status_label.setText(f"当前测试状态: {status} | {tested_status}")

    def update_module_case(self, module, case, total, is_tested):
        tested_status = "<font color='green'>已测试</font>" if is_tested else "<font color='red'>未测试</font>"
        self.module_case_label.setText(f"模块: {module} | 用例: {case}/{total} | 状态: {tested_status}")

    def update_remaining(self, modules, cases):
        self.remaining_label.setText(f"剩余: {modules}个模块, {cases}个用例")

    def update_steps(self, steps):
        self.steps_table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            self.steps_table.setItem(row, 0, QTableWidgetItem(step['describe']))
            self.steps_table.setItem(row, 1, QTableWidgetItem(step['expect']))


from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_created(self, event):
        if not event.is_directory:
            self.callback(event.src_path)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, hotkey='f4', prev_hotkey='f1', next_hotkey='f2',
                 toggle_tested_hotkey='f3', prev_function_hotkey='f5', next_function_hotkey='f6',
                 show_confirmation=True):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.screenshot_hotkey_edit = QLineEdit(hotkey)
        self.prev_case_hotkey_edit = QLineEdit(prev_hotkey)
        self.next_case_hotkey_edit = QLineEdit(next_hotkey)
        self.prev_function_hotkey_edit = QLineEdit(prev_function_hotkey)
        self.next_function_hotkey_edit = QLineEdit(next_function_hotkey)
        self.toggle_tested_hotkey_edit = QLineEdit(toggle_tested_hotkey)
        self.show_toggle_confirmation_checkbox = QCheckBox("显示确认弹窗", checked=show_confirmation)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addLayout(self.hotkey_setting_layout("截图快捷键:", self.screenshot_hotkey_edit))
        layout.addLayout(self.hotkey_setting_layout("上一个用例快捷键:", self.prev_case_hotkey_edit))
        layout.addLayout(self.hotkey_setting_layout("下一个用例快捷键:", self.next_case_hotkey_edit))
        layout.addLayout(self.hotkey_setting_layout("上一个功能快捷键:", self.prev_function_hotkey_edit))
        layout.addLayout(self.hotkey_setting_layout("下一个功能快捷键:", self.next_function_hotkey_edit))
        layout.addLayout(self.hotkey_setting_layout("切换测试状态快捷键:", self.toggle_tested_hotkey_edit))
        layout.addWidget(self.show_toggle_confirmation_checkbox)
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(QPushButton("确定", clicked=self.accept))
        buttons_layout.addWidget(QPushButton("取消", clicked=self.reject))
        layout.addLayout(buttons_layout)

    def hotkey_setting_layout(self, label_text, line_edit):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label_text))
        layout.addWidget(line_edit)
        return layout

    def get_settings(self):
        return {
            'screenshot_hotkey': self.screenshot_hotkey_edit.text(),
            'prev_case_hotkey': self.prev_case_hotkey_edit.text(),
            'next_case_hotkey': self.next_case_hotkey_edit.text(),
            'prev_function_hotkey': self.prev_function_hotkey_edit.text(),
            'next_function_hotkey': self.next_function_hotkey_edit.text(),
            'toggle_tested_hotkey': self.toggle_tested_hotkey_edit.text(),
            'show_toggle_confirmation': self.show_toggle_confirmation_checkbox.isChecked()
        }


# noinspection PyUnresolvedReferences
class App(QMainWindow):
    browserClosed = pyqtSignal()  # 定义信号
    request_update_status = pyqtSignal()  # 添加新的信号

    def __init__(self):
        super().__init__()
        self.setWindowTitle('自动测试记录工具')
        self.init_main_window()

        # 初始化图标
        self.checked_icon = QIcon(get_resource_path("icons/checked.svg"))
        self.unchecked_icon = QIcon(get_resource_path("icons/unchecked.svg"))

        self.monitor_thread = None
        self.monitor_stop_event = threading.Event()
        self.driver = None

        self.data = None
        self.load_data_if_exists()

        # 确保这些属性在任何方法调用之前就被初始化
        self.current_case_id = None
        self.current_module_id = None

        self.create_widgets()

        # 创建状态窗口
        self.status_window = TestStatusWindow(self)
        self.status_window.move(self.x() + self.width() + 20, self.y())  # 将状态窗口放在主窗口右侧
        self.status_window.show()

        # 现在加载和显示数据
        self.load_and_display_data()

        # 初始化浏览器路径为空
        self.chrome_path = ""
        self.firefox_path = ""
        self.firefox_binary_path = ""
        self.chrome_binary_path = ""
        self.default_browser = 'Chrome'
        self.settings = QSettings("MyCompany", "MyApp")
        self.load_settings()

        # 初始化mitmproxy
        self.mitmproxy_process = None
        self.start_mitmproxy()

        # 加载快捷键设置或使用默认值
        self.prev_case_hotkey = self.settings.value("prev_case_hotkey", "f1")
        self.next_case_hotkey = self.settings.value("next_case_hotkey", "f2")
        self.screenshot_hotkey = self.settings.value("screenshot_hotkey", "f4")
        self.prev_function_hotkey = self.settings.value("prev_function_hotkey", "f5")
        self.next_function_hotkey = self.settings.value("next_function_hotkey", "f6")
        self.toggle_tested_hotkey = self.settings.value("toggle_tested_hotkey", "f3")

        # 初始化截图工具
        self.custom_text = ""

        # 设置全局热键监听
        self.setup_global_hotkey_listener()

        # 连接信号
        self.browserClosed.connect(self.load_and_display_data)
        self.hotkey_listener.toggle_tested_signal.connect(self.toggle_tested)
        self.request_update_status.connect(self.delayed_update_status)  # 连接新的信号到槽

        self.settings_dialog = None

        self.init_browser_settings()

        logger.info("App initialization completed")  # 添加这行来确认初始化完成

        self.screenshot_temp_dir = tempfile.mkdtemp()
        self.screenshot_observer = Observer()
        self.screenshot_handler = ScreenshotHandler(self.on_screenshot_taken)
        self.screenshot_observer.schedule(self.screenshot_handler, self.screenshot_temp_dir, recursive=False)
        self.screenshot_observer.start()

    def init_browser_settings(self):
        default_paths = {
            'firefox': '/opt/apps/org.mozilla.firefox-nal/files/firefox-nal/firefox-bin',
            '红莲花': '/opt/apps/com.haitaichina.htbrowser/files/htbrowser.sh',
            '奇安信': '/opt/apps/com.qianxin.browser-stable/files/com.qianxin.browser'
        }

        for browser, default_path in default_paths.items():
            current_path = self.settings.value(f"{browser}_path")
            if not current_path or not os.path.exists(current_path):
                self.settings.setValue(f"{browser}_path", default_path)
                logger.info(f"已重置 {browser} 路径为默认值: {default_path}")

        logger.info("当前浏览器设置:")
        for browser in default_paths.keys():
            logger.info(f"{browser} 路径: {self.settings.value(f'{browser}_path')}")
            logger.info(f"{browser} 驱动路径: {self.settings.value(f'{browser}_driver_path', '未设置')}")

    def load_data_if_exists(self):
        import_json_path = get_user_data_path("import.json")
        if os.path.exists(import_json_path):
            self.data = load_data(import_json_path)
        else:
            logger.info("No existing configuration found. Please import a configuration file.")

    def start_mitmproxy(self):
        log_file = open(get_user_data_path("mitmproxy.log"), "a")
        self.mitmproxy_process = subprocess.Popen(
            ["mitmdump", "--listen-port", "8080", "-s", get_resource_path("mitmproxy_script.py")],
            stdout=log_file, stderr=log_file)

    def stop_mitmproxy(self):
        if self.mitmproxy_process:
            try:
                self.mitmproxy_process.terminate()
                self.mitmproxy_process.wait(timeout=5)  # 等待进程终止，最多等待5秒
            except subprocess.TimeoutExpired:
                self.mitmproxy_process.kill()  # 如果无法正常终止，强制结束进程
            except Exception as e:
                logger.error(f"Error stopping mitmproxy: {e}")
            finally:
                # 安全地关闭日志文件（如果存在）
                if hasattr(self.mitmproxy_process, 'stdout') and self.mitmproxy_process.stdout:
                    self.mitmproxy_process.stdout.close()
                self.mitmproxy_process = None

    def delayed_update_status(self):
        QTimer.singleShot(100, self.update_status_after_close)  # 在主线程中延迟执行

    def toggle_tested(self):
        current_case = self.get_current_case()
        if current_case:
            current_status = current_case.get('isTested', False)

            if self.settings.value("show_toggle_confirmation", True, type=bool):
                reply = QMessageBox.question(self, "切换测试状态",
                                             f"确认将当前用例标记为{'未测试' if current_status else '已测试'}吗?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return

            current_case['isTested'] = not current_status
            current_case['completion'] = 1 if not current_status else 0
            self.save_data()
            self.save_current_test_case()

            # 更新树状图中的图标
            self.update_tree_item_icon(self.current_module_id, self.current_case_id, not current_status)

            self.update_status_windows()
        self.load_and_display_data()

        # 切换回浏览器窗口
        if hasattr(self, 'driver') and self.driver:
            self.focus_browser_window()

    def update_tree_item_icon(self, module_id, case_id, is_tested):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            module_item = root.child(i)
            if module_item.text(0) == module_id:
                for j in range(module_item.childCount()):
                    case_item = module_item.child(j)
                    if case_item.text(0) == case_id:
                        icon = self.checked_icon if is_tested else self.unchecked_icon
                        case_item.setIcon(1, icon)
                        return

    def focus_browser_window(self):
        try:
            subprocess.run(["wmctrl", "-a", self.browser_window_title])
        except Exception as e:
            logger.error(f"Error focusing browser window: {e}")

    def get_current_case(self):
        # 从数据中查找当前激活的用例
        if self.current_module_id and self.current_case_id:
            for module in self.data:
                if str(module["id"]) == self.current_module_id:
                    for case in module.get("caseVoList", []):
                        if str(case["id"]) == self.current_case_id:
                            return case
        return None

    def save_data(self):
        # 保存数据到文件
        for module in self.data:
            for case in module.get("caseVoList", []):
                case["completion"] = 1 if case.get("isTested", False) else 0

        with open(get_user_data_path("import.json"), "w") as file:
            json.dump(self.data, file, indent=4)

    def init_main_window(self):
        screen = QApplication.primaryScreen()
        rect = screen.availableGeometry()
        width, height = int(rect.width() * 0.6), int(rect.height() * 0.85)  # 使用屏幕的60%宽度和60%高度
        x, y = int(rect.width() * 0.1), int((rect.height() - height) / 2)  # 水平方向从左侧25%开始，竖直方向居中
        self.setGeometry(x, y, width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'status_window'):
            self.status_window.set_position_near_parent()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, 'status_window'):
            self.status_window.set_position_near_parent()

    def show_settings_dialog(self):
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(
                self,
                self.screenshot_hotkey,
                self.prev_case_hotkey,
                self.next_case_hotkey,
                self.toggle_tested_hotkey,
                self.prev_function_hotkey,  # 添加上一个功能快捷键
                self.next_function_hotkey,  # 添加下一个功能快捷键
                self.settings.value("show_toggle_confirmation", True, type=bool)
            )
        if self.settings_dialog.exec_():
            settings = self.settings_dialog.get_settings()
            self.screenshot_hotkey = settings['screenshot_hotkey']
            self.prev_case_hotkey = settings['prev_case_hotkey']
            self.next_case_hotkey = settings['next_case_hotkey']
            self.toggle_tested_hotkey = settings['toggle_tested_hotkey']
            self.prev_function_hotkey = settings['prev_function_hotkey']  # 获取上一个功能快捷键设置
            self.next_function_hotkey = settings['next_function_hotkey']  # 获取下一个功能快捷键设置
            self.settings.setValue("screenshot_hotkey", self.screenshot_hotkey)
            self.settings.setValue("prev_case_hotkey", self.prev_case_hotkey)
            self.settings.setValue("next_case_hotkey", self.next_case_hotkey)
            self.settings.setValue("toggle_tested_hotkey", self.toggle_tested_hotkey)
            self.settings.setValue("prev_function_hotkey", self.prev_function_hotkey)  # 保存上一个功能快捷键设置
            self.settings.setValue("next_function_hotkey", self.next_function_hotkey)  # 保存下一个功能快捷键设置
            self.settings.setValue("show_toggle_confirmation", settings['show_toggle_confirmation'])
            self.setup_global_hotkey_listener()

    def prev_case(self):
        if self.current_module_id and self.current_case_id:
            for module in self.data:
                if str(module["id"]) == self.current_module_id:
                    cases = module.get("caseVoList", [])
                    index = next((i for i, case in enumerate(cases) if str(case["id"]) == self.current_case_id), -1)
                    if index > 0:
                        self.current_case_id = str(cases[index - 1]["id"])
                        self.save_current_test_case()
                        self.update_status_windows()

        self.update_status_windows()

    def next_case(self):
        if self.current_module_id and self.current_case_id:
            for module in self.data:
                if str(module["id"]) == self.current_module_id:
                    cases = module.get("caseVoList", [])
                    index = next((i for i, case in enumerate(cases) if str(case["id"]) == self.current_case_id), -1)
                    if index < len(cases) - 1:
                        self.current_case_id = str(cases[index + 1]["id"])
                        self.save_current_test_case()
                        self.update_status_windows()

        self.update_status_windows()

    def prev_function(self):
        current_module_index = next((index for index, module in enumerate(self.data)
                                     if str(module["id"]) == self.current_module_id), -1)
        if current_module_index > 0:
            prev_module = self.data[current_module_index - 1]
            self.current_module_id = str(prev_module["id"])
            if prev_module.get("caseVoList"):
                self.current_case_id = str(prev_module["caseVoList"][0]["id"])
            else:
                self.current_case_id = None
            self.save_current_test_case()
            self.update_status_windows()

    def next_function(self):
        current_module_index = next((index for index, module in enumerate(self.data)
                                     if str(module["id"]) == self.current_module_id), -1)
        if current_module_index < len(self.data) - 1:
            next_module = self.data[current_module_index + 1]
            self.current_module_id = str(next_module["id"])
            if next_module.get("caseVoList"):
                self.current_case_id = str(next_module["caseVoList"][0]["id"])
            else:
                self.current_case_id = None
            self.save_current_test_case()
            self.update_status_windows()

    def closeEvent(self, event):
        self.stop_mitmproxy()
        self.status_window.close()
        self.screenshot_observer.stop()
        self.screenshot_observer.join()
        shutil.rmtree(self.screenshot_temp_dir, ignore_errors=True)
        super().closeEvent(event)

    def save_bug_info(self, filename, description):
        try:
            bug_info = {"imageName": os.path.basename(filename), "remark": description}
            self.append_screenshot_result(bug_info)
            logger.info(f"Bug信息已保存: {bug_info}")
        except Exception as e:
            logger.error(f"Error saving bug info: {e}")

    def delete_screenshot(self, filename):
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"Deleted screenshot: {filename}")
            except Exception as e:
                logger.error(f"Error deleting screenshot: {e}")

    def load_settings(self):
        self.chrome_path = self.settings.value("chrome_path", "")
        self.firefox_path = self.settings.value("firefox_path", "")
        self.firefox_binary_path = self.settings.value("firefox_binary_path", "")
        self.chrome_binary_path = self.settings.value("chrome_binary_path", "")
        self.default_browser = self.settings.value("default_browser", "Chrome")
        self.screenshot_hotkey = self.settings.value("screenshot_hotkey", "f4")
        self.prev_case_hotkey = self.settings.value("prev_case_hotkey", "f1")
        self.next_case_hotkey = self.settings.value("next_case_hotkey", "f2")
        self.toggle_tested_hotkey = self.settings.value("toggle_tested_hotkey", "f3")  # 加载新快捷键设置
        self.show_toggle_confirmation = self.settings.value("show_toggle_confirmation", True, type=bool)

    # 更新 setup_global_hotkey_listener 方法
    def setup_global_hotkey_listener(self):
        self.hotkey_listener = HotkeyListener(
            self.settings  # 传递 QSettings 对象
        )
        self.hotkey_listener.hotkey_pressed.connect(self.trigger_global_screenshot)
        self.hotkey_listener.prev_case_signal.connect(self.prev_case)
        self.hotkey_listener.next_case_signal.connect(self.next_case)
        self.hotkey_listener.prev_function_signal.connect(self.prev_function)
        self.hotkey_listener.next_function_signal.connect(self.next_function)
        self.hotkey_listener.start()

    def update_hotkeys(self, new_screenshot_hotkey, new_prev_case_hotkey, new_next_case_hotkey,
                       new_toggle_tested_hotkey):
        self.settings.setValue("screenshot_hotkey", new_screenshot_hotkey)
        self.settings.setValue("prev_case_hotkey", new_prev_case_hotkey)
        self.settings.setValue("next_case_hotkey", new_next_case_hotkey)
        self.settings.setValue("toggle_tested_hotkey", new_toggle_tested_hotkey)  # 保存新快捷键设置

        self.setup_global_hotkey_listener()

    def trigger_global_screenshot(self):
        timestamp = int(time.time())
        screenshot_path = os.path.join(self.screenshot_temp_dir, f"screenshot_{timestamp}.png")
        subprocess.Popen(["/usr/bin/deepin-screen-recorder", "-n", "-s", screenshot_path])

    def on_screenshot_taken(self, screenshot_path):
        # This method will be called when a new screenshot is detected
        QMetaObject.invokeMethod(self, "show_bug_description_dialog", Qt.QueuedConnection, Q_ARG(str, screenshot_path))

    @pyqtSlot(str)
    def show_bug_description_dialog(self, screenshot_path):
        dialog = CustomInputDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            bug_desc = dialog.get_input()
            if bug_desc:
                self.process_screenshot(screenshot_path, bug_desc)
            else:
                os.remove(screenshot_path)
        else:
            os.remove(screenshot_path)

        # 切换回浏览器窗口
        self.focus_browser_window()

    def process_screenshot(self, screenshot_path, bug_desc):
        # Move the screenshot to the correct location
        dest_dir = get_user_data_path('screenshots')
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(screenshot_path))
        shutil.move(screenshot_path, dest_path)

        # Update the bug info
        bug_info = {"imageName": os.path.basename(dest_path), "remark": bug_desc}
        self.append_screenshot_result(bug_info)

        self.update_status_windows()
        self.load_and_display_data()

    def save_current_test_case(self):
        current_test_case = {
            "module_id": self.current_module_id,
            "case_id": self.current_case_id
        }
        with open(get_user_data_path("current_test_case.json"), "w") as file:
            json.dump(current_test_case, file)

    def start_test(self):
        logger.info("开始测试方法被调用")

        # 获取可用的浏览器列表
        available_browsers = ['firefox', '红莲花', '奇安信']
        browser_paths = {
            'firefox': '/opt/apps/org.mozilla.firefox-nal/files/firefox-nal/firefox-bin.sh',
            '红莲花': '/opt/apps/com.haitaichina.htbrowser/files/htbrowser.sh',
            '奇安信': '/opt/apps/com.qianxin.browser-stable/files/com.qianxin.browser'
        }

        # 过滤出已安装的浏览器
        installed_browsers = [browser for browser in available_browsers if os.path.exists(browser_paths[browser])]

        if not installed_browsers:
            logger.warning("没有检测到可用的浏览器，请确保至��安装了一个受支持的浏览器。")
            QMessageBox.warning(self, "警告", "没有检测到可用的浏览器，请确保至少安装了一个受支持的浏览器。")
            return

        # 让用户选择浏览器
        browser_choice, ok = QInputDialog.getItem(self, "选择浏览器", "请选择要使用的浏览器:", installed_browsers, 0,
                                                  False)

        if not ok or not browser_choice:
            return  # 用户取消了选择

        # 检查是否设置了浏览器和驱动路径
        browser_path = self.settings.value(f"{browser_choice}_path", browser_paths[browser_choice])
        driver_path = self.settings.value(f"{browser_choice}_driver_path", "")

        if not os.path.exists(browser_path):
            logger.error(f"未找到{browser_choice}浏览器，请在设置中配置正确的浏览器路径。")
            QMessageBox.warning(self, "警告", f"未找到{browser_choice}浏览器，请在设置中配置正确的浏览器路径。")
            return

        if not driver_path or not os.path.exists(driver_path):
            logger.error(f"请先在设置中配置{browser_choice}的驱动路径。")
            QMessageBox.warning(self, "警告", f"请先在设置中配置{browser_choice}的驱动路径。")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            logger.info("未选择测试用例")
            return

        item = selected_items[0]
        if item.parent() is None:
            logger.info("选择的是模块，而不是用例")
            return

        case_id, module_id = item.text(0), item.parent().text(0)
        logger.info(f"选择的用例 ID: {case_id}, 模块 ID: {module_id}")

        self.current_case_id = case_id
        self.current_module_id = module_id

        logger.info("正在初始化浏览器...")
        self.init_browser(browser_choice)
        logger.info("浏览器初始化完成")

        # 记录浏览器窗口名字
        self.browser_window_title = self.get_browser_window_title(browser_choice)
        logger.info(f"浏览器窗口名字: {self.browser_window_title}")

        self.save_current_test_case()
        logger.info("当前测试用例已保存")

        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_stop_event.clear()
            logger.info("监控线程不存在或未运行，准备启动新线程")
        else:
            logger.info("监控线程正在运行，准备停止")
            self.monitor_stop_event.set()
            self.monitor_thread.join()
            logger.info("监控线程已停止")

        self.monitor_stop_event.clear()
        self.monitor_thread = threading.Thread(target=self.monitor_browser_and_update)
        self.monitor_thread.start()
        logger.info("新的监控线程已启动")

        self.update_status_windows()
        logger.info("状态窗口已更新")

        logger.info("测试启动完成")

    def get_browser_window_title(self, browser_choice):
        if browser_choice == "firefox":
            return "Mozilla Firefox"
        elif browser_choice == "红莲花":
            return "红莲花"
        elif browser_choice == "奇安信":
            return "奇安信"
        else:
            return "Google Chrome"

    def monitor_browser_and_update(self):
        while not self.monitor_stop_event.is_set():
            if hasattr(self, 'driver') and self.driver:
                try:
                    if self.driver.service.process is None:
                        logger.info("浏览器进程已结束")
                        self.close_browser()
                        self.request_update_status.emit()  # 使用信号来请求更新状态
                        self.monitor_stop_event.set()
                        break
                    _ = self.driver.current_window_handle
                except WebDriverException:
                    logger.info("浏览器已关闭,正在更新测试状态...")
                    self.close_browser()
                    self.request_update_status.emit()  # 使用信号来请求更新状态
                    self.monitor_stop_event.set()
                    break

    def close_browser(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()
            self.driver = None

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_stop_event.set()
            if self.monitor_thread != threading.current_thread():
                self.monitor_thread.join()

        self.browserClosed.emit()  # 发射信号

    def update_status_after_close(self):
        try:
            # 暂时断开树形视图的信号连接，防止不必要的触发
            self.tree.itemClicked.disconnect(self.display_case_details)

            # 重新加载数据
            self.data = load_data(get_user_data_path("import.json"))

            # 更新UI
            self.load_and_display_data()

            # 更新状态窗口
            self.update_status_windows()

            # 如果当前有选中的用例，更新其显示
            if self.current_case_id and self.current_module_id:
                for module in self.data:
                    if str(module["id"]) == self.current_module_id:
                        for case in module.get("caseVoList", []):
                            if str(case["id"]) == self.current_case_id:
                                self.display_case_info(case)
                                break
                        break

            # 更新树形视图的选中状态
            self.update_tree_selection()

            logger.info("状态已更新")  # 用于调试
        except Exception as e:
            logger.error(f"更新状态时发生错误: {e}")  # 错误日志
        finally:
            # 重新连接树形视图的信号
            self.tree.itemClicked.connect(self.display_case_details)

    def update_tree_selection(self):
        # 更新树形视图的选中状态
        if self.current_module_id and self.current_case_id:
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                module_item = root.child(i)
                if module_item.text(0) == self.current_module_id:
                    for j in range(module_item.childCount()):
                        case_item = module_item.child(j)
                        if case_item.text(0) == self.current_case_id:
                            self.tree.setCurrentItem(case_item)
                            return

    def update_status_windows(self):
        current_module, current_case, total_cases = self.get_current_module_case()
        remaining_modules, remaining_cases = self.get_remaining_modules_cases()
        current_case_info = self.get_current_case()

        if current_case_info:
            is_tested = current_case_info.get('isTested', False)
            self.status_window.update_status("正在测试" if self.driver else "未测试", is_tested)
            self.status_window.update_module_case(current_module, current_case, total_cases, is_tested)
        else:
            self.status_window.update_status("未测试", False)
            self.status_window.update_module_case("-", "-", "-", False)

        self.status_window.update_remaining(remaining_modules, remaining_cases)
        self.status_window.update_steps(self.get_current_steps())

        logger.info("update_status_windows completed")  # 添加这行来确认方法执行完成

    def get_current_module_case(self):
        if self.current_module_id and self.current_case_id:
            for module in self.data:
                if str(module["id"]) == self.current_module_id:
                    for index, case in enumerate(module.get("caseVoList", []), start=1):
                        if str(case["id"]) == self.current_case_id:
                            return module["name"], index, len(module.get("caseVoList", []))
        return "-", "-", "-"

    def get_remaining_modules_cases(self):
        remaining_modules = 0
        remaining_cases = 0
        for module in self.data:
            module_has_remaining = False
            for case in module.get("caseVoList", []):
                if not case.get("isTested"):
                    remaining_cases += 1
                    module_has_remaining = True
            if module_has_remaining:
                remaining_modules += 1
        return remaining_modules, remaining_cases

    def get_current_steps(self):
        if self.current_case_id:
            for module in self.data:
                for case in module.get('caseVoList', []):
                    if str(case['id']) == self.current_case_id:
                        content_map = case.get('contentMap', [])
                        if content_map is None:
                            content_map = []
                        return content_map
        return []

    def init_error_json_from_export(self, export_file_path, error_file_path):
        with open(export_file_path, "r") as file:
            data = json.load(file)

        for module in data:
            for case in module.get("caseVoList", []):
                case["isTested"] = False

        with open(error_file_path, "w") as file:
            json.dump(data, file, indent=4)

    def init_browser(self, browser_choice):
        x, y, width, height = self.geometry().getRect()
        height += int(height * 0.1)
        y -= int(y * 0.5)

        browser_path = self.settings.value(f"{browser_choice}_path")
        driver_path = self.settings.value(f"{browser_choice}_driver_path")

        logger.info(f"初始化浏览器: {browser_choice}")
        logger.info(f"设置中的浏览器路径: {browser_path}")
        logger.info(f"设置中的驱动路径: {driver_path}")

        if not browser_path or not os.path.exists(browser_path):
            logger.error(f"错误: 浏览器路径不存在或未设置 - {browser_path}")
            QMessageBox.warning(self, "错误", f"{browser_choice} 浏览器路径无效或未设置。")
            return

        if not driver_path or not os.path.exists(driver_path):
            logger.error(f"错误: 驱动路径不存在或未设置 - {driver_path}")
            QMessageBox.warning(self, "错误", f"{browser_choice} 驱动路径无效或未设置。")
            return

        # 在调用Firefox前设置LD_LIBRARY_PATH，以包含额外的库目录
        if browser_choice == "firefox":

            firefox_options = FirefoxOptions()
            firefox_options.binary_location = browser_path
            firefox_options.set_preference('network.proxy.type', 1)
            firefox_options.set_preference('network.proxy.http', 'localhost')
            firefox_options.set_preference('network.proxy.http_port', 8080)
            firefox_options.set_preference('network.proxy.ssl', 'localhost')
            firefox_options.set_preference('network.proxy.ssl_port', 8080)

            # 将 FirefoxOptions 的日志级别设为 trace 以获取更详细信息
            firefox_options.log.level = "trace"

            # 不指定 log_path，让 geckodriver 日志直接输出到终端
            firefox_service = FirefoxService(
                executable_path=driver_path,
                log_path='geckodriver.log',  # 将日志输出到本地文件中
                service_args=["--log", "trace"]  # 设置日志级别为trace，获得更详细的日志信息
            )

            try:
                self.driver = Firefox(service=firefox_service, options=firefox_options)
            except Exception as e:
                # 在终端中打印异常信息
                print(f"启动 Firefox 时发生错误: {str(e)}")
                QMessageBox.warning(self, "错误", f"启动 Firefox 失败: {str(e)}")
                return


        else:
            chrome_options = ChromeOptions()
            chrome_options.binary_location = browser_path
            chrome_options.add_argument('--proxy-server=http://localhost:8080')
            chrome_service = ChromeService(executable_path=driver_path)
            try:
                self.driver = Chrome(service=chrome_service, options=chrome_options)
            except Exception as e:
                logger.error(f"启动 Chrome 时发生错误: {str(e)}")
                QMessageBox.warning(self, "错误", f"启动 Chrome 失败: {str(e)}")
                return

        self.driver.set_window_position(x, y)
        self.driver.set_window_size(width, height)
        logger.info("浏览器初始化完成")

    # 在 BrowserSettingsDialog 类中修改 set_browser_path 方法
    def set_browser_path(self, browser_name):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{browser_name}浏览器路径", "", "所有文件 (*)")
        if path:
            self.parent.settings.setValue(f"{browser_name}_path", path)
            logger.info(f"设置 {browser_name} 路径为: {path}")  # 添加日志
            self.refresh_table()

    def generate_import_json(self, source_file):
        try:
            with open(source_file, 'r', encoding='utf-8') as file:
                data = json.load(file)

            for module in data:
                for case in module.get("caseVoList", []):
                    case["isTested"] = False

            with open(get_user_data_path("import.json"), "w", encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Error generating import.json: {e}")

    def create_widgets(self):
        central_widget = QWidget(self)
        layout = QHBoxLayout(central_widget)

        # 设置左侧树状图样式
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(['ID', '名称'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 根据内容自适应调整第一列的宽度
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)  # 第二列填充剩余空间
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 16px; /* 调整字体大小 */
                color: #333; /* 文字颜色 */
            }
            QTreeWidget::item {
                border-bottom: 1px solid #e0e0e0; /* 每项下方的分界线 */
                padding: 5px; /* 项内边距 */
            }
            QTreeWidget::item:selected {
                background-color: #a0a0a0; /* 选中项背景色 */
            }
            QHeaderView::section {
                background-color: #f3f3f3; /* 头部背景色 */
                padding: 5px; /* 头部内边距 */
                border-style: none; /* 头部边框样式 */
                font-size: 16px; /* 头部字体大小 */
                font-weight: bold; /* 头部字体加粗 */
            }
        """)

        # 设置菜单栏样式
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar {font-size: 14px;} QMenu {font-size: 14px;}")

        left_widget = QWidget(central_widget)
        left_layout = QVBoxLayout(left_widget)

        test_btn = QPushButton("开始测试", left_widget)
        test_btn.clicked.connect(self.start_test)
        left_layout.addWidget(test_btn)

        self.tree = QTreeWidget(left_widget)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(['ID', '名称'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 根据内容自适应调整第一列的宽度
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)  # 第二列填充剩余空间
        left_layout.addWidget(self.tree)

        self.right_widget = QScrollArea(central_widget)
        self.right_widget.setWidgetResizable(True)
        layout.addWidget(self.right_widget)

        splitter = QSplitter(Qt.Horizontal, central_widget)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # 设置左侧和右侧窗口的比例为1:2
        splitter.setSizes([int(self.width() / 3), int(self.width() / 3 * 2)])

        layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        # 添加新的菜单项
        data_menu = menubar.addMenu('文件')

        # 导入数据菜单项
        import_action = data_menu.addAction('导入文件')
        import_action.triggered.connect(self.import_data)

        # 导出数据菜单项
        export_action = data_menu.addAction('导出文件')
        export_action.triggered.connect(self.export_data)

        # 添加重置测试结果的菜单项
        reset_results_action = data_menu.addAction('重置测试结果')
        reset_results_action.triggered.connect(self.reset_test_results)

        # 添加截图设置菜单项
        menubar = self.menuBar()
        self.settings_menu = menubar.addMenu('设置')  # 修改这一行

        browser_settings_action = self.settings_menu.addAction('浏览器与驱动')
        browser_settings_action.triggered.connect(self.show_browser_settings)

        # 添加截图快捷键设置菜单项
        set_hotkey_action = self.settings_menu.addAction('设置全局快捷键')
        set_hotkey_action.triggered.connect(self.show_settings_dialog)

    def show_browser_settings(self):
        dialog = BrowserSettingsDialog(self)
        dialog.exec_()

    def reset_test_results(self):
        error_file_path = get_user_data_path("import.json")

        with open(error_file_path, "r") as file:
            data = json.load(file)

        for module in data:
            for case in module.get("caseVoList", []):
                case["httpResult"] = []  # 将httpResult字段重置为空数组
                case["imageResult"] = None
                case["isTested"] = False  # 将测试状态设置为未测试

        with open(error_file_path, "w") as file:
            json.dump(data, file, indent=4)

        # 删除用户数据目录下所有符合screenshot_时间戳.png格式的图片文件
        screenshots_dir = get_user_data_path('screenshots')
        if os.path.exists(screenshots_dir):
            files = os.listdir(screenshots_dir)
            screenshots = [file for file in files if file.startswith('screenshot_') and file.endswith('.png')]
            for screenshot in screenshots:
                os.remove(os.path.join(screenshots_dir, screenshot))

        self.data = load_data(get_user_data_path("import.json"))
        self.load_and_display_data()

    def import_data(self):
        filename, _ = QFileDialog.getOpenFileName(self, "导入数据文件", "", "JSON files (*.json)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    imported_data = json.load(file)

                # 处理导入的数据，可能需要进行一些验证或转换
                self.data = imported_data

                # 保存导入的数据到用户数据目录
                import_json_path = get_user_data_path("import.json")
                with open(import_json_path, 'w', encoding='utf-8') as file:
                    json.dump(self.data, file, ensure_ascii=False, indent=4)

                logger.info(f"Data imported and saved to {import_json_path}")
                self.load_and_display_data()  # 更新UI显示
            except Exception as e:
                logger.error(f"导入文件时发生错误: {str(e)}")
                QMessageBox.warning(self, "导入错误", f"导入文件时发生错误: {str(e)}")

    def export_data(self):
        # 创建 self.data 的深度拷贝
        export_data = copy.deepcopy(self.data)

        # 预处理数据,确保httpResult字段为null或有效的数组，并修正completion字段
        for module in export_data:
            for case in module.get("caseVoList", []):
                if not case.get("httpResult"):
                    case["httpResult"] = None
                if case.get("completion") is None:
                    case["completion"] = 0

        # 生成默认的文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H_%M_%S")
        default_filename = f"export_{timestamp}.zip"

        # 打开文件选择对话框
        zip_filename, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出位置",
            os.path.join(os.path.expanduser("~"), default_filename),  # 默认保存到用户主目录
            "ZIP 文件 (*.zip)"
        )

        if not zip_filename:  # 用户取消了选择
            return

        try:
            # 创建一个临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 将修改后的数据写入临时的 JSON 文件
                temp_json_path = os.path.join(temp_dir, "import.json")
                with open(temp_json_path, 'w', encoding='utf-8') as temp_file:
                    json.dump(export_data, temp_file, ensure_ascii=False, indent=4)

                # 创建 ZIP 文件
                with zipfile.ZipFile(zip_filename, 'w') as zipf:
                    # 添加临时 JSON 文件到 ZIP
                    zipf.write(temp_json_path, arcname="import.json")

                    # 获取screenshots文件夹下所有文件
                    screenshots_dir = get_user_data_path('screenshots')
                    if os.path.exists(screenshots_dir):
                        files = os.listdir(screenshots_dir)
                        # 筛选出符合条件的图片文件
                        screenshots = [file for file in files if
                                       file.startswith('screenshot_') and file.endswith('.png')]
                        # 如果有符合条件的图片文件
                        if screenshots:
                            # 将图片文件添加到ZIP文件的image文件夹下
                            for screenshot in screenshots:
                                zipf.write(os.path.join(screenshots_dir, screenshot),
                                           arcname=os.path.join('image', screenshot))

            logger.info(f"数据已成功导出到 {zip_filename}")
            QMessageBox.information(self, "导出成功", f"数据已成功导出到 {zip_filename}")
        except Exception as e:
            logger.error(f"导出数据时发生错误: {str(e)}")
            QMessageBox.critical(self, "导出错误", f"导出数据时发生错误: {str(e)}")

    def load_and_display_data(self):
        logger.info("Starting load_and_display_data")  # 添加日志
        self.tree.clear()
        if self.right_widget.widget() is not None:
            self.right_widget.widget().deleteLater()
            self.right_widget.setWidget(None)

        if not hasattr(self, 'checked_icon') or not hasattr(self, 'unchecked_icon'):
            logger.error("Error: Icons not initialized")  # 添加错误检查
            return

        if not hasattr(self, 'status_window'):
            logger.error("Error: Status window not initialized")  # 添加错误检查
            return

        if self.data:  # 只在有数据时执行以下操作
            for module in self.data:
                module_item = QTreeWidgetItem([str(module['id']), module['name']])
                self.tree.addTopLevelItem(module_item)
                for case in module.get('caseVoList', []):
                    case_item = QTreeWidgetItem([str(case['id']), case['caseName']])
                    icon = self.checked_icon if case.get('isTested', False) else self.unchecked_icon
                    case_item.setIcon(1, icon)  # 设置图标在第二列
                    module_item.addChild(case_item)
            self.tree.itemClicked.connect(self.display_case_details)

            # 只在有数据时更新状态窗口
            self.update_status_windows()
        else:
            logger.info("No data available to display.")

        logger.info("load_and_display_data completed")  # 添加这行来确认方法执行完成

    def display_case_details(self, item):
        if item.parent() is None:
            return

        case_id = item.text(0)
        for module in self.data:
            for case in module.get('caseVoList', []):
                if str(case['id']) == case_id:
                    self.current_case_id = case_id
                    self.current_module_id = str(module['id'])
                    self.display_case_info(case)
                    self.update_status_windows()
                    break

    def display_case_info(self, case):
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # 用例名称
        title_label = QLabel(f"用例 - {case['caseName']}")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: #2e6c80;")
        title_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title_label)

        # 测试步骤和Bug描述区域
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # 左侧测试步骤布局
        steps_widget = QWidget()
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setContentsMargins(20, 10, 20, 10)
        steps_layout.setSpacing(10)

        steps_label = QLabel("测试步骤")
        steps_label.setFont(QFont("Arial", 14, QFont.Bold))
        steps_label.setAlignment(Qt.AlignCenter)
        steps_layout.addWidget(steps_label)

        steps_table = QTableWidget()
        steps_table.setColumnCount(2)
        steps_table.setHorizontalHeaderLabels(["步骤", "预期"])
        steps_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        steps_table.verticalHeader().setVisible(False)
        steps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        steps_table.setStyleSheet("""
            QTableWidget {
                background-color: #f0f0f0;
                alternate-background-color: #e0e0e0;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #c0c0c0;
                color: #333;
            }
        """)

        content_map = case.get('contentMap', [])
        if content_map is None:
            content_map = []

        steps_table.setRowCount(len(content_map))

        for row, step in enumerate(content_map):
            steps_table.setItem(row, 0, QTableWidgetItem(step['describe']))
            steps_table.setItem(row, 1, QTableWidgetItem(step['expect']))

        steps_scroll = QScrollArea()
        steps_scroll.setWidgetResizable(True)
        steps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        steps_scroll.setWidget(steps_table)

        steps_layout.addWidget(steps_scroll)
        main_layout.addWidget(steps_widget)

        # 右侧Bug描述布局
        desc_widget = QWidget()
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(20, 10, 20, 10)
        desc_layout.setSpacing(10)

        desc_title_label = QLabel("Bug描述")
        desc_title_label.setFont(QFont("Arial", 14, QFont.Bold))
        desc_title_label.setStyleSheet("""
            background-color: #f0f0f0;
            padding: 5px;
            color: black;
        """)
        desc_title_label.setAlignment(Qt.AlignCenter)
        desc_layout.addWidget(desc_title_label)

        desc_scroll = QScrollArea()
        desc_scroll.setWidgetResizable(True)
        desc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        desc_content_widget = QWidget()
        desc_content_layout = QVBoxLayout(desc_content_widget)
        desc_content_layout.setSpacing(10)

        # Bug描述和截图
        if 'imageResult' in case and case['imageResult']:
            image_results = json.loads(case['imageResult'])

            for index, image_result in enumerate(image_results):
                # Bug描述
                desc_label = QLabel(image_result['remark'])
                desc_label.setFont(QFont("Arial", 14))
                desc_label.setWordWrap(True)
                desc_label.setAlignment(Qt.AlignCenter)
                desc_content_layout.addWidget(desc_label)

                # 截图
                image_path = os.path.join(get_user_data_path('screenshots'), image_result['imageName'])
                if os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    screenshot_label = QLabel()

                    # 设置一个固定的宽度和高度
                    fixed_width = 300  # 例如，设置为300像素宽
                    fixed_height = 300  # 例如，设置为300像素高

                    # 调整截图大小以适应固定尺寸
                    resized_pixmap = pixmap.scaled(fixed_width, fixed_height, Qt.KeepAspectRatio,
                                                   Qt.SmoothTransformation)
                    screenshot_label.setPixmap(resized_pixmap)
                    screenshot_label.setAlignment(Qt.AlignCenter)
                    screenshot_label.mousePressEvent = lambda event, path=image_path: self.show_image(path)
                    desc_content_layout.addWidget(screenshot_label)
                else:
                    logger.error(f"Image file not found: {image_path}")

        desc_content_widget.setLayout(desc_content_layout)
        desc_scroll.setWidget(desc_content_widget)
        desc_layout.addWidget(desc_scroll)
        main_layout.addWidget(desc_widget)

        main_layout.setStretchFactor(steps_widget, 1)
        main_layout.setStretchFactor(desc_widget, 1)
        content_layout.addWidget(main_widget)
        content_widget.setLayout(content_layout)
        self.right_widget.setWidget(content_widget)

    def show_image(self, image_path):
        # 创建一个对话框显示放大的图片
        dialog = QDialog(self)
        dialog.setWindowTitle("截图")

        layout = QVBoxLayout(dialog)

        pixmap = QPixmap(image_path)
        image_label = QLabel(dialog)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(True)  # 自适应大小

        layout.addWidget(image_label)

        dialog.exec_()

    def show_browser_path_dialog(self, browser_name):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{browser_name}Driver", "", "所有文件 (*)")
        if path:
            if browser_name == "Chrome":
                self.chrome_path = path
                self.settings.setValue("chrome_path", path)
            elif browser_name == "Firefox":
                self.firefox_path = path
                self.settings.setValue("firefox_path", path)
            QMessageBox.information(self, f"{browser_name}Driver路径", f"已设置{browser_name}Driver路径为: {path}")

    def show_browser_binary_path_dialog(self, browser_name):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{browser_name}浏览器路径", "", "所有文件 (*)")
        if path:
            if browser_name == "Chrome":
                self.chrome_binary_path = path
                self.settings.setValue("chrome_binary_path", path)
            elif browser_name == "Firefox":
                self.firefox_binary_path = path
                self.settings.setValue("firefox_binary_path", path)
            QMessageBox.information(self, f"{browser_name}浏览器路径", f"已设置{browser_name}浏览器路径为: {path}")

    def show_default_browser_dialog(self):
        browser_choice, _ = QInputDialog.getItem(self, "选择默认浏览器", "选择默认浏览器:", ["Chrome", "Firefox"], 0,
                                                 False)
        if browser_choice:
            self.default_browser = browser_choice
            self.settings.setValue("default_browser", browser_choice)
            QMessageBox.information(self, "默认浏览器设置", f"默认浏览器已设置为: {browser_choice}")

    def show_current_settings_dialog(self):
        # 创建一个对话框显示当前的设置
        dialog = QDialog(self)
        dialog.setWindowTitle("当前设置")

        layout = QVBoxLayout()

        # 显示 Chrome 驱动路径
        chrome_driver_label = QLabel(f"Chrome 驱动路径: {self.chrome_path}")
        layout.addWidget(chrome_driver_label)

        # 显示 Chrome 浏览器路径
        chrome_binary_label = QLabel(f"Chrome 浏览器路径: {self.chrome_binary_path}")
        layout.addWidget(chrome_binary_label)

        # 显示 Firefox 驱动路径
        firefox_driver_label = QLabel(f"Firefox 驱动路径: {self.firefox_path}")
        layout.addWidget(firefox_driver_label)

        # 显示 Firefox 浏览器路径
        firefox_binary_label = QLabel(f"Firefox 浏览器路径: {self.firefox_binary_path}")
        layout.addWidget(firefox_binary_label)

        # 显示默认浏览器
        default_browser_label = QLabel(f"默认浏览器: {self.default_browser}")
        layout.addWidget(default_browser_label)

        # 显示当前截图快捷键
        current_hotkey_label = QLabel(f"截图快捷键: {self.screenshot_hotkey}")
        layout.addWidget(current_hotkey_label)

        dialog.setLayout(layout)

        # 添加一个确定按钮
        ok_button = QPushButton("确定", dialog)
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.exec_()

    def append_screenshot_result(self, bug_info):
        case_id = self.current_case_id
        module_id = self.current_module_id

        error_file_path = get_user_data_path("import.json")

        # 读取最新的import.json文件内容
        with open(error_file_path, "r") as file:
            data = json.load(file)

        # 查找指定的模块和用例
        for module in data:
            if str(module["id"]) == module_id:
                for case in module.get("caseVoList", []):
                    if str(case["id"]) == case_id:
                        # 读取并解析imageResult字段为JSON,如果存在且有效
                        existing_image_results = []
                        if "imageResult" in case and case["imageResult"]:
                            try:
                                existing_image_results = json.loads(case["imageResult"])
                                if not isinstance(existing_image_results, list):
                                    existing_image_results = [existing_image_results]
                            except json.JSONDecodeError:
                                logger.error("imageResult字段解析错误,将被覆盖。")
                                existing_image_results = []

                        # 追加新的截图结果
                        updated_image_results = existing_image_results + [bug_info]
                        case["imageResult"] = json.dumps(updated_image_results, ensure_ascii=False)
                        break

        # 保存修改后的整个data到import.json
        with open(error_file_path, "w") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        self.data = load_data(get_user_data_path("import.json"))


class BrowserSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览器与驱动设置")
        self.parent = parent
        self.init_ui()
        self.adjust_position()

    def init_ui(self):
        layout = QVBoxLayout()

        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["浏览器名称", "浏览器启动路径", "驱动路径", "操作"])

        # 设置列宽比例
        total_width = self.parent.width() if self.parent else 800
        self.table.setColumnWidth(0, int(total_width * 0.10))  # 浏览器名称列
        self.table.setColumnWidth(1, int(total_width * 0.35))  # 浏览器启动路径列
        self.table.setColumnWidth(2, int(total_width * 0.30))  # 驱动路径列
        self.table.setColumnWidth(3, int(total_width * 0.25))  # 操作列

        # 设置表格样式
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
            }
            QTableWidget::item {
                padding: 5px;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #333;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)

        # 添加浏览器数据
        self.browsers = [
            {'name': 'firefox', 'path': '/opt/apps/org.mozilla.firefox-nal/files/firefox-nal/firefox-bin'},
            {'name': '红莲花', 'path': '/opt/apps/com.haitaichina.htbrowser/files/htbrowser.sh'},
            {'name': '奇安信', 'path': '/opt/apps/com.qianxin.browser-stable/files/com.qianxin.browser'}
        ]

        for row, browser in enumerate(self.browsers):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(browser['name']))
            self.table.setItem(row, 1,
                               QTableWidgetItem(self.parent.settings.value(f"{browser['name']}_path", browser['path'])))
            self.table.setItem(row, 2,
                               QTableWidgetItem(self.parent.settings.value(f"{browser['name']}_driver_path", "未设置")))

            # 添加设置按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            browser_btn = QPushButton("设置浏览器")
            driver_btn = QPushButton("设置驱动")
            browser_btn.clicked.connect(lambda _, b=browser['name']: self.set_browser_path(b))
            driver_btn.clicked.connect(lambda _, b=browser['name']: self.set_driver_path(b))

            # 设置按钮样式
            button_style = """
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #c0c0c0;
                    padding: 5px 10px;
                    margin: 2px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """
            browser_btn.setStyleSheet(button_style)
            driver_btn.setStyleSheet(button_style)

            btn_layout.addWidget(browser_btn)
            btn_layout.addWidget(driver_btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_widget.setLayout(btn_layout)

            self.table.setCellWidget(row, 3, btn_widget)

        # 设置行高
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 40)

        layout.addWidget(self.table)

        # 创建底部按钮容器
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)

        # 添加刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_table)
        refresh_btn.setStyleSheet(button_style)
        bottom_layout.addWidget(refresh_btn)

        # 添加重置按钮
        reset_btn = QPushButton("重置为默认值")
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setStyleSheet(button_style)
        bottom_layout.addWidget(reset_btn)

        # 添加一个弹簧以将按钮推到右侧
        bottom_layout.addStretch()

        layout.addWidget(bottom_widget)

        self.setLayout(layout)

    def reset_to_defaults(self):
        default_paths = {
            'firefox': '/opt/apps/org.mozilla.firefox-nal/files/firefox-nal/firefox-bin.sh',
            '红莲花': '/opt/apps/com.haitaichina.htbrowser/files/htbrowser.sh',
            '奇安信': '/opt/apps/com.qianxin.browser-stable/files/com.qianxin.browser'
        }

        for browser, path in default_paths.items():
            self.parent.settings.setValue(f"{browser}_path", path)

        self.refresh_table()
        QMessageBox.information(self, "重置完成", "所有浏览器路径已重置为默认值。")

    def adjust_position(self):
        if self.parent:
            parent_geo = self.parent.geometry()
            dialog_width = parent_geo.width()
            dialog_height = int(parent_geo.height() * 0.8)  # 设置高度为主窗口的80%
            x = parent_geo.x()
            y = parent_geo.y() + (parent_geo.height() - dialog_height) // 2
            self.setGeometry(x, y, dialog_width, dialog_height)

        # 调整表格大小以适应对话框
        self.table.setFixedWidth(dialog_width - 20)  # 减去一些边距

        # 重新计算并设置列宽
        available_width = self.table.width() - self.table.verticalHeader().width()
        self.table.setColumnWidth(0, int(available_width * 0.10))  # 浏览器名称列
        self.table.setColumnWidth(1, int(available_width * 0.32))  # 浏览器启动路径列
        self.table.setColumnWidth(2, int(available_width * 0.30))  # 驱动路径列
        # 操作列会自动填充剩余空间

    def check_browser_path(self, path):
        if os.path.exists(path):
            return path
        return f"没有检测到安装{path.split('/')[-1].split('.')[0]}浏览器"

    def set_browser_path(self, browser_name):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{browser_name}浏览器路径", "", "所有文件 (*)")
        if path:
            self.parent.settings.setValue(f"{browser_name}_path", path)
            logger.info(f"设置 {browser_name} 路径为: {path}")
            self.refresh_table()

    def set_driver_path(self, browser_name):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{browser_name}驱动路径", "", "所有文件 (*)")
        if path:
            self.parent.settings.setValue(f"{browser_name}_driver_path", path)
            logger.info(f"设置 {browser_name} 驱动路径为: {path}")
            self.refresh_table()

    def refresh_table(self):
        for row, browser in enumerate(self.browsers):
            current_path = self.parent.settings.value(f"{browser['name']}_path", "未设置")
            self.table.setItem(row, 1, QTableWidgetItem(current_path))
            driver_path = self.parent.settings.value(f"{browser['name']}_driver_path", "未设置")
            self.table.setItem(row, 2, QTableWidgetItem(driver_path))


def load_data(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
            data.sort(key=lambda x: x['id'])
            for module in data:
                module['caseVoList'].sort(key=lambda x: x['id'])
                for case in module['caseVoList']:
                    case.setdefault('isTested', False)  # 确保每个案例都有 isTested 字段
        return data
    except FileNotFoundError:
        return []


if __name__ == '__main__':
    try:
        # 在主程序开始时调用此函数
        if not check_mitmproxy():
            logger.critical("mitmproxy 检查失败，程序将退出。")
            sys.exit(1)
        # 设置环境变量
        os.environ['QT_IM_MODULE'] = 'fcitx'  # 或者 'ibus'，取决于你的输入法
        os.environ['XMODIFIERS'] = '@im=fcitx'  # 或者 '@im=ibus'
        os.environ['GTK_IM_MODULE'] = 'fcitx'  # 或者 'ibus'

        # 设置默认语言为系统语言
        QLocale.setDefault(QLocale.system())

        # 尝试启用输入法支持（如果属性存在的话）
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # 创建应用程序实例
        app = QApplication(sys.argv)

        # 读取QSS文件并设置样式
        with open(get_resource_path('MacOS.qss'), 'r') as f:
            style = f.read()
            app.setStyleSheet(style)
        window = App()
        window.show()

        # 显式启用输入法
        input_method = QGuiApplication.inputMethod()
        input_method.show()

        sys.exit(app.exec_())
        pass
    except Exception as e:
        logger.exception("An error occurred:")
        logger.critical(f"An error occurred. Please check the log file for details.")
        sys.exit(1)