from configparser import ConfigParser
from dotenv import load_dotenv
import os

class Config():
    SONGS_FILE_NAME = "songs.csv"
    SONG_REQUESTS_FILE_NAME = "song_requests.csv"
    SONG_PLAYS_FILE_NAME = "song_plays.csv"

    def __init__(self, file):
        # Get api tokens from .env
        load_dotenv()
        self.discord_token = os.getenv("discord_token")
        self.spotipy_client_id = os.getenv("spotipy_client_id")
        self.spotipy_client_secret = os.getenv("spotipy_client_secret")
        
        # Parse config file
        config_parser = ConfigParser(inline_comment_prefixes=(";",))
        config_parser.read(file)

        self.reset_music: bool = config_parser.getboolean("Parameters", "ResetMusic", fallback=False)
        self.reset_stats: bool = config_parser.getboolean("Parameters", "ResetStats", fallback=False)

        self.data_dir: str = config_parser.get("Parameters", "DataDir", fallback="data")
        self.songs_file_path: str = os.path.join(self.data_dir, self.__class__.SONGS_FILE_NAME)
        self.song_requests_file_path: str = os.path.join(self.data_dir, self.__class__.SONG_REQUESTS_FILE_NAME)
        self.song_plays_file_path: str = os.path.join(self.data_dir, self.__class__.SONG_PLAYS_FILE_NAME)

        self.duration_limit = config_parser.getint("Parameters", "DurationLimit")
        self.max_shown_songs = config_parser.getint("Parameters", "MaxShownSongs")
        self.spotify_song_limit = config_parser.getint("Parameters", "SpotifySongLimit")
        self.inactivity_timeout = config_parser.getint("Parameters", "InactivityTimeout")