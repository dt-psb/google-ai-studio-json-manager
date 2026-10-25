#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google AI Studio - Prompt and Chunk Manager Desktop Application
PyQt5 / QtWebEngine Desktop Program with Integrated Error Logging
"""

import sys
import os
import traceback
import datetime

# 작업 디렉터리를 스크립트 위치로 고정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(CURRENT_DIR)

# QtWebEngine 안정성 극대화 및 GPU/Chromium 렌더 프로세스 충돌(0xC0000005) 방지 환경 변수
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-dev-shm-usage "
    "--no-sandbox "
    "--disable-gpu-shader-disk-cache "
    "--disable-gpu-process-crash-limit "
    "--disable-backgrounding-occluded-windows "
    "--enable-smooth-scrolling "
    "--js-flags=--max-old-space-size=4096"
)

LOG_FILE = os.path.join(CURRENT_DIR, "app_debug.log")

class LoggerTee:
    """stdout과 stderr를 콘솔과 app_debug.log 파일 양쪽에 동시에 기록"""
    def __init__(self, filename, stream):
        self.stream = stream
        self.log = open(filename, "a", encoding="utf-8", buffering=1)

    def write(self, message):
        try:
            self.stream.write(message)
            self.stream.flush()
        except Exception:
            pass
        try:
            self.log.write(message)
            self.log.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass
        try:
            self.log.flush()
        except Exception:
            pass


# 로그 파일 초기화 및 기록 시작
try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Launching Google AI Studio Desktop App\n")
        f.write(f"Python Executable: {sys.executable}\n")
        f.write(f"Python Version: {sys.version}\n")
        f.write(f"Working Dir: {CURRENT_DIR}\n")
        f.write("=" * 60 + "\n")
    sys.stdout = LoggerTee(LOG_FILE, sys.stdout)
    sys.stderr = LoggerTee(LOG_FILE, sys.stderr)
except Exception as log_init_err:
    print(f"Warning: Could not initialize log file: {log_init_err}")


def show_fatal_error(msg):
    """치명적 오류 발생 시 로그 기록 및 네이티브 팝업 경고"""
    print(f"\n[FATAL ERROR] {msg}\n")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"{msg}\n\n상세 내용은 app_debug.log 파일을 확인하세요.", "Google AI Studio 실행 오류", 0x10)
    except Exception:
        pass


try:
    import threading
    import time
    import urllib.parse
    import socketserver
    from PyQt5.QtCore import QUrl, Qt
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QFileDialog, QInputDialog, QShortcut
    )
    from PyQt5.QtGui import QIcon, QKeySequence, QColor
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineSettings
except Exception as e:
    err_text = f"PyQt5 또는 QtWebEngine 모듈을 불러올 수 없습니다.\n오류: {e}\n\n{traceback.format_exc()}"
    show_fatal_error(err_text)
    sys.exit(1)

try:
    import server
except Exception as e:
    err_text = f"server.py 모듈을 불러올 수 없습니다.\n오류: {e}\n\n{traceback.format_exc()}"
    show_fatal_error(err_text)
    sys.exit(1)

# Windows 작업 표시줄 독립 아이콘 ID 등록
try:
    import ctypes
    myappid = "google.aistudio.chunkmanager.desktop.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception as e:
    print(f"AppUserModelID setup notice: {e}")


THEME_TITLEBAR_COLORS = {
    "dark": {"is_dark": True, "bg": "#1e2024", "text": "#f8fafc", "border": "#3c4046"},
    "midnight": {"is_dark": True, "bg": "#0f172a", "text": "#ffffff", "border": "#334155"},
    "forest": {"is_dark": True, "bg": "#0d1e17", "text": "#ecfdf5", "border": "#234839"},
    "nord": {"is_dark": True, "bg": "#222732", "text": "#f1f5f9", "border": "#3f495e"},
    "cyberpunk": {"is_dark": True, "bg": "#1a122a", "text": "#faf5ff", "border": "#443166"},
    "oled": {"is_dark": True, "bg": "#0b0b0d", "text": "#ffffff", "border": "#2c2c31"},
    "warm": {"is_dark": False, "bg": "#f4eee2", "text": "#1c1917", "border": "#cfc1ab"},
    "cleanlight": {"is_dark": False, "bg": "#f1f5f9", "text": "#0f172a", "border": "#cbd5e1"},
    "rosé": {"is_dark": True, "bg": "#1c1018", "text": "#fce7f3", "border": "#46253a"},
    "rose": {"is_dark": True, "bg": "#1c1018", "text": "#fce7f3", "border": "#46253a"},
    "abyss": {"is_dark": True, "bg": "#071a1f", "text": "#e0fbff", "border": "#134151"},
    "ember": {"is_dark": True, "bg": "#181003", "text": "#fffbeb", "border": "#3d2a08"},
    "sakura": {"is_dark": False, "bg": "#fce7ef", "text": "#1a0612", "border": "#f4a7c4"},
}


def apply_dark_titlebar(window, bg_hex="#1e2024", text_hex="#f8fafc", border_hex="#3c4046", is_dark=True):
    """Windows 10/11 네이티브 다크/라이트 타이틀바 & 커스텀 테마 색상 적용"""
    try:
        import ctypes
        from ctypes import c_int, byref

        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi

        # 1. DWMWA_USE_IMMERSIVE_DARK_MODE (20 또는 19)
        dark_flag = c_int(1 if is_dark else 0)
        res = dwm.DwmSetWindowAttribute(hwnd, 20, byref(dark_flag), ctypes.sizeof(dark_flag))
        if res != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, byref(dark_flag), ctypes.sizeof(dark_flag))

        # 16진수 색상 변환 함수 (#RRGGBB -> 0x00BBGGRR COLORREF)
        def hex_to_colorref(hex_str):
            h = hex_str.lstrip("#")
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
            return (b << 16) | (g << 8) | r

        # 2. Windows 11 DWMWA_CAPTION_COLOR = 35 (타이틀바 배경색)
        caption_color = c_int(hex_to_colorref(bg_hex))
        dwm.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), ctypes.sizeof(caption_color))

        # 3. Windows 11 DWMWA_TEXT_COLOR = 36 (타이틀 글자색)
        text_color = c_int(hex_to_colorref(text_hex))
        dwm.DwmSetWindowAttribute(hwnd, 36, byref(text_color), ctypes.sizeof(text_color))

        # 4. Windows 11 DWMWA_BORDER_COLOR = 34 (창 테두리 색상)
        border_color = c_int(hex_to_colorref(border_hex))
        dwm.DwmSetWindowAttribute(hwnd, 34, byref(border_color), ctypes.sizeof(border_color))
    except Exception as e:
        pass


def get_current_theme_info(widget):
    window = widget.window() if (widget and hasattr(widget, "window")) else widget
    theme = getattr(window, "current_theme", "dark") if window else "dark"
    cfg = THEME_TITLEBAR_COLORS.get(theme, THEME_TITLEBAR_COLORS.get("dark", {}))
    return theme, cfg


def show_styled_message_box(parent, icon, title, msg, buttons, default_button=None):
    """현재 테마(다크/라이트)에 맞춰 가독성 100% 보장하는 네이티브 모달 다이얼로그"""
    mb = QMessageBox(icon, title, str(msg), buttons, parent)
    if default_button:
        mb.setDefaultButton(default_button)

    theme, cfg = get_current_theme_info(parent)
    is_dark = cfg.get("is_dark", True)

    # 버튼 텍스트 한글화
    btn_yes = mb.button(QMessageBox.Yes)
    if btn_yes: btn_yes.setText("확인 (예)")
    btn_no = mb.button(QMessageBox.No)
    if btn_no: btn_no.setText("취소 (아니오)")
    btn_ok = mb.button(QMessageBox.Ok)
    if btn_ok: btn_ok.setText("확인")
    btn_cancel = mb.button(QMessageBox.Cancel)
    if btn_cancel: btn_cancel.setText("취소")

    if is_dark:
        bg = cfg.get("bg", "#1e2024")
        text = cfg.get("text", "#f8fafc")
        border = cfg.get("border", "#3c4046")
        mb.setStyleSheet(f"""
            QMessageBox {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text} !important;
                font-size: 13px;
                font-family: 'Segoe UI', 'Pretendard', sans-serif;
                min-width: 320px;
                line-height: 1.4;
            }}
            QPushButton {{
                background-color: #272a30;
                color: #f8fafc !important;
                border: 1px solid {border};
                border-radius: 7px;
                padding: 7px 20px;
                font-size: 12px;
                font-weight: 600;
                min-width: 75px;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
                border-color: #60a5fa;
                color: #ffffff !important;
            }}
            QPushButton:pressed {{
                background-color: #1d4ed8;
            }}
        """)
        apply_dark_titlebar(mb, bg_hex=bg, text_hex=text, border_hex=border, is_dark=True)
    else:
        bg = cfg.get("bg", "#ffffff")
        text = cfg.get("text", "#0f172a")
        border = cfg.get("border", "#cbd5e1")
        mb.setStyleSheet(f"""
            QMessageBox {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text} !important;
                font-size: 13px;
                font-family: 'Segoe UI', 'Pretendard', sans-serif;
                min-width: 320px;
                line-height: 1.4;
            }}
            QPushButton {{
                background-color: #f8fafc;
                color: {text} !important;
                border: 1px solid {border};
                border-radius: 7px;
                padding: 7px 20px;
                font-size: 12px;
                font-weight: 600;
                min-width: 75px;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
                border-color: #2563eb;
                color: #ffffff !important;
            }}
            QPushButton:pressed {{
                background-color: #1d4ed8;
            }}
        """)
        apply_dark_titlebar(mb, bg_hex=bg, text_hex=text, border_hex=border, is_dark=False)

    return mb.exec_()


def show_styled_input_dialog(parent, title, msg, default_value=""):
    """현재 테마에 맞춘 프롬프트 입력 다이얼로그"""
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(str(msg))
    dlg.setTextValue(str(default_value or ""))
    dlg.setOkButtonText("확인")
    dlg.setCancelButtonText("취소")

    theme, cfg = get_current_theme_info(parent)
    is_dark = cfg.get("is_dark", True)

    if is_dark:
        bg = cfg.get("bg", "#1e2024")
        text = cfg.get("text", "#f8fafc")
        border = cfg.get("border", "#3c4046")
        dlg.setStyleSheet(f"""
            QInputDialog {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text} !important;
                font-size: 13px;
                font-family: 'Segoe UI', 'Pretendard', sans-serif;
            }}
            QLineEdit {{
                background-color: #121316;
                color: #f8fafc !important;
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: #3b82f6;
            }}
            QPushButton {{
                background-color: #272a30;
                color: #f8fafc !important;
                border: 1px solid {border};
                border-radius: 7px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
                min-width: 70px;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
                color: #ffffff !important;
            }}
        """)
        apply_dark_titlebar(dlg, bg_hex=bg, text_hex=text, border_hex=border, is_dark=True)
    else:
        bg = cfg.get("bg", "#ffffff")
        text = cfg.get("text", "#0f172a")
        border = cfg.get("border", "#cbd5e1")
        dlg.setStyleSheet(f"""
            QInputDialog {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text} !important;
                font-size: 13px;
                font-family: 'Segoe UI', 'Pretendard', sans-serif;
            }}
            QLineEdit {{
                background-color: #ffffff;
                color: {text} !important;
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: #3b82f6;
            }}
            QPushButton {{
                background-color: #f8fafc;
                color: {text} !important;
                border: 1px solid {border};
                border-radius: 7px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
                min-width: 70px;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
                color: #ffffff !important;
            }}
        """)
        apply_dark_titlebar(dlg, bg_hex=bg, text_hex=text, border_hex=border, is_dark=False)

    ok = dlg.exec_() == QInputDialog.Accepted
    return ok, dlg.textValue()


class CustomWebEnginePage(QWebEnginePage):
    """자바스크립트 alert, confirm, prompt를 네이티브 Qt 다이얼로그로 안전하게 처리 및 콘솔 에러 추적"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 클립보드 / 미디어 등 권한 요청 시 자동 허용
        self.featurePermissionRequested.connect(self._grant_permission)

    def acceptNavigationRequest(self, url, navType, isMainFrame):
        """설명서 또는 외부 링크 클릭 시 기본 시스템 브라우저(Chrome/Edge 등)로 연결"""
        url_str = url.toString()
        if "manual.html" in url_str:
            import webbrowser
            webbrowser.open(url_str)
            return False
        return super().acceptNavigationRequest(url, navType, isMainFrame)

    def createWindow(self, windowType):
        """target='_blank' 또는 window.open 링크 요청 시 시스템 기본 브라우저로 안전하게 팝업"""
        import webbrowser
        class ExternalLinkPage(QWebEnginePage):
            def acceptNavigationRequest(self, url, navType, isMainFrame):
                webbrowser.open(url.toString())
                return False
        self._temp_ext_page = ExternalLinkPage(self)
        return self._temp_ext_page

    def _grant_permission(self, origin, feature):
        self.setFeaturePermission(origin, feature, QWebEnginePage.PermissionGrantedByUser)

    def javaScriptAlert(self, securityOrigin, msg):
        try:
            show_styled_message_box(
                self.view(),
                QMessageBox.Information,
                "Google AI Studio",
                str(msg),
                QMessageBox.Ok
            )
        except Exception as e:
            print(f"javaScriptAlert notice: {e}")

    def javaScriptConfirm(self, securityOrigin, msg):
        # 인앱 모달(showConfirmDialog)이 HTML 레벨에서 처리되므로,
        # 네이티브 modal exec_()이 Chromium IPC를 블로킹하여 화면이 검게 먹통되는 현상 방지
        return True

    def javaScriptPrompt(self, securityOrigin, msg, defaultValue, *args):
        try:
            ok, text = show_styled_input_dialog(
                self.view(),
                "입력",
                str(msg),
                defaultValue
            )
            if args and hasattr(args[0], 'setValue'):
                args[0].setValue(text if ok else "")
                return ok
            return ok, text
        except Exception as prompt_err:
            print(f"javaScriptPrompt notice: {prompt_err}")
            return False, ""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # 자바스크립트 오류 로그 추적
        if level >= 2:  # 2: Error
            print(f"[JS ERROR] {sourceID}:{lineNumber} -> {message}")


