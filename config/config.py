from dotenv import load_dotenv
import os
import yaml

class Config():
    def __init__(self, file_name):
        # Get api tokens from .env
        load_dotenv()
        self.discord_token: str = os.getenv("discord_token")
        self.spotipy_client_id: str = os.getenv("spotipy_client_id")
        self.spotipy_client_secret: str = os.getenv("spotipy_client_secret")

        try:
            with open(file_name) as config_file:
                config_data: dict = yaml.safe_load(config_file)
        except yaml.YAMLError as error:
            print(error)

        self.reset_database: bool = config_data.get("reset_database", False)

        self.data_dir: str = config_data.get("data_dir", "data")
        self.database_file_path: str = os.path.join(self.data_dir, "usage.db")

        self.figure_dir: str = config_data.get("figure_dir", "figures")

        self.max_shown_songs: int = config_data.get("max_shown_songs", 10)
        self.spotify_song_limit = config_data.get("spotify_song_limit", 100)
        self.inactivity_timeout: int = config_data.get("inactivity_timeout", 600)
        
        self.get_usage_graph_with_stats: bool = config_data.get("get_usage_graph_with_stats")
    
    def __repr__(self) -> str:
        return f"Config({', '.join([f'{key!r}: {value!r}' for key, value in self.__dict__.items()])})"