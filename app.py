import asyncio
import discord
from dotenv import load_dotenv
import os
import youtube_dl

from discord.ext import commands, tasks

# youtube download source object
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['title'] if stream else ytdl.prepare_filename(data)
        return filename

# get api token from .env
load_dotenv()
DISCORD_TOKEN = os.getenv("discord_token")

# path to music files
MUSIC_PATH = "music"

# youtube download options
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', # bind to ipv4 since ipv6 addresses cause issues sometimes
    'verbose': True
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# musicp player options
ffmpeg_options = {
    'options': '-vn'
}

# make bot
intents = discord.Intents().default()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='-',intents=intents)

# define bot commands
@bot.command(name='join', help='Joins the voice channel')
async def join(ctx):
    voice_client = ctx.message.guild.voice_client
    if not voice_client:
        if not ctx.message.author.voice:
            await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
            return
        else:
            channel = ctx.message.author.voice.channel
            await channel.connect()
    else:
        await ctx.send("Stop bullying me, I'm already in a voice channel :(")

@bot.command(name='leave', help='Leaves the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("Stop bullying me, I'm not in a voice channel :(")

@bot.command(name='play', help='Plays a song')
async def play(ctx,url):
    if not ctx.message.guild.voice_client:
        if not ctx.message.author.voice:
            await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
            return
        else:
            channel = ctx.message.author.voice.channel
            await channel.connect()
    try:
        vc = ctx.message.guild.voice_client
        async with ctx.typing():
            filename = await YTDLSource.from_url(url, loop=bot.loop)
            print(f"Filename: {filename}")
            info = ytdl.extract_info(url, download=False)
            id, title = info['id'], info['title']
            vc.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=filename))

            # Get metadata
            # info = ytdl.extract_info(url, download=False)
            # title, filename = info['title'], ytdl.prepare_filename(info)
            # print(f"Filename: {filename}")
            # Check if file already exists, download if it doesn't
            # full_path = os.path.join(MUSIC_PATH, filename)
            # if not os.path.exists(full_path):
            #     print("File doesn't exist, downloading it")
            #     ytdl.download([url])
            #     os.replace(filename, full_path)
            # Play music    
            # vc.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=full_path))
        await ctx.send(f'**Now playing:** {title}')
    except Exception as e:
        print("THIS IS THE ERROR\n" + str(e))
        await ctx.send("An error occurred.  I blame Devin.")

@bot.command(name='pause', help='Pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await voice_client.pause()
    else:
        await ctx.send("smh stop trying to pause the song when nothing is playing")
    
@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        await voice_client.resume()
    else:
        await ctx.send("smh there's nothing to play")

@bot.command(name='stop', help='Stops the song')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await voice_client.stop()
    else:
        await ctx.send("stopping :'(")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)