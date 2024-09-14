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

        self.reset_database: bool = config_data.get("reset_database", False)
        self.record_stats: bool = config_data.get("record_stats", False)
        self.get_usage_graph_with_stats: bool = config_data.get(
            "get_usage_graph_with_stats", False
        )

        self.data_dir: str = config_data.get("data_dir", "data")
        self.database_file_path: str = os.path.join(self.data_dir, "usage.db")
        self.figure_dir: str = config_data.get("figure_dir", "figures")

        self.max_shown_songs: int = config_data.get("max_shown_songs", 10)
        self.yt_search_song_limit: int = config_data.get("yt_search_song_limit", 5)
        self.spotify_song_limit: int = config_data.get("spotify_song_limit", 100)
        self.inactivity_timeout: int = config_data.get("inactivity_timeout", 600)

        self.enable_multiprocessing: bool = config_data.get(
            "enable_multiprocessing", True
        )
        self.process_pool_workers: int = config_data.get("process_pool_workers", None)
        self.thread_pool_workers: int = config_data.get("thread_pool_workers", 4)

        print(f"spotify song limit: {self.spotify_song_limit}")

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
