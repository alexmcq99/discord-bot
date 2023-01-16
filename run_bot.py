import atexit
import asyncio
from config.config import Config
import discord
from discord.ext import commands
from music_bot.cog import MusicCog
import os

config_path = os.path.join("config", "config.ini")
config = Config(config_path)

print("loaded config")

# Make bot
intents = discord.Intents().default()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='-',intents=intents)

print("made the bot")

@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))

bot.add_cog(MusicCog(bot, config))

print("Added the cog")

# @atexit.register
# async def close_bot():
#     await bot.close()

# Run the bot
if __name__ == "__main__":
    try:
        bot.loop.run_until_complete(bot.run(config.discord_token))
    except Exception as e:
        print("Exception occurred: " + str(e))
    finally:
        bot.loop.close()
    print("ran the bot")