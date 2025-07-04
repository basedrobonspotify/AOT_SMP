import sys
# Disable input() to prevent lost sys.stdin errors in frozen/no-console mode
input = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("input() is disabled in this application"))
import threading
import time
import requests
from PyQt5 import QtWidgets, QtGui, QtCore
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Spotify API credentials (replace with your own)
CLIENT_ID = '672729ed0f564c70852192374450d1f5'
CLIENT_SECRET = '213f7be99528459fa4d21d10044d2830'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SCOPE = 'user-read-currently-playing user-read-playback-state'


class SpotifyDisplay(QtWidgets.QWidget):
    update_song_signal = QtCore.pyqtSignal(str, str, str, str)

    def __init__(self, sp):
        super().__init__()
        self.sp = sp
        self.setWindowTitle('Spotify Now Playing')
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setFixedSize(350, 120)
        self.setStyleSheet('background-color: #191414; border-radius: 15px;')

        self.album_cover = QtWidgets.QLabel(self)
        self.album_cover.setGeometry(10, 10, 100, 100)
        self.album_cover.setStyleSheet('border-radius: 10px;')

        self.song_label = QtWidgets.QLabel('Song', self)
        self.song_label.setGeometry(120, 20, 220, 30)
        self.song_label.setStyleSheet('color: #1DB954; font-size: 18px; font-weight: bold;')

        self.artist_label = QtWidgets.QLabel('Artist', self)
        self.artist_label.setGeometry(120, 55, 220, 25)
        self.artist_label.setStyleSheet('color: #fff; font-size: 14px;')

        self.album_label = QtWidgets.QLabel('Album', self)
        self.album_label.setGeometry(120, 80, 220, 20)
        self.album_label.setStyleSheet('color: #b3b3b3; font-size: 12px;')

        self.update_song_signal.connect(self.set_song)

        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def update_loop(self):
        while True:
            self.update_song()
            time.sleep(2)

    def update_song(self):
        try:
            current = self.sp.current_user_playing_track()
            if current and current.get('is_playing'):
                track = current['item']
                song = track['name']
                artist = ', '.join([a['name'] for a in track['artists']])
                album = track['album']['name']
                cover_url = track['album']['images'][0]['url']
                self.update_song_signal.emit(song, artist, album, cover_url)
            else:
                self.update_song_signal.emit('Not playing', '', '', '')
        except Exception as e:
            self.update_song_signal.emit('Error', str(e), '', '')

    def set_song(self, song, artist, album, cover_url):
        self.song_label.setText(song if song else "Unknown Song")
        self.artist_label.setText(artist if artist else "Unknown Artist")
        self.album_label.setText(album if album else "Unknown Album")
        if cover_url:
            img = QtGui.QImage()
            img.loadFromData(requests.get(cover_url).content)
            pixmap = QtGui.QPixmap(img).scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.album_cover.setPixmap(pixmap)
        else:
            self.album_cover.clear()


def main():
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,  # Always open browser for auth, avoids input()
        cache_path=".cache"
    )
    sp = Spotify(auth_manager=auth_manager)
    app = QtWidgets.QApplication(sys.argv)
    window = SpotifyDisplay(sp)
    # Ensure always-on-top after show
    window.show()
    window.setWindowFlags(window.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
    window.show()  # Call show again to apply the new window flag
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
