"""Runs the music bot."""

import os

from config import Config
from music_bot import MusicBot


def main():
    """Loads the config and starts the music bot."""

    # Load config
    config_path = os.path.join("config", "config.yaml")
    config = Config(config_path)
    print(f"Config: {config!r}")

    print(f"Starting process id: {os.getpid()}")

    # Make bot
    music_bot = MusicBot(config)
    music_bot.run()


if __name__ == "__main__":
    main()
