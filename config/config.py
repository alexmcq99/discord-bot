from configparser import ConfigParser
from dotenv import load_dotenv
import os

class Config():
    DATABASE_FILE_NAME = "usage.db"

    def __init__(self, file):
        # Get api tokens from .env
        load_dotenv()
        self.discord_token = os.getenv("discord_token")
        self.spotipy_client_id = os.getenv("spotipy_client_id")
        self.spotipy_client_secret = os.getenv("spotipy_client_secret")
        
        # Parse config file
        config_parser = ConfigParser(inline_comment_prefixes=(";",))
        config_parser.read(file)

        self.reset_database: bool = config_parser.getboolean("Parameters", "ResetDatabase", fallback=False)

        self.data_dir: str = config_parser.get("Parameters", "DataDir", fallback="data")
        self.database_file_path: str = os.path.join(self.data_dir, self.DATABASE_FILE_NAME)

        self.figure_dir: str = config_parser.get("Parameters", "FigureDir", fallback="figures")

        self.max_shown_songs: int = config_parser.getint("Parameters", "MaxShownSongs", fallback=10)
        self.spotify_song_limit = config_parser.getint("Parameters", "SpotifySongLimit", fallback=100)
        self.inactivity_timeout: int = config_parser.getint("Parameters", "InactivityTimeout", fallback=600)
        
        self.get_usage_graph_with_stats: bool = config_parser.getboolean("FeatureFlags", "GetUsageGraphWithFlags")