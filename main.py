import sys
import logging
import urllib.request
from PyQt5 import QtWidgets, QtCore, QtGui
import spotipy
from spotipy.oauth2 import SpotifyOAuth

logging.basicConfig(
    filename="error_log.txt",
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s",
)


class SpotifyApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.sp = None
        self.initUI()
        self.initialize_spotify_client()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_song_info)
        self.timer.start(10000)

        self.scroll_timer = QtCore.QTimer()
        self.scroll_timer.timeout.connect(self.scroll_song_name)
        self.scroll_timer.start(200)

        self.scroll_position = 0

    def initialize_spotify_client(self):
        try:
            logging.debug("Initializing Spotify client...")
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id="c25e6b278c244232a226e612e72eca90",
                    client_secret="268fa3ad1b0743f78a6e1acd3b7cdbb4",
                    redirect_uri="http://127.0.0.1:8888/callback",
                    scope="user-read-playback-state user-modify-playback-state",
                )
            )
            logging.debug("Spotify client initialized successfully.")
            self.error_label.setText("")
        except Exception as e:
            logging.error(f"Error initializing Spotify client: {e}")
            self.show_error(f"Error initializing Spotify client: {e}")

    def initUI(self):
        self.setWindowTitle("Spotify Controller")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.song_label = QtWidgets.QLabel("Song: ")
        self.song_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.song_label, alignment=QtCore.Qt.AlignCenter)

        self.artist_label = QtWidgets.QLabel("Artist: ")
        self.artist_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.artist_label, alignment=QtCore.Qt.AlignCenter)

        self.album_label = QtWidgets.QLabel("Album: ")
        self.album_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.album_label, alignment=QtCore.Qt.AlignCenter)

        self.album_cover_label = QtWidgets.QLabel()
        self.album_cover_label.setAlignment(QtCore.Qt.AlignCenter)
        self.album_cover_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.album_cover_label.setMinimumSize(400, 400)
        self.layout.addWidget(self.album_cover_label, alignment=QtCore.Qt.AlignCenter)

        self.play_button = QtWidgets.QPushButton("Play/Pause")
        self.play_button.setToolTip("Play/Pause")
        self.play_button.clicked.connect(self.toggle_play)
        self.layout.addWidget(self.play_button)

        self.skip_backward_button = QtWidgets.QPushButton("Skip Backward")
        self.skip_backward_button.setToolTip("Skip Backward")
        self.skip_backward_button.clicked.connect(self.skip_backward)
        self.layout.addWidget(self.skip_backward_button)

        self.skip_forward_button = QtWidgets.QPushButton("Skip Forward")
        self.skip_forward_button.setToolTip("Skip Forward")
        self.skip_forward_button.clicked.connect(self.skip_forward)
        self.layout.addWidget(self.skip_forward_button)

        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.layout.addWidget(self.volume_slider)

        self.error_label = QtWidgets.QLabel("")
        self.layout.addWidget(self.error_label)

        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.theme_button = QtWidgets.QPushButton("Light Mode")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.layout.addWidget(self.theme_button)

        self.update_song_info()

        self.apply_theme("light")

    def show_error(self, message):
        self.error_label.setText(message)

    def toggle_play(self):
        if not self.sp:
            self.show_error("Spotify client not initialized.")
            return

        try:
            current = self.sp.current_playback()
            if current and current["is_playing"]:
                self.sp.pause_playback()
                self.play_button.setText("Play")
            else:
                self.sp.start_playback()
                self.play_button.setText("Pause")
            self.update_song_info()
        except Exception as e:
            logging.error(f"Error in toggle_play: {e}")
            self.show_error(f"Error in toggle_play: {e}")

    def skip_backward(self):
        if not self.sp:
            self.show_error("Spotify client not initialized.")
            return

        try:
            self.sp.previous_track()
            self.update_song_info()
        except Exception as e:
            logging.error(f"Error in skip_backward: {e}")
            self.show_error(f"Error in skip_backward: {e}")

    def skip_forward(self):
        if not self.sp:
            self.show_error("Spotify client not initialized.")
            return

        try:
            self.sp.next_track()
            self.update_song_info()
        except Exception as e:
            logging.error(f"Error in skip_forward: {e}")
            self.show_error(f"Error in skip_forward: {e}")

    def set_volume(self, value):
        if not self.sp:
            self.show_error("Spotify client not initialized.")
            return

        try:
            self.sp.volume(value)
        except Exception as e:
            logging.error(f"Error in set_volume: {e}")
            self.show_error(f"Error in set_volume: {e}")

    def update_song_info(self):
        if not self.sp:
            self.show_error("Spotify client not initialized.")
            return

        try:
            current = self.sp.current_playback()
            if current and current["item"]:
                song_name = current["item"]["name"]
                artist_name = ", ".join(
                    [artist["name"] for artist in current["item"]["artists"]]
                )
                album_name = current["item"]["album"]["name"]
                album_cover_url = current["item"]["album"]["images"][0]["url"]

                self.song_label.setText(f"Song: {song_name}")
                self.artist_label.setText(f"Artist: {artist_name}")
                self.album_label.setText(f"Album: {album_name}")

                self.load_album_cover(album_cover_url)

                self.scroll_position = 0
            else:
                self.song_label.setText("Song: ")
                self.artist_label.setText("Artist: ")
                self.album_label.setText("Album: ")
                self.album_cover_label.clear()
        except Exception as e:
            logging.error(f"Error in update_song_info: {e}")
            self.show_error(f"Error in update_song_info: {e}")

    def load_album_cover(self, url):
        try:
            data = urllib.request.urlopen(url).read()
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(data)
            self.album_cover_label.setPixmap(
                pixmap.scaled(
                    self.album_cover_label.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        except Exception as e:
            logging.error(f"Error loading album cover: {e}")
            self.show_error(f"Error loading album cover: {e}")

    def toggle_theme(self):
        if self.theme_button.text() == "Light Mode":
            self.apply_theme("dark")
            self.theme_button.setText("Dark Mode")
        else:
            self.apply_theme("light")
            self.theme_button.setText("Light Mode")

    def apply_theme(self, theme):
        if theme == "light":
            self.setStyleSheet(
                """
                QMainWindow {
                    background-color: #ffffff;
                }
                QLabel {
                    color: #000000;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #cccccc;
                }
                QSlider {
                    background-color: #ffffff;
                }
            """
            )
        elif theme == "dark":
            self.setStyleSheet(
                """
                QMainWindow {
                    background-color: #2e2e2e;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #444444;
                    color: #ffffff;
                    border: 1px solid #666666;
                }
                QSlider {
                    background-color: #2e2e2e;
                }
            """
            )

    def scroll_song_name(self):
        if self.song_label.text():
            text = self.song_label.text()
            if len(text) > 30:
                self.scroll_position += 1
                if self.scroll_position > len(text):
                    self.scroll_position = 0
                self.song_label.setText(
                    text[self.scroll_position :] + text[: self.scroll_position]
                )


def main():
    app = QtWidgets.QApplication(sys.argv)
    ex = SpotifyApp()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
