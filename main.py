
# --- Fix for PyInstaller + PyQt5 missing text/images ---
import sys
import os
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_path = sys._MEIPASS
    plugin_path = os.path.join(base_path, "PyQt5", "Qt5", "plugins")
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(plugin_path, "platforms")
    os.environ["QT_PLUGIN_PATH"] = plugin_path
    os.environ["QT_IMAGEPLUGINS_PATH"] = os.path.join(plugin_path, "imageformats")
    os.environ["QT_QPA_PLATFORM"] = "windows"  # Force Windows platform
# -------------------------------------------------------

import ctypes
try:
    # Force default font to Segoe UI (Windows system font)
    ctypes.windll.gdi32.AddFontResourceW("C:\\Windows\\Fonts\\segoeui.ttf")
except Exception:
    pass

# Disable input() to prevent lost sys.stdin errors in frozen/no-console mode
input = lambda *args, **kwargs: (_ for _ in ()).throw(
    RuntimeError("input() is disabled in this application")
)
import threading
import time
import requests
from PyQt5 import QtWidgets, QtGui, QtCore
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Spotify API credentials (replace with your own)
CLIENT_ID = "c25e6b278c244232a226e612e72eca90"
CLIENT_SECRET = "268fa3ad1b0743f78a6e1acd3b7cdbb4"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
# Add user-modify-playback-state for playback/volume/skip controls
SCOPE = "user-read-currently-playing user-read-playback-state user-modify-playback-state"


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_text = self.text()

    def setText(self, text):
        self.full_text = text
        super().setText(text)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class SpotifyDisplay(QtWidgets.QWidget):
    update_song_signal = QtCore.pyqtSignal(str, str, str, str)

    def __init__(self, sp):
        super().__init__()
        # Initialize color attributes before any button is created or styled
        self.button_color = "#282828"
        self.button_fg = "#fff"
        self.text_color = "#fff"
        self.sp = sp
        self.setWindowTitle("AOT_SMP")
        # Transparent title bar and window
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        # Remove any transparency attributes for reliability
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)  # Disabled for label rendering reliability
        # Set a solid background and border for the main window for debug
        #self.setStyleSheet("background-color: #191414; border-radius: 15px; border: 2px solid #ff0000;")
        # Make window resizable and expandable
        self.setMinimumSize(350, 120)
        self.resize(400, 160)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        # Top bar for drag and close
        self.title_bar = QtWidgets.QWidget(self)
        self.title_bar.setFixedHeight(28)
        self.title_bar.setStyleSheet("background: #232323; border-radius: 8px; border: 1px solid #00ff00;")
        self.title_layout = QtWidgets.QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(8, 0, 8, 0)
        self.title_layout.setSpacing(4)
        self.title_label = QtWidgets.QLabel("AOT_SMP", self.title_bar)
        self.title_label.setStyleSheet("color: #fff; font-size: 14px; font-weight: bold;")
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        self.close_btn = QtWidgets.QPushButton("✕", self.title_bar)
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet("QPushButton { color: #fff; background: transparent; border: none; font-size: 16px; } QPushButton:hover { color: #1DB954; }")
        self.close_btn.clicked.connect(self.close)
        self.title_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.title_bar)

        # Content layout
        self.content_widget = QtWidgets.QWidget(self)
        self.content_widget.setStyleSheet("background: #111;")
        self.content_layout = QtWidgets.QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        self.album_cover = QtWidgets.QLabel(self.content_widget)
        self.album_cover.setMinimumSize(60, 60)
        self.album_cover.setMaximumSize(200, 200)
        self.album_cover.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.album_cover.setStyleSheet("border-radius: 10px; background: #222;")
        self.content_layout.addWidget(self.album_cover)

        self.info_layout = QtWidgets.QVBoxLayout()
        self.info_layout.setSpacing(4)
        # Song label with scrolling (marquee) and click to change scroll mode
        self.song_label = ClickableLabel("", self.content_widget)
        self.song_label.setStyleSheet("color: #1DB954; font-size: 18px; font-weight: bold; background: #222; border: 1px solid #00ffff;")
        self.song_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.song_label.setWordWrap(False)
        self.song_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.info_layout.addWidget(self.song_label)
        self.song_scroll_mode = 0  # 0: still, 1: left, 2: right
        self.song_scroll_offset = 0
        self.song_scroll_timer = QtCore.QTimer(self)
        self.song_scroll_timer.timeout.connect(self.scroll_song_text)
        self.song_label.clicked.connect(self.cycle_song_scroll_mode)

        self.artist_label = QtWidgets.QLabel("", self.content_widget)
        self.artist_label.setStyleSheet("color: #fff; font-size: 14px; border: 1px solid #ff00ff; background: #222;")
        self.artist_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.artist_label.setWordWrap(True)
        self.info_layout.addWidget(self.artist_label)
        self.album_label = QtWidgets.QLabel("", self.content_widget)
        self.album_label.setStyleSheet("color: #b3b3b3; font-size: 12px; border: 1px solid #ffff00; background: #222;")
        self.album_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.album_label.setWordWrap(True)
        self.info_layout.addWidget(self.album_label)
        self.info_layout.addStretch()
        self.content_layout.addLayout(self.info_layout)
        self.content_layout.setStretch(0, 0)
        self.content_layout.setStretch(1, 1)

        self.main_layout.addWidget(self.content_widget)


        # Controls layout
        self.controls_widget = QtWidgets.QWidget(self)
        self.controls_layout = QtWidgets.QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(10)

        self.play_btn = QtWidgets.QPushButton("⏯", self.controls_widget)
        self.play_btn.setToolTip("Play/Pause")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setStyleSheet(self.button_style())
        self.play_btn.clicked.connect(self.toggle_play)
        self.controls_layout.addWidget(self.play_btn)

        self.prev_btn = QtWidgets.QPushButton("⏮", self.controls_widget)
        self.prev_btn.setToolTip("Previous Track")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet(self.button_style())
        self.prev_btn.clicked.connect(self.prev_track)
        self.controls_layout.addWidget(self.prev_btn)

        self.next_btn = QtWidgets.QPushButton("⏭", self.controls_widget)
        self.next_btn.setToolTip("Next Track")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet(self.button_style())
        self.next_btn.clicked.connect(self.next_track)
        self.controls_layout.addWidget(self.next_btn)

        self.vol_btn = QtWidgets.QPushButton("🔊", self.controls_widget)
        self.vol_btn.setToolTip("Volume")
        self.vol_btn.setFixedSize(32, 32)
        self.vol_btn.setStyleSheet(self.button_style())
        self.vol_btn.clicked.connect(self.toggle_volume_slider)
        self.controls_layout.addWidget(self.vol_btn)

        self.dark_mode_btn = QtWidgets.QPushButton("🌙", self.controls_widget)
        self.dark_mode_btn.setToolTip("Toggle Dark Mode")
        self.dark_mode_btn.setFixedSize(32, 32)
        self.dark_mode_btn.setStyleSheet(self.button_style())
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)
        self.controls_layout.addWidget(self.dark_mode_btn)

        self.hide_controls_btn = QtWidgets.QPushButton("⬆", self.controls_widget)
        self.hide_controls_btn.setToolTip("Hide Controls")
        self.hide_controls_btn.setFixedSize(32, 32)
        self.hide_controls_btn.setStyleSheet(self.button_style())
        self.hide_controls_btn.clicked.connect(self.toggle_controls_visibility)
        self.controls_layout.addWidget(self.hide_controls_btn)

        # --- Group color controls in a single layout ---
        self.color_controls_widget = QtWidgets.QWidget(self.controls_widget)
        self.color_controls_layout = QtWidgets.QHBoxLayout(self.color_controls_widget)
        self.color_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.color_controls_layout.setSpacing(2)

        self.btn_color_btn = QtWidgets.QPushButton("🎨", self.color_controls_widget)
        self.btn_color_btn.setToolTip("Change Button Color")
        self.btn_color_btn.setFixedSize(32, 32)
        self.btn_color_btn.setStyleSheet(self.button_style())
        self.btn_color_btn.clicked.connect(self.pick_button_color)
        self.color_controls_layout.addWidget(self.btn_color_btn)


        # Removed transparency slider for button color


        # Remove the text color button and transparency slider for text
        # (Transparency slider for button color remains)

        self.controls_layout.addWidget(self.color_controls_widget)

        # Volume slider below controls (hidden by default)
        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.vol_slider.setMinimum(0)
        self.vol_slider.setMaximum(100)
        self.vol_slider.setValue(50)
        self.vol_slider.setFixedWidth(120)
        self.vol_slider.setStyleSheet("QSlider::handle:horizontal { background: #1DB954; border: 1px solid #191414; width: 12px; } QSlider::groove:horizontal { height: 6px; background: #444; border-radius: 3px; }")
        self.vol_slider.hide()
        self.vol_slider.sliderReleased.connect(self.set_volume_from_slider)

        self.main_layout.addWidget(self.controls_widget)
        self.main_layout.addWidget(self.vol_slider)


    # Removed update_button_transparency method

        # Floating show-controls button (hidden by default)
        self.show_controls_btn = QtWidgets.QPushButton("⬇", self)
        self.show_controls_btn.setToolTip("Show Controls")
        self.show_controls_btn.setFixedSize(32, 32)
        self.show_controls_btn.setStyleSheet(self.button_style())
        self.show_controls_btn.move(self.width() - 40, self.height() - 40)
        self.show_controls_btn.hide()
        self.show_controls_btn.clicked.connect(self.toggle_controls_visibility)

        self.controls_visible = True
        self.dark_mode = True
        self.button_color = "#282828"
        self.button_fg = "#fff"
        self.text_color = "#fff"


        self.update_song_signal.connect(self.set_song)

        # Use QTimer for periodic updates in the main thread
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_song)
        self.update_timer.start(2000)  # 2 seconds

        # Drag support
        self.offset = None
        self.title_bar.mousePressEvent = self.mousePressEvent
        self.title_bar.mouseMoveEvent = self.mouseMoveEvent

        # Resize event to reposition floating button
        self.resizeEvent = self.on_resize

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.offset)
            event.accept()

    def toggle_controls_visibility(self):
        try:
            self.controls_visible = not getattr(self, 'controls_visible', True)
            self.controls_widget.setVisible(self.controls_visible)
            self.hide_controls_btn.setText("⬇" if not self.controls_visible else "⬆")
            if hasattr(self, 'show_controls_btn'):
                self.show_controls_btn.setVisible(not self.controls_visible)
        except Exception as e:
            self.show_error(f"Hide UI error: {e}")

    def on_resize(self, event):
        # Move floating show-controls button to bottom right
        self.show_controls_btn.move(self.width() - 40, self.height() - 40)
        event.accept()

    def button_style(self):
        return f"QPushButton {{ color: {self.button_fg}; background: {self.button_color}; border-radius: 16px; font-size: 18px; }} QPushButton:hover {{ background: #1DB954; color: #191414; }}"

    def update_button_colors(self):
        # Only include buttons that exist and are not None
        button_list = [
            getattr(self, 'play_btn', None),
            getattr(self, 'prev_btn', None),
            getattr(self, 'next_btn', None),
            getattr(self, 'vol_btn', None),
            getattr(self, 'dark_mode_btn', None),
            getattr(self, 'hide_controls_btn', None),
            getattr(self, 'btn_color_btn', None),
            getattr(self, 'show_controls_btn', None)
        ]
        for btn in button_list:
            if btn is not None:
                btn.setStyleSheet(self.button_style())

    def show_error(self, message):
        self.song_label.setText(f"Error: {message}")
        self.song_label.full_text = f"Error: {message}"
        self.song_scroll_timer.stop()
        # Write error to log file
        try:
            with open("error_log.txt", "a", encoding="utf-8") as f:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def pick_button_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            # Keep current alpha
            alpha = QtGui.QColor(self.button_color).alpha() if 'rgba' in self.button_color else 255
            col = color
            col.setAlpha(alpha)
            rgba = f"rgba({col.red()},{col.green()},{col.blue()},{col.alpha()/255:.2f})"
            self.button_color = rgba
            self.update_button_colors()

    def pick_text_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()
            self.update_text_colors()

    def update_text_colors(self):
        self.song_label.setStyleSheet(f"color: {self.text_color}; font-size: 18px; font-weight: bold;")
        self.artist_label.setStyleSheet(f"color: {self.text_color}; font-size: 14px;")
        self.album_label.setStyleSheet(f"color: {self.text_color}; font-size: 12px;")
        self.title_label.setStyleSheet(f"color: {self.text_color}; font-size: 14px; font-weight: bold;")
    def toggle_volume_slider(self):
        if self.vol_slider.isVisible():
            self.vol_slider.hide()
        else:
            # Set slider to current Spotify volume if possible
            try:
                current = self.sp.current_playback()
                if current and "device" in current:
                    vol = current["device"]["volume_percent"]
                    self.vol_slider.setValue(vol)
            except Exception:
                pass
            self.vol_slider.show()

    def set_volume_from_slider(self):
        try:
            vol = self.vol_slider.value()
            # Defensive: ensure vol is int and in range
            if not isinstance(vol, int):
                vol = int(vol)
            if vol < 0 or vol > 100:
                self.log_error(f"Volume out of range: {vol}")
                self.show_error("Volume out of range (0-100)")
                return
            try:
                self.sp.volume(vol)
            except Exception as e:
                self.log_error(f"Spotify API error in set_volume_from_slider: {e}")
                self.show_error("Failed to set volume. Is Spotify running?")
                return
            self.update_song()
        except Exception as e:
            self.log_error(f"set_volume_from_slider outer error: {e}")
            self.show_error(str(e))
    def toggle_dark_mode(self):
        try:
            self.dark_mode = not getattr(self, 'dark_mode', True)
            if self.dark_mode:
                self.setStyleSheet("background-color: #191414; border-radius: 15px;")
                self.title_bar.setStyleSheet("background: rgba(25,20,20,0.7); border-radius: 8px;")
            else:
                self.setStyleSheet("background-color: #f5f5f5; border-radius: 15px;")
                self.title_bar.setStyleSheet("background: rgba(255,255,255,0.7); border-radius: 8px;")
            self.update_text_colors()
        except Exception as e:
            self.show_error(f"Dark mode error: {e}")

    def toggle_play(self):
        try:
            current = self.sp.current_playback()
            if current and current.get("is_playing"):
                self.sp.pause_playback()
            else:
                self.sp.start_playback()
            self.update_song()
        except Exception as e:
            self.show_error(str(e))

    def next_track(self):
        try:
            if self.sp is not None:
                self.sp.next_track()
                self.update_song()
            else:
                self.show_error("Spotify client not initialized.")
        except Exception as e:
            self.log_error(f"next_track error: {e}")
            self.show_error(f"Next track error: {e}")

    def prev_track(self):
        try:
            if self.sp is not None:
                self.sp.previous_track()
                self.update_song()
            else:
                self.show_error("Spotify client not initialized.")
        except Exception as e:
            self.log_error(f"prev_track error: {e}")
            self.show_error(f"Previous track error: {e}")


    # Removed update_loop; replaced with QTimer in __init__

    def update_song(self):
        try:
            current = None
            try:
                current = self.sp.current_playback()
            except Exception as e:
                self.log_error(f"Spotify API error in current_playback: {e}")
            # Log the current playback dict for debugging
            try:
                with open("error_log.txt", "a", encoding="utf-8") as f:
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[DEBUG {timestamp}] current_playback: {repr(current)}\n")
            except Exception:
                pass
            # --- Revised logic for extracting song, artist, album, cover_url ---
            song = "Unknown Song"
            artist = "Unknown Artist"
            album = "Unknown Album"
            cover_url = ""
            item = None
            if current and isinstance(current, dict):
                item = current.get("item")
            if item and isinstance(item, dict):
                # Song name
                song = item.get("name") or "Unknown Song"
                # Artist(s)
                artists = item.get("artists")
                if artists and isinstance(artists, list):
                    artist_names = []
                    for a in artists:
                        if isinstance(a, dict):
                            n = a.get("name")
                            if n:
                                artist_names.append(str(n))
                    if artist_names:
                        artist = ", ".join(artist_names)
                # Album
                album_info = item.get("album")
                if album_info and isinstance(album_info, dict):
                    album = album_info.get("name") or "Unknown Album"
                    images = album_info.get("images")
                    if images and isinstance(images, list):
                        for img in images:
                            if isinstance(img, dict) and img.get("url"):
                                cover_url = img["url"]
                                break
            # Update volume slider to match current device
            try:
                device = current.get("device") if current and isinstance(current, dict) else None
                if device and isinstance(device, dict) and device.get("is_active") and device.get("volume_percent") is not None:
                    self.vol_slider.setEnabled(True)
                    self.vol_slider.setValue(device.get("volume_percent", 50))
                else:
                    self.vol_slider.setEnabled(False)
            except Exception as e:
                self.log_error(f"Volume slider update error: {e}")
                self.vol_slider.setEnabled(False)
            # Log what will be emitted
            self.log_error(f"update_song emit: song={song}, artist={artist}, album={album}, cover_url={cover_url}")
            self.update_song_signal.emit(song, artist, album, cover_url)
        except Exception as e:
            self.log_error(f"update_song outer error: {e}")
            self.update_song_signal.emit("Error", str(e), "", "")

    @QtCore.pyqtSlot(str, str, str, str)
    def set_song(self, song, artist, album, cover_url):
        # Always show something, even if error or missing data
        song = song if song else "Unknown Song"
        artist = artist if artist else "Unknown Artist"
        album = album if album else "Unknown Album"
        # Prioritize showing song and album cover, even if other data is missing
        try:
            self.song_label.setText(str(song))
            self.song_label.full_text = str(song)
            self.song_label.setMinimumHeight(28)
            self.song_label.setMaximumHeight(40)
            self.song_label.setStyleSheet(f"color: {self.text_color}; font-size: 18px; font-weight: bold; background: #222;")
            self.song_label.show()
            self.song_label.repaint()
            self.song_scroll_offset = 0
            self.update_song_scroll_display()
            self.artist_label.setText(str(artist))
            self.album_label.setText(str(album))
            self.update_text_colors()
            # Album cover loading with error handling
            if cover_url:
                try:
                    resp = requests.get(cover_url, timeout=5)
                    resp.raise_for_status()
                    img = QtGui.QImage()
                    if img.loadFromData(resp.content):
                        pixmap = QtGui.QPixmap(img).scaled(
                            100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                        )
                        self.album_cover.setPixmap(pixmap)
                        self.album_cover.setToolTip(cover_url)
                    else:
                        self.album_cover.clear()
                        self.album_cover.setToolTip("[Failed to load image data]")
                        self.song_label.setText(f"{song} (Cover failed)")
                except Exception as e:
                    self.album_cover.clear()
                    self.album_cover.setToolTip(f"[Album cover error: {e}]")
                    self.song_label.setText(f"{song} (Cover error)")
            else:
                self.album_cover.clear()
                self.album_cover.setToolTip("[No cover URL]")
                self.song_label.setText(f"{song} (No cover)")
        except Exception as e:
            self.song_label.setText(f"Error: {e}")
            self.album_cover.clear()
            self.album_cover.setToolTip(f"[Error: {e}]")

    def log_error(self, message):
        # Write error to log file with timestamp
        try:
            with open("error_log.txt", "a", encoding="utf-8") as f:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[LOG {timestamp}] {message}\n")
        except Exception:
            pass

    def cycle_song_scroll_mode(self):
        self.song_scroll_mode = (self.song_scroll_mode + 1) % 3
        if self.song_scroll_mode == 0:
            self.song_scroll_timer.stop()
            self.song_scroll_offset = 0
            self.update_song_scroll_display()
        else:
            self.song_scroll_timer.start(60)

    def scroll_song_text(self):
        text = getattr(self.song_label, 'full_text', self.song_label.text())
        label_width = self.song_label.width()
        font_metrics = self.song_label.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text)
        if text_width <= label_width:
            self.song_scroll_timer.stop()
            self.song_label.setText(text)
            return
        if self.song_scroll_mode == 1:  # scroll left
            self.song_scroll_offset += 2
            if self.song_scroll_offset > text_width:
                self.song_scroll_offset = 0
        elif self.song_scroll_mode == 2:  # scroll right
            self.song_scroll_offset -= 2
            if self.song_scroll_offset < -label_width:
                self.song_scroll_offset = text_width
        self.update_song_scroll_display()

    def update_song_scroll_display(self):
        text = getattr(self.song_label, 'full_text', self.song_label.text())
        label_width = self.song_label.width()
        font_metrics = self.song_label.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text)
        if text_width <= label_width or self.song_scroll_mode == 0:
            self.song_label.setText(text)
        else:
            # Show a substring that fits in the label
            offset = self.song_scroll_offset
            if self.song_scroll_mode == 2:  # right
                offset = text_width - abs(offset)
            start = max(0, int(offset / font_metrics.averageCharWidth()))
            chars_fit = int(label_width / font_metrics.averageCharWidth())
            display = text[start:start+chars_fit]
            self.song_label.setText(display)


def main():
    # Determine a safe cache path for Spotipy token
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller .exe
        cache_path = os.path.join(os.path.dirname(sys.executable), '.cache')
    else:
        cache_path = os.path.abspath('.cache')

    try:
        auth_manager = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            open_browser=True,  # Always open browser for auth, avoids input()
            cache_path=cache_path,
        )
        sp = Spotify(auth_manager=auth_manager)
    except Exception as e:
        # Log and show error if authentication fails
        with open("error_log.txt", "a", encoding="utf-8") as f:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[AUTH ERROR {timestamp}] {e}\n")
        QtWidgets.QMessageBox.critical(None, "Spotify Auth Error", f"Failed to authenticate with Spotify.\n\n{e}")
        sys.exit(1)
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
    window = SpotifyDisplay(sp)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
