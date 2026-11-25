import os
import sys
import random
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QMenu, QSystemTrayIcon
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QTransform, QAction, QIcon

def resource_path(relative_path):
    """PyInstaller ile paketlendiğinde veya normal çalışırken doğru dosya yolunu döner."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class DesktopPet(QWidget):
    def __init__(self, app_controller=None):
        super().__init__()
        self.app_controller = app_controller
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.size_px = 128
        self.setFixedSize(self.size_px, self.size_px)
        
        self.label = QLabel(self)
        self.label.setFixedSize(self.size_px, self.size_px)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.animations = {
            "walk": self.load_frames(["assets/shime1.png", "assets/shime2.png", "assets/shime3.png"]),
            "run": self.load_frames(["assets/shime49.png", "assets/shime50.png", "assets/shime51.png"]),
            "leek_walk": self.load_frames(["assets/shime42.png", "assets/shime43.png", "assets/shime44.png", "assets/shime45.png"]),
            "sit": self.load_frames(["assets/shime11.png", "assets/shime12.png", "assets/shime15.png", "assets/shime16.png"]),
            "mini_miku": self.load_frames(["assets/shime52.png", "assets/shime53.png", "assets/shime54.png", "assets/shime55.png"]),
            "sleep_box": self.load_frames(["assets/shime20.png", "assets/shime21.png"]),
            "climb_wall": self.load_frames(["assets/shime30.png", "assets/shime31.png", "assets/shime32.png"]),
            "climb_ceiling": self.load_frames(["assets/shime22.png", "assets/shime23.png", "assets/shime24.png", "assets/shime25.png"]),
            "drag": self.load_frames(["assets/shime5.png", "assets/shime6.png", "assets/shime7.png", "assets/shime8.png", "assets/shime10.png"]),
            "fall": self.load_frames(["assets/shime4.png", "assets/shime9.png"])
        }

        self.state = "walk"
        self.frame_index = 0
        self.direction = random.choice([-1, 1])
        self.is_dragging = False
        self.is_paused = False
        self.drag_offset = QPoint()

        screen = QApplication.primaryScreen().availableGeometry()
        self.x_pos = random.randint(100, screen.width() - 200)
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

    def load_frames(self, paths):
        frames = []
        for path in paths:
            full_path = resource_path(path)
            pix = QPixmap(full_path)
            if not pix.isNull():
                pix.setDevicePixelRatio(1.0)
                pix = pix.scaled(
                    self.size_px, self.size_px,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                frames.append(pix)
        return frames

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
            speed = 7 if self.state == "run" else 3
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
            if abs(self.x_pos - target_x) > 5:
                self.x_pos += 5 * self.direction
            else:
                self.x_pos = target_x
                self.y_pos -= 4
                if self.y_pos <= ceiling_y:
                    self.y_pos = ceiling_y
                    self.direction = 1 if self.x_pos == screen.left() else -1
                    self.set_state("climb_ceiling")
            self.move(self.x_pos, self.y_pos)

        elif self.state == "climb_ceiling":
            self.x_pos += 3 * self.direction
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
            (self.state in ["walk", "run", "leek_walk", "climb_ceiling", "climb_wall"] and self.direction == 1)
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
        actions_menu = menu.addMenu("Hareket Seç")
        for label_text, st in [
            ("Yürü", "walk"),
            ("Koş", "run"),
            ("Pırasa Taşı", "leek_walk"),
            ("Otur", "sit"),
            ("Bebek Miku", "mini_miku"),
            ("Kutuya Gir", "sleep_box"),
            ("Duvara Tırman", "climb_wall")
        ]:
            act = QAction(label_text, self)
            act.triggered.connect(lambda checked, s=st: self.set_state(s))
            actions_menu.addAction(act)

        if self.app_controller:
            spawn_act = QAction("Bir Miku Daha Çağır (+1)", self)
            spawn_act.triggered.connect(self.app_controller.spawn_pet)
            menu.addAction(spawn_act)

        menu.addSeparator()
        pause_action = QAction("Devam Et" if self.is_paused else "Duraklat", self)
        pause_action.triggered.connect(self.toggle_pause)
        
        remove_action = QAction("Bu Miku'yu Gönder", self)
        remove_action.triggered.connect(self.close)

        quit_action = QAction("Tamamen Kapat", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(pause_action)
        menu.addAction(remove_action)
        menu.addAction(quit_action)
        menu.exec(event.globalPosition().toPoint())

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self.set_state("sit")

class PetController:
    def __init__(self, app):
        self.app = app
        self.pets = []
        self.setup_tray()
        self.spawn_pet()

    def spawn_pet(self):
        pet = DesktopPet(self)
        pet.show()
        self.pets.append(pet)

    def setup_tray(self):
        icon_pix = QPixmap(resource_path("assets/icon.png"))
        if icon_pix.isNull():
            icon_pix = QPixmap(resource_path("assets/shime1.png"))
        
        self.tray = QSystemTrayIcon(QIcon(icon_pix), self.app)
        tray_menu = QMenu()

        add_act = QAction("Yeni Miku Çağır (+1)", self.app)
        add_act.triggered.connect(self.spawn_pet)

        quit_act = QAction("Çıkış", self.app)
        quit_act.triggered.connect(self.app.quit)

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
