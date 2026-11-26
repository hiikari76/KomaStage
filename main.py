import os
import sys
import json
import shutil
import random
import zipfile
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QMenu, QSystemTrayIcon,
    QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QSlider, QFileDialog,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize
from PyQt6.QtGui import QPixmap, QTransform, QAction, QIcon

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Kullanıcı karakterlerinin ve ayarlarının saklanacağı kalıcı dizin
USER_DATA_DIR = Path.home() / "Documents" / "KomaStage"
PETS_DIR = USER_DATA_DIR / "pets"
CONFIG_FILE = USER_DATA_DIR / "config.json"


class CharacterManager:
    def __init__(self):
        PETS_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_default_miku()
        self.config = self.load_config()

    def ensure_default_miku(self):
        """Uygulama içindeki varsayılan Miku varlıklarını kullanıcı klasörüne kopyalar."""
        miku_dir = PETS_DIR / "Hatsune Miku"
        if not miku_dir.exists() or not any(miku_dir.iterdir()):
            miku_dir.mkdir(parents=True, exist_ok=True)
            bundled_assets = Path(resource_path("assets"))
            if bundled_assets.exists():
                for img in bundled_assets.glob("*.png"):
                    shutil.copy2(img, miku_dir / img.name)

    def load_config(self):
        default_cfg = {"size": 128, "speed_mult": 1.0, "last_character": "Hatsune Miku"}
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

    def get_characters(self):
        chars = []
        if PETS_DIR.exists():
            for d in sorted(PETS_DIR.iterdir()):
                if d.is_dir() and any(d.glob("*.png")):
                    chars.append(d.name)
        return chars

    def get_character_path(self, name):
        return PETS_DIR / name

    def import_character(self, source_path):
        """Klasör veya ZIP dosyasından Shimeji sprite'larını otomatik bulup içe aktarır."""
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

            # shime1.png dosyasını içeren asıl görsel klasörünü bul (örn. iç içe img/ klasörü)
            sprite_dir = None
            for p in search_root.rglob("shime1.png"):
                if "__MACOSX" not in str(p):
                    sprite_dir = p.parent
                    break

            if not sprite_dir:
                # shime1.png yoksa en çok PNG içeren klasörü al
                png_dirs = {}
                for p in search_root.rglob("*.png"):
                    if "__MACOSX" not in str(p):
                        png_dirs[p.parent] = png_dirs.get(p.parent, 0) + 1
                if png_dirs:
                    sprite_dir = max(png_dirs, key=png_dirs.get)

            if not sprite_dir:
                return False, "No valid PNG character sprites found in the selected package."

            # Klasör adı sadece 'img' ise bir üst klasörün adını karakter adı yap
            if sprite_dir.name.lower() in ["img", "images", "sprites"] and sprite_dir.parent != temp_dir:
                char_name = sprite_dir.parent.name

            target_dir = PETS_DIR / char_name
            target_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for png in sprite_dir.glob("*.png"):
                shutil.copy2(png, target_dir / png.name)
                copied += 1

            return True, f"'{char_name}' imported successfully ({copied} frames)!"
        except Exception as e:
            return False, f"Import error: {str(e)}"
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


