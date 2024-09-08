import discord
from discord.ext import commands

from config import Config

from .music_cog import MusicCog


class MusicBot(commands.Bot):
    def __init__(
        self, config: Config, intents=discord.Intents().all(), **kwargs
    ) -> None:
        super().__init__(
            command_prefix=config.command_prefix, intents=intents, **kwargs
        )
        self.config: Config = config

    async def setup_hook(self) -> None:
        await self.add_cog(MusicCog(self.config))

    async def on_ready(self):
        print(f"Logged in as:\n{self.user.name}\n{self.user.id}")

    def run(self, **kwargs) -> None:
        super().run(self.config.discord_token, **kwargs)
