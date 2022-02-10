import asyncio
import csv
import discord
from dotenv import load_dotenv
import os
import youtube_dl
from urllib.parse import urlparse, parse_qs
from contextlib import suppress
from discord.ext import commands
from collections import deque

def read_downloaded_songs(song_file):
    try:
        with open(song_file, mode="r") as f:
            reader = csv.reader(f)
            next(reader)
            downloaded_songs = {row[0]: tuple(row[1:]) for row in reader}
    except Exception as e:
        print("Error in reading file: " + str(e))
        write_downloaded_song(song_file, ["id", "title", "file_path"])
        downloaded_songs = {}
    return downloaded_songs

def write_downloaded_song(song_file, row):
    with open(song_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# noinspection PyTypeChecker
def get_yt_id(url, ignore_playlist=True):
    # Examples:
    # - http://youtu.be/SA2iWivDJiE
    # - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    # - http://www.youtube.com/embed/SA2iWivDJiE
    # - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com'}:
        if not ignore_playlist:
        # use case: get playlist id not current video in playlist
            with suppress(KeyError):
                return parse_qs(query.query)['list'][0]
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/': return query.path.split('/')[1]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
   # returns None for invalid YouTube url
    
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

# Create directory if it doesn't exist
if not os.path.exists(MUSIC_PATH):
    os.makedirs(MUSIC_PATH)
    
# youtube download options
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': True,
    'quiet': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', # bind to ipv4 since ipv6 addresses cause issues sometimes
    'verbose': True,
    'rmcachedir': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]
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

SONG_FILE = "downloaded_songs.csv"
downloaded_songs = read_downloaded_songs(SONG_FILE)

song_queue = deque([])

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
            # song_queue.append(("Skeletor says \"wat\"", "music\Skeletor_says_wat-KBjhAqXg8MY.mp3"))
            # play_next(ctx)
    else:
        await ctx.send("Stop bullying me, I'm already in a voice channel :(")

@bot.command(name='leave', help='Leaves the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("Stop bullying me, I'm not in a voice channel :(")

async def download_song(url):
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
    if 'entries' in data:
        # take first item from a playlist
        data = data['entries'][0]
    id, title, local_filename = data['id'], data['title'], ytdl.prepare_filename(data)
    print(f"ID from data is {id}")
    local_filename = local_filename[:local_filename.rfind(".")] + ".mp3"
    file_path = os.path.join(MUSIC_PATH, local_filename)
    os.replace(local_filename, file_path)
    downloaded_songs[id] = (title, file_path)
    write_downloaded_song(SONG_FILE, [id, title, file_path])
    return title, file_path

def play_next(ctx):
    print("Here!")
    print(len(song_queue))
    if len(song_queue) >= 1:
        title, file_path = song_queue.popleft()
        asyncio.run_coroutine_threadsafe(ctx.send(f'**Now playing:** :notes: {title} :notes:'), loop=bot.loop)
        ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=file_path), after=lambda e: play_next(ctx))

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
        id = get_yt_id(url)
        print(f"This is the id from the url: {id}")
        if not ctx.message.guild.voice_client.is_playing():
            async with ctx.typing():
                # Check if we've already downloaded the song, download it now if we haven't
                print(f"id is {id}")
                if id in downloaded_songs:
                    title, file_path = downloaded_songs[id]
                    print("File exists, got info")
                else:
                    await ctx.send(f'Please wait...currently downloading music')
                    title, file_path = await download_song(url)
                    print("File doesn't exist, downloaded it")

                print("Playing audio")
                await ctx.send(f'**Now playing:** :notes: {title} :notes:')
                ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=file_path), after=lambda e: play_next(ctx))
        else:
            await ctx.send("Something is currently playing...added to queue")
            # Check if we've already downloaded the song, download it now if we haven't
            if id in downloaded_songs:
                title, file_path = downloaded_songs[id]
                print("File exists, got info")
            else:
                await ctx.send(f'Please wait...currently downloading music')
                title, file_path = await download_song(url)
                print("File doesn't exist, downloaded it")
            song_queue.append((title, file_path))
            print(song_queue)
            await ctx.send(f"Successfully added :notes: {title} :notes: to the queue.")
            if not ctx.message.guild.voice_client.is_playing():
                play_next(ctx)
    except Exception as e:
        print("THIS IS THE ERROR\n" + str(e))
        print(type(e))
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
        await ctx.send("smh there's nothing to stop")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)