import os
import sys
import json
import math
import wave
import struct
import shutil
import random
import zipfile
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QMenu, QSystemTrayIcon,
    QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QSlider, QFileDialog,
    QMessageBox, QFrame, QComboBox, QTabWidget, QCheckBox,
    QLineEdit, QColorDialog
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, QUrl
from PyQt6.QtGui import QPixmap, QTransform, QAction, QIcon, QColor, QFontDatabase, QCursor, QPainter, QRadialGradient
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

USER_DATA_DIR = Path.home() / "Documents" / "KomaStage"
PETS_DIR = USER_DATA_DIR / "pets"
FONTS_DIR = USER_DATA_DIR / "fonts"
SOUNDS_DIR = USER_DATA_DIR / "sounds"
ICONS_DIR = USER_DATA_DIR / "icons"
CONFIG_FILE = USER_DATA_DIR / "config.json"

THEME_PRESETS = {
    "Miku Teal (Dark)": {"mode": "dark", "accent": "#39C5BB"},
    "Sakura Pink (Dark)": {"mode": "dark", "accent": "#FF7EB6"},
    "Lavender Purple (Dark)": {"mode": "dark", "accent": "#B388FF"},
    "Amber Gold (Dark)": {"mode": "dark", "accent": "#FFB74D"},
    "Minimal Light": {"mode": "light", "accent": "#00897B"}
}

BUILTIN_FONTS = {
    "Cute Rounded": '"Arial Rounded MT Bold", "Quicksand", "Nunito", "Trebuchet MS", sans-serif',
    "Clean Modern": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    "Retro Pixel / Mono": '"Courier New", "Menlo", "Consolas", monospace',
    "Playful Handwritten": '"Chalkboard SE", "Comic Sans MS", "Marker Felt", cursive'
}

DEFAULT_SFX_PRESETS = [
    "Cute Chime",
    "Retro 8-Bit Coin",
    "Soft Bubble Pop",
    "Happy Arpeggio",
    "Random Mix"
]


class AudioActivityDetector:
    """Hiçbir mikrofon veya kayıt izni istemeden sistem ses çıkışının aktif olup olmadığını algılar."""
    def is_system_playing_audio(self):
        try:
            if sys.platform == "darwin":
                import ctypes
                ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")

                class AudioObjectPropertyAddress(ctypes.Structure):
                    _fields_ = [
                        ("mSelector", ctypes.c_uint32),
                        ("mScope", ctypes.c_uint32),
                        ("mElement", ctypes.c_uint32),
                    ]

                def fourcc(s):
                    return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])

                ca.AudioObjectGetPropertyData.argtypes = [
                    ctypes.c_uint32,
                    ctypes.POINTER(AudioObjectPropertyAddress),
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ]
                ca.AudioObjectGetPropertyData.restype = ctypes.c_int32

                addr_dev = AudioObjectPropertyAddress(fourcc("dOut"), fourcc("glob"), 0)
                dev_id = ctypes.c_uint32(0)
                size = ctypes.c_uint32(ctypes.sizeof(dev_id))
                status = ca.AudioObjectGetPropertyData(
                    1, ctypes.byref(addr_dev), 0, None, ctypes.byref(size), ctypes.byref(dev_id)
                )
                if status == 0 and dev_id.value != 0:
                    addr_run = AudioObjectPropertyAddress(fourcc("goin"), fourcc("glob"), 0)
                    is_running = ctypes.c_uint32(0)
                    size_r = ctypes.c_uint32(ctypes.sizeof(is_running))
                    st2 = ca.AudioObjectGetPropertyData(
                        dev_id.value, ctypes.byref(addr_run), 0, None, ctypes.byref(size_r), ctypes.byref(is_running)
                    )
                    if st2 == 0 and is_running.value != 0:
                        return True

            elif sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", wintypes.DWORD),
                        ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD),
                        ("Data4", wintypes.c_ubyte * 8),
                    ]

                def make_guid(s):
                    s = s.strip("{}")
                    parts = s.split("-")
                    d4 = bytes.fromhex(parts[3] + parts[4])
                    return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), (ctypes.c_ubyte * 8)(*d4))

                ole32 = ctypes.windll.ole32
                ole32.CoInitialize(None)
                CLSID_MMDeviceEnumerator = make_guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
                IID_IMMDeviceEnumerator = make_guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
                IID_IAudioMeterInformation = make_guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

                enum_ptr = ctypes.c_void_p()
                hr = ole32.CoCreateInstance(
                    ctypes.byref(CLSID_MMDeviceEnumerator), None, 23,
                    ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enum_ptr)
                )
                if hr == 0 and enum_ptr.value:
                    vtbl_enum = ctypes.cast(enum_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    get_def = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(vtbl_enum[4])
                    dev_ptr = ctypes.c_void_p()
                    if get_def(enum_ptr, 0, 1, ctypes.byref(dev_ptr)) == 0 and dev_ptr.value:
                        vtbl_dev = ctypes.cast(dev_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                        activate = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vtbl_dev[3])
                        meter_ptr = ctypes.c_void_p()
                        if activate(dev_ptr, ctypes.byref(IID_IAudioMeterInformation), 23, None, ctypes.byref(meter_ptr)) == 0 and meter_ptr.value:
                            vtbl_meter = ctypes.cast(meter_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                            get_peak = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float))(vtbl_meter[3])
                            peak = ctypes.c_float(0.0)
                            if get_peak(meter_ptr, ctypes.byref(peak)) == 0:
                                release_m = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl_meter[2])
                                release_m(meter_ptr)
                                release_d = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl_dev[2])
                                release_d(dev_ptr)
                                release_e = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl_enum[2])
                                release_e(enum_ptr)
                                return peak.value > 0.01

            else:
                asound = Path("/proc/asound")
                if asound.exists():
                    for status_file in asound.glob("card*/pcm*p/sub*/status"):
                        try:
                            txt = status_file.read_text(errors="ignore")
                            if "state: RUNNING" in txt:
                                return True
                        except Exception:
                            pass
        except Exception:
            pass
        return False


class FloatingEmoteOverlay(QWidget):
    """Maskotun kafasının üzerinde hafifçe salınarak yukarı süzülen mini duygu efekti (♡, ♪, Zzz, !)."""
    def __init__(self, symbol, color_hex, start_x, start_y):
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.lbl = QLabel(symbol)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet(f"""
            QLabel {{
                color: {color_hex};
                font-size: 18px;
                font-weight: 800;
                background: transparent;
            }}
        """)
        layout.addWidget(self.lbl)
        self.adjustSize()

        self.base_x = start_x - (self.width() // 2)
        self.curr_y = float(start_y)
        self.step = 0
        self.max_steps = 36
        self.move(int(self.base_x), int(self.curr_y))
        self.show()

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.tick)
        self.anim_timer.start(32)

    def tick(self):
        self.step += 1
        if self.step >= self.max_steps:
            self.anim_timer.stop()
            self.close()
            return
        self.curr_y -= 1.35
        sway_x = self.base_x + math.sin(self.step * 0.28) * 6.0
        self.move(int(round(sway_x)), int(round(self.curr_y)))
        opacity = max(0.0, 1.0 - (self.step / self.max_steps) ** 1.6)
        self.setWindowOpacity(opacity)


class LaserPointerOverlay(QWidget):
    """Fare ucunu takip eden parlayan kırmızı lazer noktası (tıklama geçirgen)."""
    def __init__(self):
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(28, 28)

        self.follow_timer = QTimer(self)
        self.follow_timer.timeout.connect(self.sync_to_cursor)

    def start(self):
        self.sync_to_cursor()
        self.show()
        self.follow_timer.start(16)

    def stop(self):
        self.follow_timer.stop()
        self.hide()

    def sync_to_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() - 14, pos.y() - 14)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(14, 14, 13)
        grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        grad.setColorAt(0.25, QColor(255, 35, 65, 245))
        grad.setColorAt(0.65, QColor(255, 0, 40, 110))
        grad.setColorAt(1.0, QColor(255, 0, 40, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 26, 26)


class WindowTracker:
    """Tüm işletim sistemlerinde ek izin istemeden açık pencere üst kenarlarını algılar."""
    def __init__(self):
        self.ledges = []

    def refresh(self, screen_rect):
        new_ledges = []
        try:
            if sys.platform == "darwin":
                import ctypes
                cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
                cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

                cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
                cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
                cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
                cf.CFArrayGetCount.restype = ctypes.c_long
                cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
                cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
                cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                cf.CFDictionaryGetValue.restype = ctypes.c_void_p
                cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
                cf.CFStringCreateWithCString.restype = ctypes.c_void_p
                cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                cf.CFNumberGetValue.restype = ctypes.c_bool
                cf.CFRelease.argtypes = [ctypes.c_void_p]

                kCFStringEncodingUTF8 = 0x08000100
                kCFNumberIntType = 9
                kCFNumberDoubleType = 13

                def cf_str(s):
                    return cf.CFStringCreateWithCString(None, s.encode("utf-8"), kCFStringEncodingUTF8)

                key_layer = cf_str("kCGWindowLayer")
                key_bounds = cf_str("kCGWindowBounds")
                key_pid = cf_str("kCGWindowOwnerPID")
                key_x = cf_str("X")
                key_y = cf_str("Y")
                key_w = cf_str("Width")
                key_h = cf_str("Height")

                own_pid = os.getpid()
                win_list = cg.CGWindowListCopyWindowInfo(1 | 16, 0)
                if win_list:
                    count = cf.CFArrayGetCount(win_list)
                    for i in range(count):
                        win_dict = cf.CFArrayGetValueAtIndex(win_list, i)
                        if not win_dict:
                            continue

                        layer_ref = cf.CFDictionaryGetValue(win_dict, key_layer)
                        layer_val = ctypes.c_int(0)
                        if layer_ref:
                            cf.CFNumberGetValue(layer_ref, kCFNumberIntType, ctypes.byref(layer_val))
                        if layer_val.value != 0:
                            continue

                        pid_ref = cf.CFDictionaryGetValue(win_dict, key_pid)
                        pid_val = ctypes.c_int(0)
                        if pid_ref:
                            cf.CFNumberGetValue(pid_ref, kCFNumberIntType, ctypes.byref(pid_val))
                        if pid_val.value == own_pid:
                            continue

                        bounds_ref = cf.CFDictionaryGetValue(win_dict, key_bounds)
                        if bounds_ref:
                            bx, by, bw, bh = ctypes.c_double(0), ctypes.c_double(0), ctypes.c_double(0), ctypes.c_double(0)
                            rx = cf.CFDictionaryGetValue(bounds_ref, key_x)
                            ry = cf.CFDictionaryGetValue(bounds_ref, key_y)
                            rw = cf.CFDictionaryGetValue(bounds_ref, key_w)
                            rh = cf.CFDictionaryGetValue(bounds_ref, key_h)
                            if rx and ry and rw and rh:
                                cf.CFNumberGetValue(rx, kCFNumberDoubleType, ctypes.byref(bx))
                                cf.CFNumberGetValue(ry, kCFNumberDoubleType, ctypes.byref(by))
                                cf.CFNumberGetValue(rw, kCFNumberDoubleType, ctypes.byref(bw))
                                cf.CFNumberGetValue(rh, kCFNumberDoubleType, ctypes.byref(bh))
                                x, y, w, h = int(bx.value), int(by.value), int(bw.value), int(bh.value)
                                if w > 140 and h > 100 and (screen_rect.top() + 35) < y < (screen_rect.bottom() - 80):
                                    new_ledges.append((x, x + w, y))

                    cf.CFRelease(win_list)
                for k in (key_layer, key_bounds, key_pid, key_x, key_y, key_w, key_h):
                    if k:
                        cf.CFRelease(k)

            elif sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                own_pid = os.getpid()

                def enum_cb(hwnd, _):
                    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                        return True
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value == own_pid:
                        return True
                    rect = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 140 and h > 100 and (screen_rect.top() + 35) < rect.top < (screen_rect.bottom() - 80):
                            new_ledges.append((rect.left, rect.right, rect.top))
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            else:
                res = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, timeout=0.5)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        cols = line.split()
                        if len(cols) >= 7:
                            x, y, w, h = int(cols[2]), int(cols[3]), int(cols[4]), int(cols[5])
                            if w > 140 and h > 100 and (screen_rect.top() + 35) < y < (screen_rect.bottom() - 80):
                                new_ledges.append((x, x + w, y))
        except Exception:
            pass
        self.ledges = new_ledges


