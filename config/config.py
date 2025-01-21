import math
import os
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    def __init__(self, filename):
        # Get api tokens from .env
        load_dotenv()
        self.discord_token: str = os.getenv("discord_token")
        self.spotipy_client_id: str = os.getenv("spotipy_client_id")
        self.spotipy_client_secret: str = os.getenv("spotipy_client_secret")

        # Load config file
        config_data = self.load_config_file(filename)

        self.command_prefix: str = config_data.get("command_prefix", "-")

        # Stats and Usage data
        self.data_dir: str = config_data.get("data_dir", "data")
        self.usage_database_filename: str = config_data.get(
            "usage_database_filename", "usage.db"
        )
        self.usage_database_file_path: str = os.path.join(
            self.data_dir, self.usage_database_filename
        )
        self.figure_dir: str = config_data.get("figure_dir", "figures")
        self.enable_usage_database: bool = config_data.get(
            "enable_usage_database", False
        )
        self.reset_usage_database: bool = config_data.get("reset_usage_database", False)
        self.enable_stats_usage_graph: bool = config_data.get(
            "enable_stats_usage_graph", False
        )

        # Music
        self.max_displayed_songs: int = config_data.get("max_displayed_songs", 25)
        self.playlist_song_limit: int = config_data.get("spotify_song_limit", math.inf)
        self.yt_search_playlist_song_limit: int = config_data.get(
            "yt_search_playlist_song_limit", 10
        )
        self.inactivity_timeout: int = config_data.get("inactivity_timeout", 600)

        # Concurrency
        self.enable_multiprocessing: bool = config_data.get(
            "enable_multiprocessing", True
        )
        self.process_pool_workers: int = config_data.get("process_pool_workers", None)
        self.thread_pool_workers: int = config_data.get("thread_pool_workers", 4)

        print(f"spotify song limit: {self.playlist_song_limit}")

        # Youtube
        self.yt_cookies_file_name: str = "www.youtube.com_cookies.txt"
        self.yt_cookies_file_path: str = self.yt_cookies_file_name

    def load_config_file(self, filename: str) -> dict[str, Any]:
        try:
            with open(filename, encoding="utf-8") as config_file:
                config_data = yaml.safe_load(config_file)
        except yaml.YAMLError as error:
            print(error)
        return config_data

    def __repr__(self) -> str:
        config_flags_repr = ", ".join(
            [f"{key!r}={value!r}" for key, value in self.__dict__.items()]
        )
        return f"Config({config_flags_repr})"
