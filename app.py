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

# youtube download options
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', # bind to ipv4 since ipv6 addresses cause issues sometimes
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
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
    try :
        server = ctx.message.guild
        voice_channel = server.voice_client

        async with ctx.typing():
            with youtube_dl.YoutubeDL(ytdl_format_options) as ydl:
                ydl.download([url])
                title = ydl.extract_info(url, download=False)
            for file in os.listdir("./"):
                if file.endswith(".mp3"):
                    os.rename(file, 'song.mp3')
            voice_channel.play(discord.FFmpegPCMAudio("song.mp3"))
            voice_channel.volume = 100
            voice_channel.is_playing()
            voice_channel.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source="song.mp3"))
        await ctx.send(f'**Now playing:** {title}')
    except:
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