class DesktopPet(QWidget):
    def __init__(self, char_name, char_dir, size_px=128, speed_mult=1.0, app_controller=None):
        super().__init__()
        self.char_name = char_name
        self.char_dir = Path(char_dir)
        self.size_px = size_px
        self.speed_mult = speed_mult
        self.app_controller = app_controller

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.size_px, self.size_px)

        self.label = QLabel(self)
        self.label.setFixedSize(self.size_px, self.size_px)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.load_all_animations()

        self.state = "walk"
        self.frame_index = 0
        self.direction = random.choice([-1, 1])
        self.is_dragging = False
        self.is_paused = False
        self.drag_offset = QPoint()

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

    def load_all_animations(self):
        walk = self.load_frames(["shime1.png", "shime2.png", "shime3.png"])
        if not walk:
            # Hiç standart dosya yoksa klasördeki ilk birkaç PNG'yi al
            any_pngs = [p.name for p in sorted(self.char_dir.glob("*.png"))[:4]]
            walk = self.load_frames(any_pngs)

        sit = self.load_frames(["shime11.png", "shime12.png", "shime15.png", "shime16.png"]) or walk

        # Eksik animasyon kareleri varsa walk/sit ile yedekle (özel Shimeji paketleri çökmesin)
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

    def decide_next_action(self):
        if self.is_dragging or self.is_paused or self.state == "fall":
            return
        if self.state == "climb_ceiling":
            if random.random() < 0.4:
                self.set_state("fall")
            return

        choices = ["walk", "walk", "run", "leek_walk", "sit", "mini_miku", "sleep_box", "climb_wall"]
        chosen = random.choice(choices)
        if chosen in ["walk", "run", "leek_walk"]:
            self.direction = random.choice([-1, 1])
        elif chosen == "climb_wall":
            screen = QApplication.primaryScreen().availableGeometry()
            self.direction = -1 if self.x_pos < screen.width() // 2 else 1
        self.set_state(chosen)

    def update_physics(self):
        if self.is_dragging or self.is_paused:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        ground_y = screen.bottom() - self.size_px
        ceiling_y = screen.top()

        if self.state not in ["climb_wall", "climb_ceiling"] and self.y_pos < ground_y:
            self.set_state("fall")
            self.y_pos = min(self.y_pos + 11, ground_y)
            self.move(self.x_pos, self.y_pos)
            if self.y_pos == ground_y:
                self.set_state("sit")
            return

        if self.state in ["walk", "run", "leek_walk"]:
            base_speed = 7 if self.state == "run" else 3
            speed = max(1, int(round(base_speed * self.speed_mult)))
            self.x_pos += speed * self.direction
            if self.x_pos <= screen.left():
                self.x_pos = screen.left()
                self.direction = 1
            elif self.x_pos + self.size_px >= screen.right():
                self.x_pos = screen.right() - self.size_px
                self.direction = -1
            self.move(self.x_pos, self.y_pos)

        elif self.state == "climb_wall":
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
            self.state in ["walk", "run", "leek_walk", "climb_ceiling", "climb_wall"] and self.direction == 1
        )
        if needs_flip:
            current_pix = current_pix.transformed(QTransform().scale(-1, 1))
        self.label.setPixmap(current_pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.set_state("drag")
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.x_pos = new_pos.x()
            self.y_pos = new_pos.y()
            self.move(self.x_pos, self.y_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.set_state("fall")
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        actions_menu = menu.addMenu("Select Action")
        for label_text, st in [
            ("Walk", "walk"),
            ("Run", "run"),
            ("Özel Walkyüş", "leek_walk"),
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
        if self.app_controller:
            self.app_controller.remove_pet(self)
        self.close()


class ControlPanel(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("KomaStage")
        self.setMinimumSize(460, 560)
        self.apply_styles()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Başlık
        title = QLabel("KomaStage")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Manage, resize, and summon custom Shimeji characters onto your desktop")
        subtitle.setObjectName("SubLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Karakter Listesi Kartı
        char_card = QFrame()
        char_card.setObjectName("Card")
        char_layout = QVBoxLayout(char_card)

        header_row = QHBoxLayout()
        lbl_chars = QLabel("Installed Characters")
        lbl_chars.setObjectName("SectionTitle")

        btn_add_zip = QPushButton("+ Add ZIP")
        btn_add_zip.setObjectName("SecondaryBtn")
        btn_add_zip.clicked.connect(self.import_zip)

        btn_add_dir = QPushButton("+ Add Folder")
        btn_add_dir.setObjectName("SecondaryBtn")
        btn_add_dir.clicked.connect(self.import_folder)

        header_row.addWidget(lbl_chars)
        header_row.addStretch()
        header_row.addWidget(btn_add_zip)
        header_row.addWidget(btn_add_dir)
        char_layout.addLayout(header_row)

        self.char_list = QListWidget()
        self.char_list.setIconSize(QSize(48, 48))
        self.char_list.setSpacing(4)
        char_layout.addWidget(self.char_list)

        spawn_row = QHBoxLayout()
        btn_spawn = QPushButton("Summon Selected (+1)")
        btn_spawn.setObjectName("PrimaryBtn")
        btn_spawn.clicked.connect(self.spawn_selected)

        btn_replace = QPushButton("Replace Active with Selected")
        btn_replace.setObjectName("SecondaryBtn")
        btn_replace.clicked.connect(self.replace_with_selected)

        spawn_row.addWidget(btn_spawn)
        spawn_row.addWidget(btn_replace)
        char_layout.addLayout(spawn_row)
        layout.addWidget(char_card)

        # Ayarlar Kartı
        settings_card = QFrame()
        settings_card.setObjectName("Card")
        settings_layout = QVBoxLayout(settings_card)

        lbl_settings = QLabel("Appearance & Movement Settings")
        lbl_settings.setObjectName("SectionTitle")
        settings_layout.addWidget(lbl_settings)

        # Boyut Kaydırıcısı
        size_row = QHBoxLayout()
        self.lbl_size = QLabel(f"Mascot Size: {self.controller.manager.config['size']} px")
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(64, 256)
        self.slider_size.setValue(self.controller.manager.config['size'])
        self.slider_size.valueChanged.connect(self.on_size_changed)
        size_row.addWidget(self.lbl_size)
        size_row.addWidget(self.slider_size)
        settings_layout.addLayout(size_row)

        # Hız Kaydırıcısı
        speed_row = QHBoxLayout()
        speed_pct = int(self.controller.manager.config['speed_mult'] * 100)
        self.lbl_speed = QLabel(f"Movement Speed: {speed_pct}%")
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 250)
        self.slider_speed.setValue(speed_pct)
        self.slider_speed.valueChanged.connect(self.on_speed_changed)
        speed_row.addWidget(self.lbl_speed)
        speed_row.addWidget(self.slider_speed)
        settings_layout.addLayout(speed_row)
        layout.addWidget(settings_card)

        # Alt Kontrol Butonları
        bottom_row = QHBoxLayout()
        self.lbl_active = QLabel("Active Mascots: 1")
        btn_clear = QPushButton("Clear All")
        btn_clear.setObjectName("DangerBtn")
        btn_clear.clicked.connect(self.controller.clear_all_pets)

        btn_open_dir = QPushButton("Open Folder")
        btn_open_dir.setObjectName("SecondaryBtn")
        btn_open_dir.clicked.connect(self.open_pets_folder)

        bottom_row.addWidget(self.lbl_active)
        bottom_row.addStretch()
        bottom_row.addWidget(btn_open_dir)
        bottom_row.addWidget(btn_clear)
        layout.addLayout(bottom_row)

        self.refresh_character_list()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #161822;
                color: #E6E8F0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 13px;
            }
            #TitleLabel {
                font-size: 20px;
                font-weight: 700;
                color: #39C5BB;
            }
            #SubLabel {
                color: #9499B3;
                margin-bottom: 4px;
            }
            #SectionTitle {
                font-size: 14px;
                font-weight: 600;
                color: #FFFFFF;
            }
            #Card {
                background-color: #1F2232;
                border: 1px solid #2D324A;
                border-radius: 12px;
                padding: 8px;
            }
            QListWidget {
                background-color: #161822;
                border: 1px solid #2D324A;
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #2B3B4E;
                color: #39C5BB;
                font-weight: 600;
            }
            QPushButton {
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            #PrimaryBtn {
                background-color: #39C5BB;
                color: #0F171A;
            }
            #PrimaryBtn:hover {
                background-color: #4AD8CE;
            }
            #SecondaryBtn {
                background-color: #2B3046;
                color: #E6E8F0;
            }
            #SecondaryBtn:hover {
                background-color: #383F5C;
            }
            #DangerBtn {
                background-color: #4A2530;
                color: #FF8A9E;
            }
            #DangerBtn:hover {
                background-color: #632F3E;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #161822;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #39C5BB;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)

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

    def get_selected_character(self):
        item = self.char_list.currentItem()
        return item.text() if item else "Hatsune Miku"

    def spawn_selected(self):
        name = self.get_selected_character()
        self.controller.spawn_pet(name)

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
        import subprocess
        if sys.platform == "darwin":
            subprocess.run(["open", str(PETS_DIR)])
        elif sys.platform == "win32":
            os.startfile(str(PETS_DIR))

    def closeEvent(self, event):
        # Pencere kapatıldığında uygulama arka planda çalışmaya devam etsin
        event.ignore()
        self.hide()