class SoundEngine:
    """Karakter ses paketlerini ve 4 farklı yerleşik etkileşim sesini yönetir."""
    def __init__(self, manager):
        self.manager = manager
        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
        self.builtin_files = {
            "Cute Chime": SOUNDS_DIR / "cute_chime.wav",
            "Retro 8-Bit Coin": SOUNDS_DIR / "retro_coin.wav",
            "Soft Bubble Pop": SOUNDS_DIR / "bubble_pop.wav",
            "Happy Arpeggio": SOUNDS_DIR / "happy_arpeggio.wav",
        }
        self.ensure_all_builtin_sounds()

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

    def _write_wav(self, filepath, samples, sample_rate=44100):
        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(bytes(samples))

    def ensure_all_builtin_sounds(self):
        sr = 44100
        if not self.builtin_files["Cute Chime"].exists():
            buf = bytearray()
            for freq, dur in [(587.33, 0.08), (880.00, 0.14)]:
                for i in range(int(sr * dur)):
                    t = i / sr
                    env = math.exp(-t * 14.0)
                    val = int(14000 * env * math.sin(2 * math.pi * freq * t))
                    buf.extend(struct.pack("<h", max(-32767, min(32767, val))))
            self._write_wav(self.builtin_files["Cute Chime"], buf, sr)

        if not self.builtin_files["Retro 8-Bit Coin"].exists():
            buf = bytearray()
            for freq, dur in [(987.77, 0.06), (1318.51, 0.16)]:
                for i in range(int(sr * dur)):
                    t = i / sr
                    env = math.exp(-t * 11.0)
                    s = math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(6 * math.pi * freq * t)
                    val = int(11000 * env * s)
                    buf.extend(struct.pack("<h", max(-32767, min(32767, val))))
            self._write_wav(self.builtin_files["Retro 8-Bit Coin"], buf, sr)

        if not self.builtin_files["Soft Bubble Pop"].exists():
            buf = bytearray()
            dur = 0.09
            for i in range(int(sr * dur)):
                t = i / sr
                freq = 320.0 + (t / dur) * 680.0
                env = math.sin(math.pi * (t / dur))
                val = int(15000 * env * math.sin(2 * math.pi * freq * t))
                buf.extend(struct.pack("<h", max(-32767, min(32767, val))))
            self._write_wav(self.builtin_files["Soft Bubble Pop"], buf, sr)

        if not self.builtin_files["Happy Arpeggio"].exists():
            buf = bytearray()
            for freq, dur in [(523.25, 0.065), (659.25, 0.065), (783.99, 0.13)]:
                for i in range(int(sr * dur)):
                    t = i / sr
                    env = math.exp(-t * 13.0)
                    val = int(13500 * env * math.sin(2 * math.pi * freq * t))
                    buf.extend(struct.pack("<h", max(-32767, min(32767, val))))
            self._write_wav(self.builtin_files["Happy Arpeggio"], buf, sr)

    def play_for_character(self, char_name, force_builtin=False):
        if not self.manager.config.get("sound_enabled", True):
            return
        vol = self.manager.config.get("sound_volume", 70) / 100.0
        self.audio_output.setVolume(vol)

        chosen_file = None
        if not force_builtin:
            char_sounds_dir = PETS_DIR / char_name / "sounds"
            if char_sounds_dir.exists():
                sound_files = [
                    p for p in char_sounds_dir.iterdir()
                    if p.suffix.lower() in [".wav", ".mp3", ".ogg"]
                ]
                if sound_files:
                    chosen_file = random.choice(sound_files)

        if not chosen_file:
            preset = self.manager.config.get("default_sfx", "Cute Chime")
            if preset == "Random Mix":
                chosen_file = random.choice(list(self.builtin_files.values()))
            else:
                chosen_file = self.builtin_files.get(preset, self.builtin_files["Cute Chime"])

        if chosen_file and chosen_file.exists():
            self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(str(chosen_file)))
            self.player.play()


class SpeechBubble(QWidget):
    """Maskotun başının üzerinde beliren kuyruklu ve özel font destekli konuşma balonu."""
    def __init__(self, accent_color="#39C5BB", mode="dark", font_css=None):
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.lbl_text = QLabel()
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_tail = QLabel("▼")
        self.lbl_tail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_text)
        layout.addWidget(self.lbl_tail)

        self.update_theme(accent_color, mode, font_css or BUILTIN_FONTS["Cute Rounded"])

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def update_theme(self, accent_color, mode="dark", font_css=None):
        bg = "rgba(24, 27, 38, 242)" if mode == "dark" else "rgba(255, 255, 255, 246)"
        fg = "#F2F4FA" if mode == "dark" else "#1E2230"
        family = font_css or BUILTIN_FONTS["Cute Rounded"]

        self.lbl_text.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 2px solid {accent_color};
                border-radius: 14px;
                padding: 7px 13px;
                font-family: {family};
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        self.lbl_tail.setStyleSheet(f"""
            QLabel {{
                color: {accent_color};
                font-size: 10px;
                margin-top: -3px;
                background: transparent;
            }}
        """)
        self.adjustSize()

    def show_message(self, text, pet_geometry, duration_ms=3400):
        self.lbl_text.setText(text)
        self.adjustSize()
        bx = pet_geometry.center().x() - (self.width() // 2)
        by = max(10, pet_geometry.top() - self.height() - 2)
        self.move(bx, by)
        self.show()
        self.hide_timer.start(duration_ms)


class CharacterManager:
    DEFAULT_QUOTES = [
        "Ehehe, hello there! ♡",
        "Pat pat~ ♪",
        "Staying hydrated? 💧",
        "You're doing great! ★",
        "Need a tiny stretch?",
        "♪ ~ ♫ ~ ♪",
        "Yay! That tickles~"
    ]

    def __init__(self):
        PETS_DIR.mkdir(parents=True, exist_ok=True)
        FONTS_DIR.mkdir(parents=True, exist_ok=True)
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_default_miku()
        self.config = self.load_config()
        self.custom_fonts = {}
        self.load_all_custom_fonts()

    def ensure_default_miku(self):
        miku_dir = PETS_DIR / "Hatsune Miku"
        if not miku_dir.exists() or not any(miku_dir.iterdir()):
            miku_dir.mkdir(parents=True, exist_ok=True)
            bundled_assets = Path(resource_path("assets"))
            if bundled_assets.exists():
                for img in bundled_assets.glob("*.png"):
                    shutil.copy2(img, miku_dir / img.name)

    def load_config(self):
        default_cfg = {
            "size": 128,
            "speed_mult": 1.0,
            "last_character": "Hatsune Miku",
            "bubbles_enabled": True,
            "custom_quotes": list(self.DEFAULT_QUOTES),
            "theme_preset": "Miku Teal (Dark)",
            "theme_mode": "dark",
            "accent_color": "#39C5BB",
            "bubble_font": "Cute Rounded",
            "app_icon_path": "",
            "sound_enabled": True,
            "sound_volume": 70,
            "default_sfx": "Cute Chime",
            "window_landing": True,
            "social_interactions": True,
            "restore_last_stage": True,
            "last_stage_chars": ["Hatsune Miku"],
            "stage_presets": {},
            "throw_physics": True,
            "ghost_mode": False,
            "follow_cursor": False,
            "floating_emotes": True,
            "hourly_chime": True,
            "day_night_routine": True,
            "music_reaction": True
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_app_icon(self):
        cfg_icon = self.config.get("app_icon_path", "")
        if cfg_icon and Path(cfg_icon).exists():
            return QIcon(cfg_icon)
        for cand in ["assets/app_icon.png", "assets/KomaStage.icns", "assets/shime1.png"]:
            p = Path(resource_path(cand))
            if p.exists():
                return QIcon(str(p))
        return QIcon()

    def set_custom_app_icon(self, source_path):
        src = Path(source_path)
        if not src.exists():
            return False, "Selected icon file does not exist."
        try:
            target = ICONS_DIR / f"custom_icon{src.suffix.lower()}"
            shutil.copy2(src, target)
            self.config["app_icon_path"] = str(target)
            self.save_config()
            return True, f"App icon updated to '{src.name}'!"
        except Exception as e:
            return False, f"Could not set icon: {str(e)}"

    def reset_app_icon(self):
        self.config["app_icon_path"] = ""
        self.save_config()

    def load_all_custom_fonts(self):
        self.custom_fonts.clear()
        if not FONTS_DIR.exists():
            return
        for font_file in sorted(FONTS_DIR.iterdir()):
            if font_file.suffix.lower() in [".ttf", ".otf"]:
                font_id = QFontDatabase.addApplicationFont(str(font_file))
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        family = families[0]
                        label = f"{family} (Custom)"
                        self.custom_fonts[label] = (family, font_file)

    def import_font(self, source_path):
        src = Path(source_path)
        if not src.exists() or src.suffix.lower() not in [".ttf", ".otf"]:
            return False, "Please select a valid .ttf or .otf font file.", None
        try:
            target = FONTS_DIR / src.name
            shutil.copy2(src, target)
            font_id = QFontDatabase.addApplicationFont(str(target))
            if font_id == -1:
                target.unlink(missing_ok=True)
                return False, "Could not load this font file.", None
            families = QFontDatabase.applicationFontFamilies(font_id)
            if not families:
                return False, "No font family found inside the file.", None
            self.load_all_custom_fonts()
            label = f"{families[0]} (Custom)"
            return True, f"Font '{families[0]}' added!", label
        except Exception as e:
            return False, f"Font import error: {str(e)}", None

    def delete_custom_font(self, label):
        if label in self.custom_fonts:
            _, file_path = self.custom_fonts[label]
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            self.load_all_custom_fonts()
            return True
        return False

    def get_active_font_css(self):
        selected = self.config.get("bubble_font", "Cute Rounded")
        if selected in BUILTIN_FONTS:
            return BUILTIN_FONTS[selected]
        if selected in self.custom_fonts:
            family, _ = self.custom_fonts[selected]
            return f'"{family}", sans-serif'
        return BUILTIN_FONTS["Cute Rounded"]

    def get_all_font_names(self):
        return list(BUILTIN_FONTS.keys()) + list(self.custom_fonts.keys())

    def get_characters(self):
        chars = []
        if PETS_DIR.exists():
            for d in sorted(PETS_DIR.iterdir()):
                if d.is_dir() and any(d.glob("*.png")):
                    chars.append(d.name)
        return chars

    def get_character_path(self, name):
        return PETS_DIR / name

    def create_custom_pet(self, name, walk_files, sit_files=None, drag_files=None, special_files=None, sound_file=None):
        clean_name = "".join(c for c in name.strip() if c.isalnum() or c in (" ", "-", "_")).strip()
        if not clean_name:
            return False, "Please enter a valid character name."
        if not walk_files:
            return False, "Please select at least 1 PNG image for the Walk animation."

        target_dir = PETS_DIR / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)

        def copy_slot(files, slot_names):
            if not files:
                return
            for idx, s_name in enumerate(slot_names):
                src_p = Path(files[idx % len(files)])
                if src_p.exists():
                    shutil.copy2(src_p, target_dir / s_name)

        copy_slot(walk_files, ["shime1.png", "shime2.png", "shime3.png"])
        copy_slot(sit_files or walk_files, ["shime11.png", "shime12.png", "shime15.png", "shime16.png"])
        copy_slot(drag_files or walk_files, ["shime5.png", "shime6.png", "shime4.png"])
        copy_slot(special_files or walk_files, ["shime42.png", "shime43.png", "shime52.png"])

        if sound_file and Path(sound_file).exists():
            snd_dir = target_dir / "sounds"
            snd_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sound_file, snd_dir / Path(sound_file).name)

        return True, f"Custom character '{clean_name}' created and added to your library!"

    def add_character_sound(self, char_name, sound_path):
        src = Path(sound_path)
        if not src.exists() or src.suffix.lower() not in [".wav", ".mp3", ".ogg"]:
            return False, "Please select a valid .wav, .mp3, or .ogg audio file."
        char_sounds = PETS_DIR / char_name / "sounds"
        char_sounds.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, char_sounds / src.name)
        return True, f"Sound '{src.name}' attached to {char_name}!"

    def get_character_sound_count(self, char_name):
        char_sounds = PETS_DIR / char_name / "sounds"
        if not char_sounds.exists():
            return 0
        return len([p for p in char_sounds.iterdir() if p.suffix.lower() in [".wav", ".mp3", ".ogg"]])

    def delete_character(self, name):
        if name == "Hatsune Miku":
            return False, "The default Hatsune Miku character cannot be deleted."
        target = PETS_DIR / name
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            return True, f"'{name}' has been removed."
        return False, "Character folder not found."

    def import_character(self, source_path):
        src = Path(source_path)
        temp_dir = None
        try:
            if src.is_file() and src.suffix.lower() == ".zip":
                temp_dir = Path(tempfile.mkdtemp())
                with zipfile.ZipFile(src, "r") as zf:
                    zf.extractall(temp_dir)
                search_root = temp_dir
                char_name = src.stem
            elif src.is_dir():
                search_root = src
                char_name = src.name
            else:
                return False, "Please select a valid folder or .zip file."

            sprite_dir = None
            for p in search_root.rglob("shime1.png"):
                if "__MACOSX" not in str(p):
                    sprite_dir = p.parent
                    break

            if not sprite_dir:
                png_dirs = {}
                for p in search_root.rglob("*.png"):
                    if "__MACOSX" not in str(p):
                        png_dirs[p.parent] = png_dirs.get(p.parent, 0) + 1
                if png_dirs:
                    sprite_dir = max(png_dirs, key=png_dirs.get)

            if not sprite_dir:
                return False, "No valid PNG character sprites found in the selected package."

            if sprite_dir.name.lower() in ["img", "images", "sprites"] and sprite_dir.parent != temp_dir:
                char_name = sprite_dir.parent.name

            target_dir = PETS_DIR / char_name
            target_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for png in sprite_dir.glob("*.png"):
                shutil.copy2(png, target_dir / png.name)
                copied += 1

            sounds_copied = 0
            for ext in ("*.wav", "*.mp3", "*.ogg"):
                for snd in search_root.rglob(ext):
                    if "__MACOSX" not in str(snd):
                        snd_target = target_dir / "sounds"
                        snd_target.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(snd, snd_target / snd.name)
                        sounds_copied += 1

            sound_note = f" + {sounds_copied} sound(s)" if sounds_copied > 0 else ""
            return True, f"'{char_name}' imported successfully ({copied} frames{sound_note})!"
        except Exception as e:
            return False, f"Import error: {str(e)}"
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