class DevToolsWindow(QMainWindow):
    """F12 개발자 도구 전용 창"""
    def __init__(self, target_page, parent=None):
        super().__init__(parent)
        self.setWindowTitle("개발자 도구 (DevTools) - Google AI Studio")
        self.resize(1000, 600)
        self.devtools_view = QWebEngineView()
        target_page.setDevToolsPage(self.devtools_view.page())
        self.setCentralWidget(self.devtools_view)

    def closeEvent(self, event):
        self.hide()
        event.ignore()


def update_window_theme(window, theme_name):
    cfg = THEME_TITLEBAR_COLORS.get(theme_name, THEME_TITLEBAR_COLORS["dark"])
    window.current_theme = theme_name
    apply_dark_titlebar(
        window,
        bg_hex=cfg["bg"],
        text_hex=cfg["text"],
        border_hex=cfg["border"],
        is_dark=cfg["is_dark"]
    )


class MainWindow(QMainWindow):
    def __init__(self, url, saved_theme="dark"):
        super().__init__()
        self.url = url
        self.devtools_win = None
        self.current_theme = saved_theme
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(" ")
        self.resize(1440, 900)
        self.setMinimumSize(960, 600)

        # 초기 타이틀바 테마 적용
        update_window_theme(self, self.current_theme)

        # 앱 아이콘 설정
        icon_path = os.path.join(CURRENT_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

        # 화면 중앙 배치
        screen = QApplication.primaryScreen().geometry()
        x = max(0, (screen.width() - self.width()) // 2)
        y = max(0, (screen.height() - self.height()) // 2)
        self.move(x, y)

        # 다크 테마 배경 스타일 설정 (흰 화면 번쩍임 및 깜빡임 원천 차단)
        self.setStyleSheet("QMainWindow { background-color: #131314; }")

        # WebEngine 설정
        self.view = QWebEngineView(self)
        self.view.setStyleSheet("background-color: #131314;")
        palette = self.view.palette()
        palette.setColor(palette.Window, QColor("#131314"))
        palette.setColor(palette.Base, QColor("#131314"))
        self.view.setPalette(palette)

        self.page = CustomWebEnginePage(self.view)
        # 기본 배경을 다크로 설정하여 흰 화면 번쩍임 및 백지화 방지
        self.page.setBackgroundColor(QColor("#131314"))
        self.view.setPage(self.page)

        # 렌더 프로세스 비정상 종료 시 자동 복구(흰 화면 방지)
        self.view.renderProcessTerminated.connect(self.on_render_process_terminated)

        # WebEngine 설정 활성화
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, False)

        self.setCentralWidget(self.view)

        # 다운로드 핸들러 연결
        profile = self.page.profile()
        profile.downloadRequested.connect(self.on_download_requested)

        # 단축키 설정
        # 1. 새로고침 (F5, Ctrl+R)
        shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        shortcut_f5.activated.connect(self.view.reload)
        shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_ctrl_r.activated.connect(self.view.reload)

        # 2. 강제 새로고침 (Ctrl+Shift+R)
        shortcut_hard_reload = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        shortcut_hard_reload.activated.connect(lambda: self.view.triggerPageAction(QWebEnginePage.ReloadAndBypassCache))

        # 3. 개발자 도구 (F12)
        shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        shortcut_f12.activated.connect(self.toggle_devtools)

        # 4. 전체화면 (F11)
        shortcut_f11 = QShortcut(QKeySequence("F11"), self)
        shortcut_f11.activated.connect(self.toggle_fullscreen)

        # 5. 줌 조절 (Ctrl + / Ctrl - / Ctrl 0)
        shortcut_zoom_in = QShortcut(QKeySequence("Ctrl+="), self)
        shortcut_zoom_in.activated.connect(lambda: self.view.setZoomFactor(min(3.0, self.view.zoomFactor() + 0.1)))
        shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        shortcut_zoom_out.activated.connect(lambda: self.view.setZoomFactor(max(0.3, self.view.zoomFactor() - 0.1)))
        shortcut_zoom_reset = QShortcut(QKeySequence("Ctrl+0"), self)
        shortcut_zoom_reset.activated.connect(lambda: self.view.setZoomFactor(1.0))

        # 페이지 로드
        print(f"Loading UI URL: {self.url}")
        self.view.titleChanged.connect(self.on_title_changed)
        self.view.load(QUrl(self.url))

    def on_render_process_terminated(self, termination_status, exit_code):
        """WebEngine 렌더 프로세스가 비정상 종료되거나 메모리 초과로 크래시된 경우 자동 복구"""
        print(f"[WARNING] WebEngine render process terminated: status={termination_status}, exit_code={exit_code}")
        # 동기 즉시 리로드 시 Qt 내부 IPC 채널 및 마우스 이벤트 포커스가 먹통되는 현상 방지
        # 300ms 지연 후 안전하게 리로드 및 윈도우 포커스/마우스 이벤트 채널 복원
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(300, self._safe_reload_after_crash)
        except Exception as e:
            print(f"Recovery timer error: {e}")

    def _safe_reload_after_crash(self):
        try:
            self.view.reload()
            self.view.setFocus()
            self.activateWindow()
            print("WebEngine recovered and reloaded cleanly after termination.")
        except Exception as e:
            print(f"Reload after crash notice: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        update_window_theme(self, self.current_theme)

    def on_title_changed(self, title):
        """웹에서 테마 변경 시 document.title을 통해 전달되는 테마 신호 감지하여 네이티브 타이틀바 즉각 갱신"""
        if title.startswith("__ais_theme__:"):
            theme_name = title.replace("__ais_theme__:", "").strip()
            update_window_theme(self, theme_name)

    def on_download_requested(self, download_item):
        """웹에서 다운로드 발생 시 C드라이브 Downloads 폴더를 기본 위치로 하여 저장 다이얼로그 표시"""
        suggested_filename = download_item.suggestedFileName() or "download.json"
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(downloads_dir, exist_ok=True)
            default_save_path = os.path.join(downloads_dir, suggested_filename)
        except Exception:
            default_save_path = os.path.join(CURRENT_DIR, suggested_filename)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "파일 저장 (기본 위치: 내 PC 다운로드 폴더)",
            default_save_path,
            "JSON 파일 (*.json);;모든 파일 (*.*)"
        )
        if save_path:
            download_item.setPath(save_path)
            download_item.accept()
            print(f"File downloaded to: {save_path}")
        else:
            download_item.cancel()

    def toggle_devtools(self):
        """F12 개발자 도구 토글"""
        if self.devtools_win is None:
            self.devtools_win = DevToolsWindow(self.page, self)
        if self.devtools_win.isVisible():
            self.devtools_win.hide()
        else:
            self.devtools_win.show()
            self.devtools_win.raise_()
            self.devtools_win.activateWindow()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


class ServerThread(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.httpd = None
        self.daemon = True

    def run(self):
        socketserver.TCPServer.allow_reuse_address = True
        try:
            self.httpd = socketserver.TCPServer(("", self.port), server.AISHandler)
            print(f"Server started on http://127.0.0.1:{self.port}")
            self.httpd.serve_forever()
        except Exception as e:
            print(f"[Server Thread Error] {e}\n{traceback.format_exc()}")

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
                print("Server stopped cleanly.")
            except Exception as e:
                print(f"Server stop error: {e}")


def find_free_port(start_port=8500, max_attempts=20):
    port = start_port
    for _ in range(max_attempts):
        try:
            test_server = socketserver.TCPServer(("", port), server.AISHandler)
            test_server.server_close()
            return port
        except OSError:
            port += 1
    return start_port


def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        # QtWebEngine 안정성 및 Windows 메모리 접근 위반(0xC0000005) 방지
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

        app = QApplication(sys.argv)
        app.setApplicationName("Google AI Studio Prompt and Chunk Manager")

        port = find_free_port(server.DEFAULT_PORT)
        server_thread = ServerThread(port)
        server_thread.start()

        time.sleep(0.3)

        saved_settings = server.load_app_settings()
        saved_theme = saved_settings.get("theme", "dark")

        target_url = f"http://127.0.0.1:{port}/index.html?theme={urllib.parse.quote(saved_theme)}"
        window = MainWindow(target_url, saved_theme=saved_theme)
        window.show()

        print("Desktop application window displayed successfully.")
        exit_code = app.exec_()

        server_thread.stop()
        print(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        show_fatal_error(f"실행 중 예외 발생: {e}\n\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