class PetController:
    def __init__(self, app):
        self.app = app
        self.manager = CharacterManager()
        self.pets = []
        self.panel = ControlPanel(self)
        self.setup_tray()

        start_char = self.manager.config.get("last_character", "Hatsune Miku")
        if start_char not in self.manager.get_characters():
            start_char = "Hatsune Miku"
        self.spawn_pet(start_char)
        self.panel.show()

    def spawn_pet(self, char_name=None):
        if not char_name:
            char_name = self.manager.config.get("last_character", "Hatsune Miku")
        char_dir = self.manager.get_character_path(char_name)
        if not char_dir.exists():
            return

        self.manager.config["last_character"] = char_name
        self.manager.save_config()

        pet = DesktopPet(
            char_name=char_name,
            char_dir=char_dir,
            size_px=self.manager.config["size"],
            speed_mult=self.manager.config["speed_mult"],
            app_controller=self
        )
        pet.show()
        self.pets.append(pet)
        self.panel.update_active_count(len(self.pets))

    def remove_pet(self, pet):
        if pet in self.pets:
            self.pets.remove(pet)
            self.panel.update_active_count(len(self.pets))

    def clear_all_pets(self):
        for p in list(self.pets):
            p.close()
        self.pets.clear()
        self.panel.update_active_count(0)

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
        icon_pix = QPixmap(resource_path("assets/shime1.png"))
        self.tray = QSystemTrayIcon(QIcon(icon_pix), self.app)
        tray_menu = QMenu()

        panel_act = QAction("Open Control Panel", self.app)
        panel_act.triggered.connect(self.show_panel)

        add_act = QAction("Summon New Mascot (+1)", self.app)
        add_act.triggered.connect(lambda: self.spawn_pet())

        quit_act = QAction("Quit", self.app)
        quit_act.triggered.connect(self.app.quit)

        tray_menu.addAction(panel_act)
        tray_menu.addAction(add_act)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_act)

        self.tray.setContextMenu(tray_menu)
        self.tray.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = PetController(app)
    sys.exit(app.exec())
