import asyncio
from config import Config
import discord
from discord.ext import commands
from music_bot import MusicCog
import os
import platform

# Run the bot
if __name__ == "__main__":
    config_path = os.path.join("config", "config.ini")
    config = Config(config_path)

    print("loaded config")

    # Make bot
    intents = discord.Intents().all()
    client = discord.Client(intents=intents)
    bot = commands.Bot(command_prefix='-',intents=intents)

    print("made the bot")

    @bot.event
    async def on_ready():
        print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(bot.add_cog(MusicCog(bot, config)))

    print("Added the cog")
    try:
        bot.run(config.discord_token)
    except Exception as e:
        print("Exception occurred: " + str(e))
    print("ran the bot")