class DesktopPet(QWidget):
    SOCIAL_GREETINGS = [
        ("Hi there! ♡", "Hello! ♪"),
        ("Let's hang out! ★", "Yay! ~"),
        ("Nice weather today~", "Totally! ♡"),
        ("♪ ~ ♫ ~ ♪", "♫ ~ ♪ ~ ♫"),
        ("Pat pat! ☆", "Ehehe~ ♡")
    ]

    def __init__(self, char_name, char_dir, size_px=128, speed_mult=1.0, app_controller=None):
        super().__init__()
        self.char_name = char_name
        self.char_dir = Path(char_dir)
        self.size_px = size_px
        self.speed_mult = speed_mult
        self.app_controller = app_controller

        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.size_px, self.size_px)

        self.label = QLabel(self)
        self.label.setFixedSize(self.size_px, self.size_px)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        accent = "#39C5BB"
        mode = "dark"
        font_css = BUILTIN_FONTS["Cute Rounded"]
        if self.app_controller:
            accent = self.app_controller.manager.config.get("accent_color", "#39C5BB")
            mode = self.app_controller.manager.config.get("theme_mode", "dark")
            font_css = self.app_controller.manager.get_active_font_css()
        self.bubble = SpeechBubble(accent, mode, font_css)

        self.load_all_animations()

        self.state = "walk"
        self.frame_index = 0
        self.direction = random.choice([-1, 1])
        self.is_dragging = False
        self.is_paused = False
        self.focus_mode = False
        self.drag_offset = QPoint()
        self.last_drag_pos = QPoint()
        self.vx = 0.0
        self.vy = 0.0
        self.social_cooldown = 0
        self.active_ledge = None
        self.laser_pounce_cooldown = 0
        self.active_emotes = []

        screen = QApplication.primaryScreen().availableGeometry()
        self.x_pos = random.randint(100, max(150, screen.width() - 200))
        self.y_pos = screen.bottom() - self.size_px
        self.move(self.x_pos, self.y_pos)

        self.update_animation()

        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self.update_physics)
        self.move_timer.start(30)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(160)

        self.ai_timer = QTimer(self)
        self.ai_timer.timeout.connect(self.decide_next_action)
        self.ai_timer.start(4500)

        self.emote_timer = QTimer(self)
        self.emote_timer.timeout.connect(self.emit_ambient_emote)
        self.emote_timer.start(2600)

    def spawn_emote(self, symbol, color_hex=None):
        if self.app_controller:
            if self.app_controller.pets_hidden:
                return
            if not self.app_controller.manager.config.get("floating_emotes", True):
                return
            if not color_hex:
                color_hex = self.app_controller.manager.config.get("accent_color", "#39C5BB")
        color_hex = color_hex or "#39C5BB"

        cx = self.frameGeometry().center().x() + random.randint(-12, 12)
        cy = max(12, self.frameGeometry().top() + 8)
        emote = FloatingEmoteOverlay(symbol, color_hex, cx, cy)
        self.active_emotes.append(emote)
        emote.destroyed.connect(lambda _, e=emote: self.active_emotes.remove(e) if e in self.active_emotes else None)

    def emit_ambient_emote(self):
        if self.is_dragging or self.is_paused:
            return
        if self.state == "sleep_box":
            self.spawn_emote("Zzz...", "#9FA8DA")
        elif self.state in ["leek_walk", "mini_miku"]:
            self.spawn_emote(random.choice(["♪", "♫"]))
        elif self.focus_mode and random.random() < 0.45:
            self.spawn_emote("★")

    def apply_ghost_mode(self, enabled):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if self.isVisible():
            self.hide()
            self.show()

    def say(self, message, duration_ms=3400, force=False):
        if not force and self.app_controller:
            if self.app_controller.pets_hidden:
                return
            if not self.app_controller.manager.config.get("bubbles_enabled", True):
                return
        self.bubble.show_message(message, self.frameGeometry(), duration_ms)

    def load_all_animations(self):
        walk = self.load_frames(["shime1.png", "shime2.png", "shime3.png"])
        if not walk:
            any_pngs = [p.name for p in sorted(self.char_dir.glob("*.png"))[:4]]
            walk = self.load_frames(any_pngs)

        sit = self.load_frames(["shime11.png", "shime12.png", "shime15.png", "shime16.png"]) or walk

        self.animations = {
            "walk": walk,
            "run": self.load_frames(["shime49.png", "shime50.png", "shime51.png"]) or walk,
            "leek_walk": self.load_frames(["shime42.png", "shime43.png", "shime44.png", "shime45.png"]) or walk,
            "sit": sit,
            "mini_miku": self.load_frames(["shime52.png", "shime53.png", "shime54.png", "shime55.png"]) or sit,
            "sleep_box": self.load_frames(["shime20.png", "shime21.png"]) or sit,
            "climb_wall": self.load_frames(["shime30.png", "shime31.png", "shime32.png"]) or walk,
            "climb_ceiling": self.load_frames(["shime22.png", "shime23.png", "shime24.png", "shime25.png"]) or walk,
            "drag": self.load_frames(["shime5.png", "shime6.png", "shime7.png", "shime8.png", "shime10.png"]) or walk,
            "fall": self.load_frames(["shime4.png", "shime9.png"]) or walk
        }

    def load_frames(self, filenames):
        frames = []
        for fname in filenames:
            full_path = self.char_dir / fname
            if full_path.exists():
                pix = QPixmap(str(full_path))
                if not pix.isNull():
                    pix.setDevicePixelRatio(1.0)
                    pix = pix.scaled(
                        self.size_px, self.size_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    frames.append(pix)
        return frames

    def set_size(self, new_size):
        self.size_px = new_size
        self.setFixedSize(self.size_px, self.size_px)
        self.label.setFixedSize(self.size_px, self.size_px)
        screen = QApplication.primaryScreen().availableGeometry()
        if self.y_pos > screen.bottom() - self.size_px:
            self.y_pos = screen.bottom() - self.size_px
            self.move(self.x_pos, self.y_pos)
        self.load_all_animations()
        self.update_animation()

    def set_speed(self, new_mult):
        self.speed_mult = new_mult

    def set_state(self, new_state):
        if self.state != new_state:
            self.state = new_state
            self.frame_index = 0
            self.update_animation()

    def set_focus_mode(self, active):
        self.focus_mode = active
        if active:
            self.set_state("sit")
            self.spawn_emote("♡", "#FF7EB6")
            self.say("Focus time! Cheering for you~ ♡", force=True)
        else:
            self.set_state("leek_walk")
            self.spawn_emote("♪")
            self.say("Time's up! Take a cozy break! ♪", 5000, force=True)
            if self.app_controller:
                self.app_controller.sound_engine.play_for_character(self.char_name)

    def decide_next_action(self):
        if self.is_dragging or self.is_paused or self.state == "fall":
            return
        if self.app_controller:
            if self.app_controller.laser_active or self.app_controller.manager.config.get("follow_cursor", False):
                return
            if self.app_controller.music_dancing:
                self.set_state(random.choice(["leek_walk", "mini_miku"]))
                return
        if self.focus_mode:
            self.set_state(random.choice(["sit", "mini_miku"]))
            return
        if self.state == "climb_ceiling":
            if random.random() < 0.45:
                self.vx = 0.0
                self.vy = 2.0
                self.set_state("fall")
            return

        if self.active_ledge is not None and random.random() < 0.25:
            self.active_ledge = None
            self.y_pos += 16
            self.vx = 0.0
            self.vy = 2.0
            self.set_state("fall")
            return

        choices = ["walk", "walk", "run", "leek_walk", "sit", "mini_miku", "sleep_box", "climb_wall"]
        if self.app_controller and self.app_controller.manager.config.get("day_night_routine", True):
            period = self.app_controller.get_time_period()
            if period == "night":
                choices = ["sleep_box", "sleep_box", "sleep_box", "sit", "sit", "walk"]
            elif period == "morning":
                choices = ["walk", "run", "run", "leek_walk", "leek_walk", "mini_miku", "climb_wall"]

        chosen = random.choice(choices)
        if chosen in ["walk", "run", "leek_walk"]:
            self.direction = random.choice([-1, 1])
        elif chosen == "climb_wall":
            screen = QApplication.primaryScreen().availableGeometry()
            self.direction = -1 if self.x_pos < screen.width() // 2 else 1
        self.set_state(chosen)

    def get_current_surface_bounds(self, screen):
        win_enabled = True
        if self.app_controller:
            win_enabled = self.app_controller.manager.config.get("window_landing", True)

        if win_enabled and self.active_ledge and self.app_controller:
            lx, rx, ly = self.active_ledge
            still_exists = any(
                abs(w_ly - ly) <= 14 and abs(w_lx - lx) <= 40
                for (w_lx, w_rx, w_ly) in self.app_controller.window_tracker.ledges
            )
            center_x = self.x_pos + (self.size_px // 2)
            if still_exists and (lx - 10) <= center_x <= (rx + 10):
                return lx, rx - self.size_px, ly - self.size_px
            else:
                self.active_ledge = None

        return screen.left(), screen.right() - self.size_px, screen.bottom() - self.size_px

    def check_social_interaction(self):
        if not self.app_controller or self.social_cooldown > 0 or self.app_controller.pets_hidden:
            return
        if self.app_controller.laser_active or self.app_controller.manager.config.get("follow_cursor", False):
            return
        if not self.app_controller.manager.config.get("social_interactions", True):
            return
        if self.state not in ["walk", "run", "leek_walk", "sit"]:
            return

        for other in self.app_controller.pets:
            if other is self or other.is_dragging or other.is_paused or other.social_cooldown > 0:
                continue
            if abs(self.y_pos - other.y_pos) < 35 and abs(self.x_pos - other.x_pos) < int(self.size_px * 0.85):
                self.social_cooldown = 450
                other.social_cooldown = 450

                self.direction = 1 if other.x_pos > self.x_pos else -1
                other.direction = -self.direction
                self.set_state("sit")
                other.set_state("mini_miku")

                g1, g2 = random.choice(self.SOCIAL_GREETINGS)
                self.spawn_emote("♡", "#FF7EB6")
                self.say(g1, 2800)
                QTimer.singleShot(450, lambda o=other, msg=g2: (o.spawn_emote("♪"), o.say(msg, 2800)))
                break

    def update_cursor_or_laser_behavior(self, screen, left_bound, right_bound, ground_y):
        cursor = QCursor.pos()
        center_x = self.x_pos + (self.size_px // 2)
        dx = cursor.x() - center_x
        is_laser = self.app_controller.laser_active

        if is_laser:
            if abs(dx) > 22:
                self.direction = 1 if dx > 0 else -1
                self.set_state("run")
                speed = max(2, int(round(9 * self.speed_mult)))
                self.x_pos = max(left_bound, min(right_bound, self.x_pos + speed * self.direction))
                self.move(self.x_pos, self.y_pos)
            else:
                self.set_state("mini_miku")
                if self.laser_pounce_cooldown <= 0 and cursor.y() < self.y_pos + 20:
                    self.laser_pounce_cooldown = 45
                    self.active_ledge = None
                    self.vx = (1 if dx >= 0 else -1) * 3.5
                    self.vy = -14.0
                    self.y_pos -= 12
                    self.spawn_emote("!", "#FF5252")
                    self.set_state("fall")
        else:
            if abs(dx) > int(self.size_px * 0.55):
                self.direction = 1 if dx > 0 else -1
                self.set_state("run" if abs(dx) > 260 else "walk")
                base_spd = 6 if abs(dx) > 260 else 3
                speed = max(1, int(round(base_spd * self.speed_mult)))
                self.x_pos = max(left_bound, min(right_bound, self.x_pos + speed * self.direction))
                self.move(self.x_pos, self.y_pos)
            else:
                self.direction = 1 if dx >= 0 else -1
                self.set_state("sit")

    def update_physics(self):
        if self.social_cooldown > 0:
            self.social_cooldown -= 1
        if self.laser_pounce_cooldown > 0:
            self.laser_pounce_cooldown -= 1

        if self.bubble.isVisible():
            bx = self.frameGeometry().center().x() - (self.bubble.width() // 2)
            by = max(10, self.frameGeometry().top() - self.bubble.height() - 2)
            self.bubble.move(bx, by)

        if self.is_dragging or self.is_paused:
            return

        screen = QApplication.primaryScreen().availableGeometry()
        left_bound, right_bound, ground_y = self.get_current_surface_bounds(screen)
        ceiling_y = screen.top()

        if self.state not in ["climb_wall", "climb_ceiling"] and (self.y_pos < ground_y or self.vy < 0):
            self.set_state("fall")
            throw_on = self.app_controller.manager.config.get("throw_physics", True) if self.app_controller else True

            if throw_on:
                self.vy = min(22.0, self.vy + 1.35)
                self.vx *= 0.97
                self.x_pos = int(round(self.x_pos + self.vx))
                next_y = int(round(self.y_pos + self.vy))

                if self.x_pos <= screen.left():
                    self.x_pos = screen.left()
                    self.vx = abs(self.vx) * 0.65
                    self.direction = 1
                elif self.x_pos >= screen.right() - self.size_px:
                    self.x_pos = screen.right() - self.size_px
                    self.vx = -abs(self.vx) * 0.65
                    self.direction = -1

                if next_y <= ceiling_y:
                    next_y = ceiling_y
                    self.vy = abs(self.vy) * 0.4
            else:
                next_y = min(self.y_pos + 11, ground_y)

            win_enabled = self.app_controller.manager.config.get("window_landing", True) if self.app_controller else True
            if win_enabled and self.app_controller and self.vy >= 0:
                foot_old = self.y_pos + self.size_px
                foot_new = next_y + self.size_px
                center_x = self.x_pos + (self.size_px // 2)
                for (lx, rx, ly) in self.app_controller.window_tracker.ledges:
                    if (lx + 15) <= center_x <= (rx - 15) and foot_old <= ly <= foot_new:
                        self.active_ledge = (lx, rx, ly)
                        self.y_pos = ly - self.size_px
                        self.vx = 0.0
                        self.vy = 0.0
                        self.move(self.x_pos, self.y_pos)
                        self.set_state("sit")
                        return

            if next_y >= ground_y:
                self.y_pos = ground_y
                self.vx = 0.0
                self.vy = 0.0
                self.move(self.x_pos, self.y_pos)
                self.set_state("sit")
            else:
                self.y_pos = next_y
                self.move(self.x_pos, self.y_pos)
            return

        if self.app_controller and not self.focus_mode:
            if self.app_controller.laser_active or self.app_controller.manager.config.get("follow_cursor", False):
                if self.state in ["climb_wall", "climb_ceiling"]:
                    self.set_state("fall")
                    return
                self.update_cursor_or_laser_behavior(screen, left_bound, right_bound, ground_y)
                return

        if self.state in ["walk", "run", "leek_walk"]:
            base_speed = 7 if self.state == "run" else 3
            speed = max(1, int(round(base_speed * self.speed_mult)))
            self.x_pos += speed * self.direction
            if self.x_pos <= left_bound:
                self.x_pos = left_bound
                self.direction = 1
            elif self.x_pos >= right_bound:
                self.x_pos = right_bound
                self.direction = -1
            self.move(self.x_pos, self.y_pos)
            self.check_social_interaction()

        elif self.state == "climb_wall":
            self.active_ledge = None
            target_x = screen.left() if self.direction == -1 else screen.right() - self.size_px
            climb_speed = max(1, int(round(4 * self.speed_mult)))
            if abs(self.x_pos - target_x) > 5:
                self.x_pos += 5 * self.direction
            else:
                self.x_pos = target_x
                self.y_pos -= climb_speed
                if self.y_pos <= ceiling_y:
                    self.y_pos = ceiling_y
                    self.direction = 1 if self.x_pos == screen.left() else -1
                    self.set_state("climb_ceiling")
            self.move(self.x_pos, self.y_pos)

        elif self.state == "climb_ceiling":
            speed = max(1, int(round(3 * self.speed_mult)))
            self.x_pos += speed * self.direction
            if self.x_pos <= screen.left():
                self.x_pos = screen.left()
                self.direction = 1
            elif self.x_pos + self.size_px >= screen.right():
                self.x_pos = screen.right() - self.size_px
                self.direction = -1
            self.move(self.x_pos, self.y_pos)

    def update_animation(self):
        frames = self.animations.get(self.state, [])
        if not frames:
            return
        self.frame_index = (self.frame_index + 1) % len(frames)
        current_pix = frames[self.frame_index]
        needs_flip = (
            self.state in ["walk", "run", "leek_walk", "climb_ceiling", "climb_wall", "sit", "mini_miku"]
            and self.direction == 1
        )
        if needs_flip:
            current_pix = current_pix.transformed(QTransform().scale(-1, 1))
        self.label.setPixmap(current_pix)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.active_ledge = None
            self.vx = 0.0
            self.vy = -12.0
            self.y_pos = max(0, self.y_pos - 25)
            self.move(self.x_pos, self.y_pos)
            self.set_state("leek_walk")
            self.spawn_emote("♡", "#FF7EB6")
            quotes = CharacterManager.DEFAULT_QUOTES
            if self.app_controller:
                quotes = self.app_controller.manager.config.get("custom_quotes", quotes) or quotes
                self.app_controller.sound_engine.play_for_character(self.char_name)
            self.say(random.choice(quotes))
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.active_ledge = None
            self.vx = 0.0
            self.vy = 0.0
            self.set_state("drag")
            gpos = event.globalPosition().toPoint()
            self.drag_offset = gpos - self.frameGeometry().topLeft()
            self.last_drag_pos = gpos
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            gpos = event.globalPosition().toPoint()
            delta = gpos - self.last_drag_pos
            self.vx = max(-32.0, min(32.0, delta.x() * 0.85))
            self.vy = max(-32.0, min(32.0, delta.y() * 0.85))
            self.last_drag_pos = gpos

            new_pos = gpos - self.drag_offset
            self.x_pos = new_pos.x()
            self.y_pos = new_pos.y()
            self.move(self.x_pos, self.y_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            throw_on = self.app_controller.manager.config.get("throw_physics", True) if self.app_controller else True
            if not throw_on:
                self.vx = 0.0
                self.vy = 4.0
            else:
                if abs(self.vx) > 2:
                    self.direction = 1 if self.vx > 0 else -1
                if abs(self.vx) > 10 or self.vy < -10:
                    self.spawn_emote("!", "#FFB74D")
                if self.vy == 0:
                    self.vy = 2.0
            self.set_state("fall")
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        actions_menu = menu.addMenu("Select Action")
        for label_text, st in [
            ("Walk", "walk"),
            ("Run", "run"),
            ("Special Walk", "leek_walk"),
            ("Sit", "sit"),
            ("Mini Mode", "mini_miku"),
            ("Hide in Box", "sleep_box"),
            ("Climb Wall", "climb_wall")
        ]:
            act = QAction(label_text, self)
            act.triggered.connect(lambda checked, s=st: self.set_state(s))
            actions_menu.addAction(act)

        if self.app_controller:
            panel_act = QAction("Open Control Panel", self)
            panel_act.triggered.connect(self.app_controller.show_panel)
            menu.addAction(panel_act)

            spawn_act = QAction(f"Spawn Another {self.char_name} (+1)", self)
            spawn_act.triggered.connect(lambda: self.app_controller.spawn_pet(self.char_name))
            menu.addAction(spawn_act)

            menu.addSeparator()
            follow_act = QAction("Follow Cursor", self)
            follow_act.setCheckable(True)
            follow_act.setChecked(self.app_controller.manager.config.get("follow_cursor", False))
            follow_act.triggered.connect(self.app_controller.set_follow_cursor)
            menu.addAction(follow_act)

            laser_act = QAction("Laser Pointer Toy", self)
            laser_act.setCheckable(True)
            laser_act.setChecked(self.app_controller.laser_active)
            laser_act.triggered.connect(self.app_controller.set_laser_toy)
            menu.addAction(laser_act)

            hide_act = QAction("Hide All Mascots (Boss Key)", self)
            hide_act.triggered.connect(self.app_controller.toggle_hide_all)
            menu.addAction(hide_act)

        menu.addSeparator()
        pause_action = QAction("Resume" if self.is_paused else "Pause", self)
        pause_action.triggered.connect(self.toggle_pause)

        remove_action = QAction("Dismiss Mascot", self)
        remove_action.triggered.connect(self.remove_self)

        quit_action = QAction("Quit Application", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(pause_action)
        menu.addAction(remove_action)
        menu.addAction(quit_action)
        menu.exec(event.globalPosition().toPoint())

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self.set_state("sit")

    def remove_self(self):
        self.bubble.close()
        for em in list(self.active_emotes):
            em.close()
        if self.app_controller:
            self.app_controller.remove_pet(self)
        self.close()


class ControlPanel(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("KomaStage")
        self.setMinimumSize(580, 740)

        self.creator_slots = {"walk": [], "sit": [], "drag": [], "special": [], "sound": ""}

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("KomaStage")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Custom Shimeji Engine & Desktop Companion Studio")
        subtitle.setObjectName("SubLabel")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.build_characters_tab()
        self.build_creator_tab()
        self.build_stage_tab()
        self.build_focus_tab()
        self.build_theme_tab()

        bottom_row = QHBoxLayout()
        self.lbl_active = QLabel("Active Mascots: 1")
        self.lbl_active.setObjectName("SubLabel")

        self.btn_boss_hide = QPushButton("Hide All (Boss Key)")
        self.btn_boss_hide.setObjectName("SecondaryBtn")
        self.btn_boss_hide.clicked.connect(self.controller.toggle_hide_all)

        btn_open_dir = QPushButton("Open Folder")
        btn_open_dir.setObjectName("SecondaryBtn")
        btn_open_dir.clicked.connect(self.open_pets_folder)

        btn_clear = QPushButton("Clear All")
        btn_clear.setObjectName("DangerBtn")
        btn_clear.clicked.connect(self.controller.clear_all_pets)

        bottom_row.addWidget(self.lbl_active)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_boss_hide)
        bottom_row.addWidget(btn_open_dir)
        bottom_row.addWidget(btn_clear)
        main_layout.addLayout(bottom_row)

        self.apply_styles()
        self.refresh_character_list()
        self.refresh_stage_presets()

    def build_characters_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 14, 12, 12)

        top_bar = QHBoxLayout()
        lbl = QLabel("Character Library")
        lbl.setObjectName("SectionTitle")

        btn_add_zip = QPushButton("+ Add ZIP")
        btn_add_zip.setObjectName("SecondaryBtn")
        btn_add_zip.clicked.connect(self.import_zip)

        btn_add_dir = QPushButton("+ Add Folder")
        btn_add_dir.setObjectName("SecondaryBtn")
        btn_add_dir.clicked.connect(self.import_folder)

        btn_del = QPushButton("Delete")
        btn_del.setObjectName("DangerBtn")
        btn_del.clicked.connect(self.delete_selected)

        top_bar.addWidget(lbl)
        top_bar.addStretch()
        top_bar.addWidget(btn_add_zip)
        top_bar.addWidget(btn_add_dir)
        top_bar.addWidget(btn_del)
        layout.addLayout(top_bar)

        self.char_list = QListWidget()
        self.char_list.setIconSize(QSize(48, 48))
        self.char_list.setSpacing(4)
        self.char_list.currentRowChanged.connect(self.update_sound_badge)
        layout.addWidget(self.char_list)

        sound_bar = QHBoxLayout()
        self.lbl_char_sounds = QLabel("Voice/SFX: Using Default SFX Preset")
        self.lbl_char_sounds.setObjectName("SubLabel")

        btn_add_snd = QPushButton("+ Add Voice/SFX (.wav/.mp3)")
        btn_add_snd.setObjectName("SecondaryBtn")
        btn_add_snd.clicked.connect(self.import_sound_for_selected)

        sound_bar.addWidget(self.lbl_char_sounds)
        sound_bar.addStretch()
        sound_bar.addWidget(btn_add_snd)
        layout.addLayout(sound_bar)

        action_bar = QHBoxLayout()
        btn_spawn = QPushButton("Summon Selected (+1)")
        btn_spawn.setObjectName("PrimaryBtn")
        btn_spawn.clicked.connect(self.spawn_selected)

        btn_replace = QPushButton("Replace Active")
        btn_replace.setObjectName("SecondaryBtn")
        btn_replace.clicked.connect(self.replace_with_selected)

        action_bar.addWidget(btn_spawn)
        action_bar.addWidget(btn_replace)
        layout.addLayout(action_bar)

        self.tabs.addTab(tab, "Characters")

    def build_creator_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 14, 12, 12)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        lbl_title = QLabel("Custom Pet Creator (From PNGs)")
        lbl_title.setObjectName("SectionTitle")
        lbl_desc = QLabel(
            "Build your own desktop companion in seconds using transparent PNG images. "
            "Only Walk frames are required; other animations will fall back automatically."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("SubLabel")
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Mascot Name:"))
        self.creator_name_input = QLineEdit()
        self.creator_name_input.setPlaceholderText("e.g., Mini Neko, Cyber Bunny...")
        name_row.addWidget(self.creator_name_input)
        card_layout.addLayout(name_row)

        self.creator_slot_labels = {}
        slot_defs = [
            ("walk", "Walk Frames (Required):", "Select 1-3 PNGs..."),
            ("sit", "Sit / Idle Frames (Optional):", "Select 1-4 PNGs..."),
            ("drag", "Drag / Fall Frames (Optional):", "Select 1-3 PNGs..."),
            ("special", "Special / Dance Frames (Optional):", "Select 1-3 PNGs...")
        ]
        for key, title_txt, btn_txt in slot_defs:
            row = QHBoxLayout()
            lbl_s = QLabel(title_txt)
            status_lbl = QLabel("None selected")
            status_lbl.setObjectName("SubLabel")
            self.creator_slot_labels[key] = status_lbl

            btn_pick = QPushButton(btn_txt)
            btn_pick.setObjectName("SecondaryBtn")
            btn_pick.clicked.connect(lambda _, k=key: self.pick_creator_images(k))

            row.addWidget(lbl_s)
            row.addStretch()
            row.addWidget(status_lbl)
            row.addWidget(btn_pick)
            card_layout.addLayout(row)

        snd_row = QHBoxLayout()
        snd_row.addWidget(QLabel("Custom Voice/SFX (Optional):"))
        self.lbl_creator_snd = QLabel("Default SFX")
        self.lbl_creator_snd.setObjectName("SubLabel")
        btn_pick_snd = QPushButton("Select Audio...")
        btn_pick_snd.setObjectName("SecondaryBtn")
        btn_pick_snd.clicked.connect(self.pick_creator_sound)
        snd_row.addStretch()
        snd_row.addWidget(self.lbl_creator_snd)
        snd_row.addWidget(btn_pick_snd)
        card_layout.addLayout(snd_row)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset Form")
        btn_reset.setObjectName("SecondaryBtn")
        btn_reset.clicked.connect(self.reset_creator_form)

        btn_create = QPushButton("Create & Summon Mascot")
        btn_create.setObjectName("PrimaryBtn")
        btn_create.clicked.connect(self.submit_custom_pet)

        btn_row.addWidget(btn_reset)
        btn_row.addWidget(btn_create)
        card_layout.addLayout(btn_row)

        layout.addWidget(card)
        layout.addStretch()
        self.tabs.addTab(tab, "Pet Creator")

    def pick_creator_images(self, slot_key):
        paths, _ = QFileDialog.getOpenFileNames(
            self, f"Select PNG Images for {slot_key.title()}", str(Path.home()), "PNG Images (*.png)"
        )
        if paths:
            self.creator_slots[slot_key] = paths
            self.creator_slot_labels[slot_key].setText(f"{len(paths)} PNG(s) ready")

    def pick_creator_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Custom Sound", str(Path.home()), "Audio Files (*.wav *.mp3 *.ogg)"
        )
        if path:
            self.creator_slots["sound"] = path
            self.lbl_creator_snd.setText(Path(path).name)

    def reset_creator_form(self):
        self.creator_name_input.clear()
        self.creator_slots = {"walk": [], "sit": [], "drag": [], "special": [], "sound": ""}
        for lbl in self.creator_slot_labels.values():
            lbl.setText("None selected")
        self.lbl_creator_snd.setText("Default SFX")

    def submit_custom_pet(self):
        name = self.creator_name_input.text().strip()
        ok, msg = self.controller.manager.create_custom_pet(
            name=name,
            walk_files=self.creator_slots["walk"],
            sit_files=self.creator_slots["sit"],
            drag_files=self.creator_slots["drag"],
            special_files=self.creator_slots["special"],
            sound_file=self.creator_slots["sound"]
        )
        if ok:
            clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
            self.refresh_character_list()
            self.controller.spawn_pet(clean_name)
            self.reset_creator_form()
            self.tabs.setCurrentIndex(0)
            QMessageBox.information(self, "Mascot Created", msg)
        else:
            QMessageBox.warning(self, "Missing Info", msg)

    def build_stage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 8, 12, 8)

        preset_card = QFrame()
        preset_card.setObjectName("Card")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setSpacing(4)

        preset_top = QHBoxLayout()
        lbl_st = QLabel("Stage Presets & Startup")
        lbl_st.setObjectName("SectionTitle")

        self.chk_restore_stage = QCheckBox("Restore Last Stage on Launch")
        self.chk_restore_stage.setChecked(self.controller.manager.config.get("restore_last_stage", True))
        self.chk_restore_stage.toggled.connect(self.on_restore_stage_toggled)

        preset_top.addWidget(lbl_st)
        preset_top.addStretch()
        preset_top.addWidget(self.chk_restore_stage)
        preset_layout.addLayout(preset_top)

        save_row = QHBoxLayout()
        self.input_stage_name = QLineEdit()
        self.input_stage_name.setPlaceholderText("Scene name (e.g., Study Squad)...")
        btn_save_stage = QPushButton("Save Current Stage")
        btn_save_stage.setObjectName("PrimaryBtn")
        btn_save_stage.clicked.connect(self.save_current_stage_preset)
        save_row.addWidget(self.input_stage_name)
        save_row.addWidget(btn_save_stage)
        preset_layout.addLayout(save_row)

        load_row = QHBoxLayout()
        self.stage_preset_combo = QComboBox()
        btn_load_stage = QPushButton("Load Scene")
        btn_load_stage.setObjectName("SecondaryBtn")
        btn_load_stage.clicked.connect(self.load_selected_stage_preset)

        btn_del_stage = QPushButton("Delete")
        btn_del_stage.setObjectName("DangerBtn")
        btn_del_stage.clicked.connect(self.delete_selected_stage_preset)

        load_row.addWidget(self.stage_preset_combo, 1)
        load_row.addWidget(btn_load_stage)
        load_row.addWidget(btn_del_stage)
        preset_layout.addLayout(load_row)
        layout.addWidget(preset_card)

        phys_card = QFrame()
        phys_card.setObjectName("Card")
        phys_layout = QVBoxLayout(phys_card)
        phys_layout.setSpacing(4)

        size_row = QHBoxLayout()
        self.lbl_size = QLabel(f"Mascot Size: {self.controller.manager.config['size']} px")
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(64, 256)
        self.slider_size.setValue(self.controller.manager.config['size'])
        self.slider_size.valueChanged.connect(self.on_size_changed)
        size_row.addWidget(self.lbl_size)
        size_row.addWidget(self.slider_size)
        phys_layout.addLayout(size_row)

        speed_row = QHBoxLayout()
        speed_pct = int(self.controller.manager.config['speed_mult'] * 100)
        self.lbl_speed = QLabel(f"Movement Speed: {speed_pct}%")
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 250)
        self.slider_speed.setValue(speed_pct)
        self.slider_speed.valueChanged.connect(self.on_speed_changed)
        speed_row.addWidget(self.lbl_speed)
        speed_row.addWidget(self.slider_speed)
        phys_layout.addLayout(speed_row)

        interact_row1 = QHBoxLayout()
        self.chk_windows = QCheckBox("Sit & Walk on App Windows")
        self.chk_windows.setChecked(self.controller.manager.config.get("window_landing", True))
        self.chk_windows.toggled.connect(self.on_window_landing_toggled)

        self.chk_social = QCheckBox("Mascot Greetings")
        self.chk_social.setChecked(self.controller.manager.config.get("social_interactions", True))
        self.chk_social.toggled.connect(self.on_social_toggled)

        interact_row1.addWidget(self.chk_windows)
        interact_row1.addWidget(self.chk_social)
        phys_layout.addLayout(interact_row1)

        interact_row2 = QHBoxLayout()
        self.chk_throw = QCheckBox("Throw Momentum & Bounce")
        self.chk_throw.setChecked(self.controller.manager.config.get("throw_physics", True))
        self.chk_throw.toggled.connect(self.on_throw_toggled)

        self.chk_ghost = QCheckBox("Ghost Mode (Click-Through)")
        self.chk_ghost.setChecked(self.controller.manager.config.get("ghost_mode", False))
        self.chk_ghost.toggled.connect(self.on_ghost_toggled)

        interact_row2.addWidget(self.chk_throw)
        interact_row2.addWidget(self.chk_ghost)
        phys_layout.addLayout(interact_row2)

        interact_row3 = QHBoxLayout()
        self.chk_follow_cursor = QCheckBox("Follow Mouse Cursor")
        self.chk_follow_cursor.setChecked(self.controller.manager.config.get("follow_cursor", False))
        self.chk_follow_cursor.toggled.connect(self.controller.set_follow_cursor)

        self.chk_laser_toy = QCheckBox("Red Laser Pointer Toy")
        self.chk_laser_toy.setChecked(False)
        self.chk_laser_toy.toggled.connect(self.controller.set_laser_toy)

        interact_row3.addWidget(self.chk_follow_cursor)
        interact_row3.addWidget(self.chk_laser_toy)
        phys_layout.addLayout(interact_row3)

        interact_row4 = QHBoxLayout()
        self.chk_music_react = QCheckBox("Dance to Music / System Audio")
        self.chk_music_react.setChecked(self.controller.manager.config.get("music_reaction", True))
        self.chk_music_react.toggled.connect(self.on_music_react_toggled)

        btn_test_dance = QPushButton("Test Music Dance")
        btn_test_dance.setObjectName("SecondaryBtn")
        btn_test_dance.clicked.connect(self.controller.trigger_music_dance_preview)

        interact_row4.addWidget(self.chk_music_react)
        interact_row4.addStretch()
        interact_row4.addWidget(btn_test_dance)
        phys_layout.addLayout(interact_row4)
        layout.addWidget(phys_card)

        audio_card = QFrame()
        audio_card.setObjectName("Card")
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setSpacing(4)

        audio_top = QHBoxLayout()
        self.chk_sound = QCheckBox("Sound Effects")
        self.chk_sound.setChecked(self.controller.manager.config.get("sound_enabled", True))
        self.chk_sound.toggled.connect(self.on_sound_toggled)

        self.sfx_combo = QComboBox()
        self.sfx_combo.addItems(DEFAULT_SFX_PRESETS)
        current_sfx = self.controller.manager.config.get("default_sfx", "Cute Chime")
        if current_sfx in DEFAULT_SFX_PRESETS:
            self.sfx_combo.setCurrentText(current_sfx)
        self.sfx_combo.currentTextChanged.connect(self.on_sfx_preset_changed)

        btn_test_snd = QPushButton("Test")
        btn_test_snd.setObjectName("SecondaryBtn")
        btn_test_snd.clicked.connect(self.test_builtin_sound)

        audio_top.addWidget(self.chk_sound)
        audio_top.addStretch()
        audio_top.addWidget(self.sfx_combo)
        audio_top.addWidget(btn_test_snd)
        audio_layout.addLayout(audio_top)

        vol_row = QHBoxLayout()
        vol_val = self.controller.manager.config.get("sound_volume", 70)
        self.lbl_vol = QLabel(f"Sound Volume: {vol_val}%")
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(vol_val)
        self.slider_vol.valueChanged.connect(self.on_volume_changed)
        vol_row.addWidget(self.lbl_vol)
        vol_row.addWidget(self.slider_vol)
        audio_layout.addLayout(vol_row)
        layout.addWidget(audio_card)

        bubble_card = QFrame()
        bubble_card.setObjectName("Card")
        bubble_layout = QVBoxLayout(bubble_card)
        bubble_layout.setSpacing(4)

        bubble_top_row = QHBoxLayout()
        self.chk_bubbles = QCheckBox("Enable Speech Bubbles")
        self.chk_bubbles.setChecked(self.controller.manager.config.get("bubbles_enabled", True))
        self.chk_bubbles.toggled.connect(self.on_bubbles_toggled)

        self.chk_emotes = QCheckBox("Floating Emotes (♡, ♪, Zzz)")
        self.chk_emotes.setChecked(self.controller.manager.config.get("floating_emotes", True))
        self.chk_emotes.toggled.connect(self.on_emotes_toggled)

        bubble_top_row.addWidget(self.chk_bubbles)
        bubble_top_row.addWidget(self.chk_emotes)
        bubble_layout.addLayout(bubble_top_row)

        self.quote_list = QListWidget()
        self.quote_list.setMaximumHeight(40)
        self.refresh_quotes_list()
        bubble_layout.addWidget(self.quote_list)

        quote_row = QHBoxLayout()
        self.input_quote = QLineEdit()
        self.input_quote.setPlaceholderText("Write something cute for your mascot...")
        btn_add_quote = QPushButton("Add")
        btn_add_quote.setObjectName("PrimaryBtn")
        btn_add_quote.clicked.connect(self.add_custom_quote)

        btn_del_quote = QPushButton("Remove")
        btn_del_quote.setObjectName("DangerBtn")
        btn_del_quote.clicked.connect(self.remove_selected_quote)

        quote_row.addWidget(self.input_quote)
        quote_row.addWidget(btn_add_quote)
        quote_row.addWidget(btn_del_quote)
        bubble_layout.addLayout(quote_row)

        layout.addWidget(bubble_card)
        self.tabs.addTab(tab, "Stage & Physics")

    def on_music_react_toggled(self, checked):
        self.controller.manager.config["music_reaction"] = checked
        self.controller.manager.save_config()
        if not checked:
            self.controller.music_dancing = False

    def on_emotes_toggled(self, checked):
        self.controller.manager.config["floating_emotes"] = checked
        self.controller.manager.save_config()
        if checked:
            for p in self.controller.pets:
                p.spawn_emote("♡", "#FF7EB6")

    def on_throw_toggled(self, checked):
        self.controller.manager.config["throw_physics"] = checked
        self.controller.manager.save_config()

    def on_ghost_toggled(self, checked):
        self.controller.set_ghost_mode(checked)

    def on_restore_stage_toggled(self, checked):
        self.controller.manager.config["restore_last_stage"] = checked
        self.controller.manager.save_config()

    def refresh_stage_presets(self):
        self.stage_preset_combo.clear()
        presets = self.controller.manager.config.get("stage_presets", {})
        if presets:
            self.stage_preset_combo.addItems(list(presets.keys()))
        else:
            self.stage_preset_combo.addItem("(No saved scenes yet)")

    def save_current_stage_preset(self):
        scene_name = self.input_stage_name.text().strip()
        if not scene_name:
            QMessageBox.warning(self, "Warning", "Please enter a name for this stage scene.")
            return
        if not self.controller.pets:
            QMessageBox.warning(self, "Warning", "Summon at least one mascot before saving a scene.")
            return

        presets = self.controller.manager.config.get("stage_presets", {})
        presets[scene_name] = {
            "characters": [p.char_name for p in self.controller.pets],
            "size": self.controller.manager.config["size"],
            "speed_mult": self.controller.manager.config["speed_mult"]
        }
        self.controller.manager.config["stage_presets"] = presets
        self.controller.manager.save_config()
        self.input_stage_name.clear()
        self.refresh_stage_presets()
        self.stage_preset_combo.setCurrentText(scene_name)
        QMessageBox.information(self, "Saved", f"Stage preset '{scene_name}' saved!")

    def load_selected_stage_preset(self):
        scene_name = self.stage_preset_combo.currentText()
        presets = self.controller.manager.config.get("stage_presets", {})
        if scene_name not in presets:
            return
        data = presets[scene_name]
        self.controller.clear_all_pets()

        new_size = data.get("size", 128)
        new_speed = data.get("speed_mult", 1.0)
        self.slider_size.setValue(new_size)
        self.slider_speed.setValue(int(new_speed * 100))

        available = self.controller.manager.get_characters()
        chars_to_spawn = [c for c in data.get("characters", []) if c in available]
        if not chars_to_spawn:
            chars_to_spawn = ["Hatsune Miku"]

        for c in chars_to_spawn:
            self.controller.spawn_pet(c)

    def delete_selected_stage_preset(self):
        scene_name = self.stage_preset_combo.currentText()
        presets = self.controller.manager.config.get("stage_presets", {})
        if scene_name in presets:
            del presets[scene_name]
            self.controller.manager.config["stage_presets"] = presets
            self.controller.manager.save_config()
            self.refresh_stage_presets()

    def build_focus_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        lbl_title = QLabel("Focus & Study Companion")
        lbl_title.setObjectName("SectionTitle")
        lbl_desc = QLabel(
            "When a focus session is active, your mascots sit calmly on your desktop "
            "and cheer you on when the timer finishes."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("SubLabel")
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)

        self.lbl_timer = QLabel("25:00")
        self.lbl_timer.setObjectName("TimerLabel")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_timer)

        ctrl_row = QHBoxLayout()
        self.focus_combo = QComboBox()
        self.focus_combo.addItems(["25 min (Pomodoro)", "45 min (Deep Work)", "5 min (Short Break)"])
        self.focus_combo.currentIndexChanged.connect(self.on_preset_changed)

        self.btn_focus = QPushButton("Start Focus")
        self.btn_focus.setObjectName("PrimaryBtn")
        self.btn_focus.clicked.connect(self.toggle_focus_timer)

        ctrl_row.addWidget(self.focus_combo)
        ctrl_row.addWidget(self.btn_focus)
        card_layout.addLayout(ctrl_row)
        layout.addWidget(card)

        chime_card = QFrame()
        chime_card.setObjectName("Card")
        chime_layout = QVBoxLayout(chime_card)
        chime_layout.setSpacing(6)

        lbl_chime_title = QLabel("Hourly Chime & Care Reminders")
        lbl_chime_title.setObjectName("SectionTitle")
        lbl_chime_desc = QLabel(
            "At the top of every hour (XX:00), a mascot announces the time with a gentle chime "
            "and reminds you to hydrate, stretch, or rest your eyes."
        )
        lbl_chime_desc.setWordWrap(True)
        lbl_chime_desc.setObjectName("SubLabel")

        chime_ctrl_row = QHBoxLayout()
        self.chk_hourly_chime = QCheckBox("Enable Hourly Chime & Reminders")
        self.chk_hourly_chime.setChecked(self.controller.manager.config.get("hourly_chime", True))
        self.chk_hourly_chime.toggled.connect(self.on_hourly_chime_toggled)

        btn_test_chime = QPushButton("Test Chime Now")
        btn_test_chime.setObjectName("SecondaryBtn")
        btn_test_chime.clicked.connect(lambda: self.controller.trigger_hourly_chime(force=True))

        chime_ctrl_row.addWidget(self.chk_hourly_chime)
        chime_ctrl_row.addStretch()
        chime_ctrl_row.addWidget(btn_test_chime)

        chime_layout.addWidget(lbl_chime_title)
        chime_layout.addWidget(lbl_chime_desc)
        chime_layout.addLayout(chime_ctrl_row)
        layout.addWidget(chime_card)

        routine_card = QFrame()
        routine_card.setObjectName("Card")
        routine_layout = QVBoxLayout(routine_card)
        routine_layout.setSpacing(6)

        lbl_rt_title = QLabel("Day / Night Routine")
        lbl_rt_title.setObjectName("SectionTitle")
        lbl_rt_desc = QLabel(
            "Mascots adapt to the time of day: energetic dances in the morning, "
            "balanced play in the afternoon, and cozy box naps (Zzz...) after 22:00."
        )
        lbl_rt_desc.setWordWrap(True)
        lbl_rt_desc.setObjectName("SubLabel")

        rt_ctrl_row = QHBoxLayout()
        self.chk_day_night = QCheckBox("Enable Day / Night Behavior")
        self.chk_day_night.setChecked(self.controller.manager.config.get("day_night_routine", True))
        self.chk_day_night.toggled.connect(self.on_day_night_toggled)

        btn_night_preview = QPushButton("Preview Night Mood")
        btn_night_preview.setObjectName("SecondaryBtn")
        btn_night_preview.clicked.connect(self.controller.preview_night_mood)

        rt_ctrl_row.addWidget(self.chk_day_night)
        rt_ctrl_row.addStretch()
        rt_ctrl_row.addWidget(btn_night_preview)

        routine_layout.addWidget(lbl_rt_title)
        routine_layout.addWidget(lbl_rt_desc)
        routine_layout.addLayout(rt_ctrl_row)
        layout.addWidget(routine_card)

        layout.addStretch()
        self.tabs.addTab(tab, "Focus & Routine")

    def on_day_night_toggled(self, checked):
        self.controller.manager.config["day_night_routine"] = checked
        self.controller.manager.save_config()

    def on_hourly_chime_toggled(self, checked):
        self.controller.manager.config["hourly_chime"] = checked
        self.controller.manager.save_config()

    def build_theme_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        lbl_title = QLabel("Appearance, Colors & Fonts")
        lbl_title.setObjectName("SectionTitle")
        lbl_desc = QLabel("Personalize the window theme, accent colors, and speech bubble fonts.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setObjectName("SubLabel")
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)

        preset_row = QHBoxLayout()
        lbl_preset = QLabel("Theme Preset:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEME_PRESETS.keys()) + ["Custom"])
        current_preset = self.controller.manager.config.get("theme_preset", "Miku Teal (Dark)")
        if current_preset in THEME_PRESETS:
            self.theme_combo.setCurrentText(current_preset)
        else:
            self.theme_combo.setCurrentText("Custom")
        self.theme_combo.currentTextChanged.connect(self.on_theme_preset_changed)
        preset_row.addWidget(lbl_preset)
        preset_row.addWidget(self.theme_combo)
        card_layout.addLayout(preset_row)

        font_row = QHBoxLayout()
        lbl_font = QLabel("Bubble Font:")
        self.font_combo = QComboBox()
        self.refresh_font_combo()
        self.font_combo.currentTextChanged.connect(self.on_font_changed)

        btn_add_font = QPushButton("+ Font (.ttf/.otf)")
        btn_add_font.setObjectName("SecondaryBtn")
        btn_add_font.clicked.connect(self.import_custom_font)

        btn_del_font = QPushButton("Remove")
        btn_del_font.setObjectName("DangerBtn")
        btn_del_font.clicked.connect(self.delete_selected_font)

        font_row.addWidget(lbl_font)
        font_row.addWidget(self.font_combo)
        font_row.addWidget(btn_add_font)
        font_row.addWidget(btn_del_font)
        card_layout.addLayout(font_row)

        custom_row = QHBoxLayout()
        self.lbl_accent_hex = QLabel(f"Accent Color: {self.controller.manager.config.get('accent_color', '#39C5BB')}")
        btn_pick_color = QPushButton("Pick Custom Accent Color...")
        btn_pick_color.setObjectName("PrimaryBtn")
        btn_pick_color.clicked.connect(self.pick_custom_color)
        custom_row.addWidget(self.lbl_accent_hex)
        custom_row.addStretch()
        custom_row.addWidget(btn_pick_color)
        card_layout.addLayout(custom_row)

        mode_row = QHBoxLayout()
        btn_dark = QPushButton("Dark Base")
        btn_dark.setObjectName("SecondaryBtn")
        btn_dark.clicked.connect(lambda: self.set_base_mode("dark"))

        btn_light = QPushButton("Light Base")
        btn_light.setObjectName("SecondaryBtn")
        btn_light.clicked.connect(lambda: self.set_base_mode("light"))

        mode_row.addWidget(QLabel("Window Surface:"))
        mode_row.addStretch()
        mode_row.addWidget(btn_dark)
        mode_row.addWidget(btn_light)
        card_layout.addLayout(mode_row)

        layout.addWidget(card)

        # Her OS'ta Uygulama İkonu Değiştirme Kartı
        icon_card = QFrame()
        icon_card.setObjectName("Card")
        icon_layout = QVBoxLayout(icon_card)
        icon_layout.setSpacing(8)

        lbl_ic_title = QLabel("App Icon (All OS)")
        lbl_ic_title.setObjectName("SectionTitle")
        lbl_ic_desc = QLabel(
            "Change the window, tray, and dock icon across macOS, Windows, and Linux."
        )
        lbl_ic_desc.setWordWrap(True)
        lbl_ic_desc.setObjectName("SubLabel")

        ic_btn_row = QHBoxLayout()
        btn_choose_icon = QPushButton("Choose Icon File...")
        btn_choose_icon.setObjectName("PrimaryBtn")
        btn_choose_icon.clicked.connect(self.choose_app_icon)

        btn_reset_icon = QPushButton("Reset Default")
        btn_reset_icon.setObjectName("SecondaryBtn")
        btn_reset_icon.clicked.connect(self.reset_app_icon)

        ic_btn_row.addWidget(btn_choose_icon)
        ic_btn_row.addWidget(btn_reset_icon)
        ic_btn_row.addStretch()

        icon_layout.addWidget(lbl_ic_title)
        icon_layout.addWidget(lbl_ic_desc)
        icon_layout.addLayout(ic_btn_row)
        layout.addWidget(icon_card)

        layout.addStretch()

        self.tabs.addTab(tab, "Theme & UI")

    def choose_app_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select App Icon", str(Path.home()),
            "Icon & Image Files (*.png *.ico *.icns *.jpg *.jpeg)"
        )
        if path:
            ok, msg = self.controller.manager.set_custom_app_icon(path)
            if ok:
                self.controller.apply_app_icon()
                QMessageBox.information(self, "App Icon", msg)
            else:
                QMessageBox.warning(self, "Warning", msg)

    def reset_app_icon(self):
        self.controller.manager.reset_app_icon()
        self.controller.apply_app_icon()
        QMessageBox.information(self, "App Icon", "Reverted to default KomaStage icon.")

    def on_window_landing_toggled(self, checked):
        self.controller.manager.config["window_landing"] = checked
        self.controller.manager.save_config()
        if not checked:
            for p in self.controller.pets:
                p.active_ledge = None

    def on_social_toggled(self, checked):
        self.controller.manager.config["social_interactions"] = checked
        self.controller.manager.save_config()

    def on_sfx_preset_changed(self, sfx_name):
        self.controller.manager.config["default_sfx"] = sfx_name
        self.controller.manager.save_config()
        self.controller.sound_engine.play_for_character(self.get_selected_character(), force_builtin=True)

    def test_builtin_sound(self):
        self.controller.sound_engine.play_for_character(self.get_selected_character(), force_builtin=True)

    def on_sound_toggled(self, checked):
        self.controller.manager.config["sound_enabled"] = checked
        self.controller.manager.save_config()

    def on_volume_changed(self, value):
        self.lbl_vol.setText(f"Sound Volume: {value}%")
        self.controller.manager.config["sound_volume"] = value
        self.controller.manager.save_config()

    def update_sound_badge(self):
        name = self.get_selected_character()
        cnt = self.controller.manager.get_character_sound_count(name)
        if cnt > 0:
            self.lbl_char_sounds.setText(f"Voice/SFX: {cnt} custom audio file(s)")
        else:
            self.lbl_char_sounds.setText("Voice/SFX: Using Default SFX Preset")

    def import_sound_for_selected(self):
        name = self.get_selected_character()
        path, _ = QFileDialog.getOpenFileName(
            self, f"Add Voice/SFX for {name}", str(Path.home()), "Audio Files (*.wav *.mp3 *.ogg)"
        )
        if path:
            ok, msg = self.controller.manager.add_character_sound(name, path)
            if ok:
                self.update_sound_badge()
                self.controller.sound_engine.play_for_character(name)
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Warning", msg)

    def refresh_font_combo(self):
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        all_fonts = self.controller.manager.get_all_font_names()
        self.font_combo.addItems(all_fonts)
        current = self.controller.manager.config.get("bubble_font", "Cute Rounded")
        if current in all_fonts:
            self.font_combo.setCurrentText(current)
        self.font_combo.blockSignals(False)

    def import_custom_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Font File", str(Path.home()), "Font Files (*.ttf *.otf)"
        )
        if path:
            ok, msg, new_label = self.controller.manager.import_font(path)
            if ok and new_label:
                self.controller.manager.config["bubble_font"] = new_label
                self.controller.manager.save_config()
                self.refresh_font_combo()
                self.controller.update_all_bubble_themes()
                for p in self.controller.pets:
                    p.say("Testing my new custom font! ♪")
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Warning", msg)

    def delete_selected_font(self):
        selected = self.font_combo.currentText()
        if selected in BUILTIN_FONTS:
            QMessageBox.information(self, "Info", "Built-in font presets cannot be removed.")
            return
        if self.controller.manager.delete_custom_font(selected):
            self.controller.manager.config["bubble_font"] = "Cute Rounded"
            self.controller.manager.save_config()
            self.refresh_font_combo()
            self.controller.update_all_bubble_themes()

    def on_font_changed(self, font_name):
        if not font_name:
            return
        self.controller.manager.config["bubble_font"] = font_name
        self.controller.manager.save_config()
        self.controller.update_all_bubble_themes()
        for p in self.controller.pets:
            p.say("New cute font style! ♪")

    def on_theme_preset_changed(self, name):
        if name in THEME_PRESETS:
            preset = THEME_PRESETS[name]
            self.controller.manager.config["theme_preset"] = name
            self.controller.manager.config["theme_mode"] = preset["mode"]
            self.controller.manager.config["accent_color"] = preset["accent"]
            self.controller.manager.save_config()
            self.lbl_accent_hex.setText(f"Accent Color: {preset['accent']}")
            self.apply_styles()
            self.controller.update_all_bubble_themes()

    def pick_custom_color(self):
        current = QColor(self.controller.manager.config.get("accent_color", "#39C5BB"))
        color = QColorDialog.getColor(current, self, "Choose Accent Color")
        if color.isValid():
            hex_code = color.name().upper()
            self.controller.manager.config["theme_preset"] = "Custom"
            self.controller.manager.config["accent_color"] = hex_code
            self.controller.manager.save_config()
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText("Custom")
            self.theme_combo.blockSignals(False)
            self.lbl_accent_hex.setText(f"Accent Color: {hex_code}")
            self.apply_styles()
            self.controller.update_all_bubble_themes()

    def set_base_mode(self, mode):
        self.controller.manager.config["theme_mode"] = mode
        self.controller.manager.config["theme_preset"] = "Custom"
        self.controller.manager.save_config()
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText("Custom")
        self.theme_combo.blockSignals(False)
        self.apply_styles()
        self.controller.update_all_bubble_themes()

    def apply_styles(self):
        mode = self.controller.manager.config.get("theme_mode", "dark")
        accent = self.controller.manager.config.get("accent_color", "#39C5BB")
        accent_q = QColor(accent)
        accent_hover = accent_q.lighter(115).name()
        lum = (0.299 * accent_q.red() + 0.587 * accent_q.green() + 0.114 * accent_q.blue())
        primary_fg = "#0F171A" if lum > 145 else "#FFFFFF"

        if mode == "light":
            bg_main = "#F4F6FA"
            bg_pane = "#FFFFFF"
            bg_card = "#F8FAFC"
            bg_input = "#FFFFFF"
            border = "#DCE1EB"
            text_main = "#1E2230"
            text_sub = "#5A6275"
            sec_bg = "#E6EAF2"
            sec_hover = "#D7DCE8"
            sel_bg = accent_q.lighter(165).name()
        else:
            bg_main = "#161822"
            bg_pane = "#1B1E2C"
            bg_card = "#1F2232"
            bg_input = "#161822"
            border = "#2D324A"
            text_main = "#E6E8F0"
            text_sub = "#9499B3"
            sec_bg = "#2B3046"
            sec_hover = "#383F5C"
            sel_bg = "#2B3B4E"

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {bg_main};
                color: {text_main};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 13px;
            }}
            #TitleLabel {{
                font-size: 20px;
                font-weight: 700;
                color: {accent};
            }}
            #SubLabel {{
                color: {text_sub};
                margin-bottom: 2px;
            }}
            #SectionTitle {{
                font-size: 14px;
                font-weight: 600;
                color: {text_main};
            }}
            #TimerLabel {{
                font-size: 34px;
                font-weight: 700;
                color: {accent};
                padding: 8px;
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                border-radius: 10px;
                background-color: {bg_pane};
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {bg_main};
                color: {text_sub};
                padding: 7px 11px;
                border: 1px solid {border};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 3px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {bg_pane};
                color: {accent};
            }}
            #Card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 5px;
            }}
            QListWidget {{
                background-color: {bg_input};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 5px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: {sel_bg};
                color: {accent};
                font-weight: 600;
            }}
            QLineEdit, QComboBox {{
                background-color: {bg_input};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 5px 9px;
                color: {text_main};
            }}
            QPushButton {{
                border-radius: 8px;
                padding: 7px 11px;
                font-weight: 600;
            }}
            #PrimaryBtn {{
                background-color: {accent};
                color: {primary_fg};
            }}
            #PrimaryBtn:hover {{
                background-color: {accent_hover};
            }}
            #SecondaryBtn {{
                background-color: {sec_bg};
                color: {text_main};
            }}
            #SecondaryBtn:hover {{
                background-color: {sec_hover};
            }}
            #DangerBtn {{
                background-color: #4A2530;
                color: #FF8A9E;
            }}
            #DangerBtn:hover {{
                background-color: #632F3E;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {bg_input};
                border: 1px solid {border};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
        """)

    def on_preset_changed(self, idx):
        if not self.controller.focus_active:
            mins = [25, 45, 5][idx]
            self.lbl_timer.setText(f"{mins:02d}:00")

    def toggle_focus_timer(self):
        if self.controller.focus_active:
            self.controller.stop_focus()
        else:
            mins = [25, 45, 5][self.focus_combo.currentIndex()]
            self.controller.start_focus(mins)

    def on_bubbles_toggled(self, checked):
        self.controller.manager.config["bubbles_enabled"] = checked
        self.controller.manager.save_config()

    def refresh_quotes_list(self):
        self.quote_list.clear()
        quotes = self.controller.manager.config.get("custom_quotes", list(CharacterManager.DEFAULT_QUOTES))
        for q in quotes:
            self.quote_list.addItem(q)

    def add_custom_quote(self):
        text = self.input_quote.text().strip()
        if not text:
            return
        quotes = self.controller.manager.config.get("custom_quotes", list(CharacterManager.DEFAULT_QUOTES))
        quotes.append(text)
        self.controller.manager.config["custom_quotes"] = quotes
        self.controller.manager.save_config()
        self.input_quote.clear()
        self.refresh_quotes_list()
        for p in self.controller.pets:
            p.say(text)

    def remove_selected_quote(self):
        row = self.quote_list.currentRow()
        if row < 0:
            return
        quotes = self.controller.manager.config.get("custom_quotes", list(CharacterManager.DEFAULT_QUOTES))
        if len(quotes) <= 1:
            QMessageBox.information(self, "Info", "At least one phrase must remain in the list.")
            return
        quotes.pop(row)
        self.controller.manager.config["custom_quotes"] = quotes
        self.controller.manager.save_config()
        self.refresh_quotes_list()

    def delete_selected(self):
        name = self.get_selected_character()
        if name == "Hatsune Miku":
            QMessageBox.information(self, "Info", "The default Hatsune Miku character cannot be deleted.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete", f"Remove '{name}' from your library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.controller.manager.delete_character(name)
            if ok:
                self.refresh_character_list()
            else:
                QMessageBox.warning(self, "Warning", msg)

    def refresh_character_list(self):
        self.char_list.clear()
        chars = self.controller.manager.get_characters()
        last_char = self.controller.manager.config.get("last_character", "Hatsune Miku")
        selected_row = 0

        for idx, name in enumerate(chars):
            char_dir = self.controller.manager.get_character_path(name)
            preview = char_dir / "shime1.png"
            if not preview.exists():
                pngs = list(char_dir.glob("*.png"))
                preview = pngs[0] if pngs else None

            icon = QIcon(str(preview)) if preview and preview.exists() else QIcon()
            item = QListWidgetItem(icon, name)
            self.char_list.addItem(item)
            if name == last_char:
                selected_row = idx

        if self.char_list.count() > 0:
            self.char_list.setCurrentRow(selected_row)
        self.update_sound_badge()

    def get_selected_character(self):
        item = self.char_list.currentItem()
        return item.text() if item else "Hatsune Miku"

    def spawn_selected(self):
        self.controller.spawn_pet(self.get_selected_character())

    def replace_with_selected(self):
        name = self.get_selected_character()
        self.controller.clear_all_pets()
        self.controller.spawn_pet(name)

    def import_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Shimeji ZIP File", str(Path.home()), "ZIP Archives (*.zip)"
        )
        if path:
            self.process_import(path)

    def import_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Shimeji Sprite Folder", str(Path.home())
        )
        if path:
            self.process_import(path)

    def process_import(self, path):
        ok, msg = self.controller.manager.import_character(path)
        if ok:
            self.refresh_character_list()
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.warning(self, "Warning", msg)

    def on_size_changed(self, value):
        self.lbl_size.setText(f"Mascot Size: {value} px")
        self.controller.update_all_sizes(value)

    def on_speed_changed(self, value):
        self.lbl_speed.setText(f"Movement Speed: {value}%")
        self.controller.update_all_speeds(value / 100.0)

    def update_active_count(self, count):
        self.lbl_active.setText(f"Active Mascots: {count}")

    def open_pets_folder(self):
        if sys.platform == "darwin":
            subprocess.run(["open", str(PETS_DIR)])
        elif sys.platform == "win32":
            os.startfile(str(PETS_DIR))
        else:
            subprocess.run(["xdg-open", str(PETS_DIR)])

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class PetController:
    CARE_REMINDERS = [
        "Time for a sip of water! 💧",
        "Don't forget to blink and rest your eyes~ ♡",
        "Check your posture and roll your shoulders! ★",
        "Stretch your wrists for a moment~ ♪",
        "Take a deep breath, you're doing awesome! ☆"
    ]

    def __init__(self, app):
        self.app = app
        self.manager = CharacterManager()
        self.sound_engine = SoundEngine(self.manager)
        self.window_tracker = WindowTracker()
        self.laser_overlay = LaserPointerOverlay()
        self.audio_detector = AudioActivityDetector()
        self.pets = []
        self.pets_hidden = False
        self.laser_active = False
        self.focus_active = False
        self.focus_seconds_left = 0
        self.music_dancing = False
        self.music_silent_ticks = 0
        self.last_chime_hour = datetime.now().hour
        self.last_period = self.get_time_period()

        self.focus_timer = QTimer(self.app)
        self.focus_timer.timeout.connect(self.tick_focus)

        self.clock_timer = QTimer(self.app)
        self.clock_timer.timeout.connect(self.check_hourly_and_period)
        self.clock_timer.start(20000)

        self.music_timer = QTimer(self.app)
        self.music_timer.timeout.connect(self.poll_music_activity)
        self.music_timer.start(2200)

        self.win_scan_timer = QTimer(self.app)
        self.win_scan_timer.timeout.connect(self.scan_desktop_windows)
        self.win_scan_timer.start(1500)
        self.scan_desktop_windows()

        self.panel = ControlPanel(self)
        self.setup_tray()
        self.apply_app_icon()

        available = self.manager.get_characters()
        if self.manager.config.get("restore_last_stage", True):
            saved_chars = [c for c in self.manager.config.get("last_stage_chars", []) if c in available]
            if not saved_chars:
                saved_chars = ["Hatsune Miku"]
            for c in saved_chars:
                self.spawn_pet(c, save_state=False)
        else:
            start_char = self.manager.config.get("last_character", "Hatsune Miku")
            if start_char not in available:
                start_char = "Hatsune Miku"
            self.spawn_pet(start_char, save_state=False)

        self.save_active_stage_state()
        self.panel.show()

    def apply_app_icon(self):
        icon = self.manager.get_app_icon()
        if not icon.isNull():
            self.app.setWindowIcon(icon)
            self.panel.setWindowIcon(icon)
            if hasattr(self, "tray") and self.tray:
                self.tray.setIcon(icon)

    def get_time_period(self):
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 22:
            return "afternoon"
        return "night"

    def preview_night_mood(self):
        if not self.pets:
            return
        for p in self.pets:
            p.set_state("sleep_box")
            p.spawn_emote("Zzz...", "#9FA8DA")
        random.choice(self.pets).say("Getting sleepy... cozy box nap time~ Zzz", 3800, force=True)

    def trigger_music_dance_preview(self):
        if not self.pets:
            return
        self.music_dancing = True
        self.music_silent_ticks = 0
        for p in self.pets:
            p.set_state(random.choice(["leek_walk", "mini_miku"]))
            p.spawn_emote("♫")
        random.choice(self.pets).say("Vibing to the beat! ♪ ~ ♫", 3200, force=True)
        QTimer.singleShot(6000, self._end_music_preview)

    def _end_music_preview(self):
        if not self.audio_detector.is_system_playing_audio():
            self.music_dancing = False

    def poll_music_activity(self):
        if not self.manager.config.get("music_reaction", True):
            self.music_dancing = False
            return
        if self.focus_active or self.laser_active or self.pets_hidden or not self.pets:
            return
        if self.sound_engine.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            return

        playing = self.audio_detector.is_system_playing_audio()
        if playing:
            self.music_silent_ticks = 0
            if not self.music_dancing:
                self.music_dancing = True
                for p in self.pets:
                    if not p.is_dragging and not p.is_paused:
                        p.set_state(random.choice(["leek_walk", "mini_miku"]))
                        p.spawn_emote("♪")
                random.choice(self.pets).say("Ooh, music time! ♪ ~ ♫", 2800)
        else:
            if self.music_dancing:
                self.music_silent_ticks += 1
                if self.music_silent_ticks >= 2:
                    self.music_dancing = False
                    for p in self.pets:
                        if not p.is_dragging and not p.is_paused and p.state in ["leek_walk", "mini_miku"]:
                            p.set_state("sit")

    def check_hourly_and_period(self):
        now = datetime.now()
        if now.minute == 0 and now.hour != self.last_chime_hour:
            self.last_chime_hour = now.hour
            self.trigger_hourly_chime(force=False)

        curr_period = self.get_time_period()
        if curr_period != self.last_period:
            self.last_period = curr_period
            if self.manager.config.get("day_night_routine", True) and self.pets and not self.pets_hidden:
                if curr_period == "night":
                    self.preview_night_mood()
                elif curr_period == "morning":
                    random.choice(self.pets).say("Good morning! Ready for a great day~ ★", 3600)

    def trigger_hourly_chime(self, force=False):
        if not force and not self.manager.config.get("hourly_chime", True):
            return
        if not self.pets or self.pets_hidden:
            return
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        reminder = random.choice(self.CARE_REMINDERS)
        speaker = random.choice(self.pets)
        speaker.spawn_emote("♪")
        speaker.say(f"It's {time_str}! {reminder}", 5200, force=True)
        self.sound_engine.play_for_character(speaker.char_name)

    def set_follow_cursor(self, enabled):
        self.manager.config["follow_cursor"] = enabled
        self.manager.save_config()
        if enabled and self.laser_active:
            self.set_laser_toy(False)

        if self.panel.chk_follow_cursor.isChecked() != enabled:
            self.panel.chk_follow_cursor.blockSignals(True)
            self.panel.chk_follow_cursor.setChecked(enabled)
            self.panel.chk_follow_cursor.blockSignals(False)
        self.tray_follow_act.setChecked(enabled)

        if not enabled:
            for p in self.pets:
                p.set_state("sit")

    def set_laser_toy(self, enabled):
        self.laser_active = enabled
        if enabled:
            if self.manager.config.get("follow_cursor", False):
                self.set_follow_cursor(False)
            if not self.pets_hidden:
                self.laser_overlay.start()
            for p in self.pets:
                p.spawn_emote("!", "#FF5252")
                p.say("Ooh, a red dot!! ★", 2200)
        else:
            self.laser_overlay.stop()
            for p in self.pets:
                p.set_state("sit")

        if self.panel.chk_laser_toy.isChecked() != enabled:
            self.panel.chk_laser_toy.blockSignals(True)
            self.panel.chk_laser_toy.setChecked(enabled)
            self.panel.chk_laser_toy.blockSignals(False)
        self.tray_laser_act.setChecked(enabled)

    def toggle_hide_all(self):
        self.pets_hidden = not self.pets_hidden
        for p in self.pets:
            if self.pets_hidden:
                p.bubble.hide()
                for em in list(p.active_emotes):
                    em.close()
                p.hide()
            else:
                p.show()
                if self.manager.config.get("ghost_mode", False):
                    p.apply_ghost_mode(True)

        if self.pets_hidden:
            self.laser_overlay.stop()
        elif self.laser_active:
            self.laser_overlay.start()

        label = "Show Mascots" if self.pets_hidden else "Hide All (Boss Key)"
        self.panel.btn_boss_hide.setText(label)
        self.tray_hide_act.setText(label)

    def set_ghost_mode(self, enabled):
        self.manager.config["ghost_mode"] = enabled
        self.manager.save_config()
        if self.panel.chk_ghost.isChecked() != enabled:
            self.panel.chk_ghost.blockSignals(True)
            self.panel.chk_ghost.setChecked(enabled)
            self.panel.chk_ghost.blockSignals(False)
        self.tray_ghost_act.setChecked(enabled)
        for p in self.pets:
            if not self.pets_hidden:
                p.apply_ghost_mode(enabled)

    def save_active_stage_state(self):
        if self.pets:
            self.manager.config["last_stage_chars"] = [p.char_name for p in self.pets]
            self.manager.save_config()

    def scan_desktop_windows(self):
        if self.manager.config.get("window_landing", True):
            screen = QApplication.primaryScreen().availableGeometry()
            self.window_tracker.refresh(screen)
        else:
            self.window_tracker.ledges.clear()

    def update_all_bubble_themes(self):
        accent = self.manager.config.get("accent_color", "#39C5BB")
        mode = self.manager.config.get("theme_mode", "dark")
        font_css = self.manager.get_active_font_css()
        for p in self.pets:
            p.bubble.update_theme(accent, mode, font_css)

    def start_focus(self, minutes):
        self.focus_active = True
        self.focus_seconds_left = minutes * 60
        self.panel.btn_focus.setText("Stop Focus")
        self.panel.btn_focus.setObjectName("DangerBtn")
        self.panel.apply_styles()
        self.update_focus_label()
        self.focus_timer.start(1000)
        for p in self.pets:
            p.set_focus_mode(True)

    def stop_focus(self, completed=False):
        self.focus_active = False
        self.focus_timer.stop()
        mins = [25, 45, 5][self.panel.focus_combo.currentIndex()]
        self.panel.lbl_timer.setText("Done!" if completed else f"{mins:02d}:00")
        self.panel.btn_focus.setText("Start Focus")
        self.panel.btn_focus.setObjectName("PrimaryBtn")
        self.panel.apply_styles()
        for p in self.pets:
            if completed:
                p.set_focus_mode(False)
            else:
                p.focus_mode = False

    def tick_focus(self):
        self.focus_seconds_left -= 1
        if self.focus_seconds_left <= 0:
            self.stop_focus(completed=True)
        else:
            self.update_focus_label()

    def update_focus_label(self):
        mins = self.focus_seconds_left // 60
        secs = self.focus_seconds_left % 60
        self.panel.lbl_timer.setText(f"{mins:02d}:{secs:02d}")

    def spawn_pet(self, char_name=None, save_state=True):
        if not char_name:
            char_name = self.manager.config.get("last_character", "Hatsune Miku")
        char_dir = self.manager.get_character_path(char_name)
        if not char_dir.exists():
            return

        self.manager.config["last_character"] = char_name
        pet = DesktopPet(
            char_name=char_name,
            char_dir=char_dir,
            size_px=self.manager.config["size"],
            speed_mult=self.manager.config["speed_mult"],
            app_controller=self
        )
        if self.focus_active:
            pet.set_focus_mode(True)
        if self.manager.config.get("ghost_mode", False):
            pet.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if not self.pets_hidden:
            pet.show()
            pet.spawn_emote("★")
        self.pets.append(pet)
        self.panel.update_active_count(len(self.pets))
        if save_state:
            self.save_active_stage_state()

    def remove_pet(self, pet):
        if pet in self.pets:
            self.pets.remove(pet)
            self.panel.update_active_count(len(self.pets))
            self.save_active_stage_state()

    def clear_all_pets(self):
        for p in list(self.pets):
            p.bubble.close()
            for em in list(p.active_emotes):
                em.close()
            p.close()
        self.pets.clear()
        self.panel.update_active_count(0)
        self.save_active_stage_state()

    def update_all_sizes(self, new_size):
        self.manager.config["size"] = new_size
        self.manager.save_config()
        for p in self.pets:
            p.set_size(new_size)

    def update_all_speeds(self, new_mult):
        self.manager.config["speed_mult"] = new_mult
        self.manager.save_config()
        for p in self.pets:
            p.set_speed(new_mult)

    def show_panel(self):
        self.panel.refresh_character_list()
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def setup_tray(self):
        icon = self.manager.get_app_icon()
        self.tray = QSystemTrayIcon(icon, self.app)
        tray_menu = QMenu()

        panel_act = QAction("Open Control Panel", self.app)
        panel_act.triggered.connect(self.show_panel)

        add_act = QAction("Summon New Mascot (+1)", self.app)
        add_act.triggered.connect(lambda: self.spawn_pet())

        self.tray_follow_act = QAction("Follow Mouse Cursor", self.app)
        self.tray_follow_act.setCheckable(True)
        self.tray_follow_act.setChecked(self.manager.config.get("follow_cursor", False))
        self.tray_follow_act.triggered.connect(self.set_follow_cursor)

        self.tray_laser_act = QAction("Red Laser Pointer Toy", self.app)
        self.tray_laser_act.setCheckable(True)
        self.tray_laser_act.setChecked(False)
        self.tray_laser_act.triggered.connect(self.set_laser_toy)

        self.tray_hide_act = QAction("Hide All (Boss Key)", self.app)
        self.tray_hide_act.triggered.connect(self.toggle_hide_all)

        self.tray_ghost_act = QAction("Ghost Mode (Click-Through)", self.app)
        self.tray_ghost_act.setCheckable(True)
        self.tray_ghost_act.setChecked(self.manager.config.get("ghost_mode", False))
        self.tray_ghost_act.triggered.connect(self.set_ghost_mode)

        quit_act = QAction("Quit", self.app)
        quit_act.triggered.connect(self.app.quit)

        tray_menu.addAction(panel_act)
        tray_menu.addAction(add_act)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_follow_act)
        tray_menu.addAction(self.tray_laser_act)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_hide_act)
        tray_menu.addAction(self.tray_ghost_act)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_act)

        self.tray.setContextMenu(tray_menu)
        self.tray.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("KomaStage")
    app.setApplicationDisplayName("KomaStage")
    app.setDesktopFileName("KomaStage")
    app.setQuitOnLastWindowClosed(False)
    try:
        import setproctitle
        setproctitle.setproctitle("KomaStage")
    except Exception:
        pass
    controller = PetController(app)
    sys.exit(app.exec())
