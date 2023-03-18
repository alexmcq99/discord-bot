import asyncio
import os

import discord
from discord.ext import commands

from config import Config
from music_bot import MusicCog

# Load config
config_path = os.path.join("config", "config.ini")
config = Config(config_path)

# Make bot
intents = discord.Intents().all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='-',intents=intents)

@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))

# Run bot
asyncio.run(bot.add_cog(MusicCog(bot, config)))
bot.run(config.discord_token)