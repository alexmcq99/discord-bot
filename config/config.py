from configparser import ConfigParser
from dotenv import load_dotenv
import os

class Config():
    def __init__(self, file):
        # Get api tokens from .env
        load_dotenv()
        self.discord_token = os.getenv("discord_token")
        self.spotipy_client_id = os.getenv("spotipy_client_id")
        self.spotipy_client_secret = os.getenv("spotipy_client_secret")
        
        # Parse config file
        config_parser = ConfigParser()
        config_parser.read(file)

        self.reset_music = config_parser.getboolean("Parameters", "ResetMusic", fallback=False)
        self.reset_stats = config_parser.getboolean("Parameters", "ResetStats", fallback=False)

        self.duration_limit = config_parser.getint("Parameters", "DurationLimit")
        self.max_shown_songs = config_parser.getint("Parameters", "MaxShownSongs")
        self.spotify_song_limit = config_parser.getint("Parameters", "SpotifySongLimit")
        self.inactivity_timeout = config_parser.getint("Parameters", "InactivityTimeout")

        self.music_path = config_parser.get("Paths", "MusicPath")
        self.song_file = config_parser.get("Paths", "SongFile")
        self.user_file = config_parser.get("Paths", "UserFile")
        self.ffmpeg_path = config_parser.get("Paths", "FfmpegPath")