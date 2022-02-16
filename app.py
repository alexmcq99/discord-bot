import asyncio
import csv
import discord
from dotenv import load_dotenv
import os
import re
import yt_dlp
from collections import deque
from contextlib import suppress
from discord.ext import commands
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

def read_downloaded_songs(song_file):
    try:
        with open(song_file, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            next(reader)
            downloaded_songs = {row[0]: tuple(row[1:]) for row in reader}
    except Exception as e:
        # print("Error in reading file: " + str(e))
        write_downloaded_song(song_file, ["id", "title", "file_path"])
        downloaded_songs = {}
    return downloaded_songs

def write_downloaded_song(song_file, row):
    with open(song_file, mode="a", newline="", encoding="utf-8", errors="ignore") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# get api token from .env
load_dotenv()
DISCORD_TOKEN = os.getenv("discord_token")

# path to music files
MUSIC_PATH = "music"

# Create directory if it doesn't exist
if not os.path.exists(MUSIC_PATH):
    os.makedirs(MUSIC_PATH)
    
# youtube download options
yt_dlp.utils.bug_reports_message = lambda: ''
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
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

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

is_looping = False

current_song = None

# search_query is a list of words
def yt_search(search_query):
    html = urlopen("https://www.youtube.com/results?search_query=" + "+".join(search_query))
    video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
    id = video_ids[0]
    url = "https://www.youtube.com/watch?v=" + id
    return id, url

# noinspection PyTypeChecker
def get_yt_id(url, ignore_playlist=True):
    # Examples:
    # - http://youtu.be/SA2iWivDJiE
    # - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    # - http://www.youtube.com/embed/SA2iWivDJiE
    # - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com', 'm.youtube.com'}:
        if not ignore_playlist:
        # use case: get playlist id not current video in playlist
            with suppress(KeyError):
                return parse_qs(query.query)['list'][0]
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/': return query.path.split('/')[1]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
   # returns None for invalid YouTube url

async def download_song(url):
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
    if 'entries' in data:
        # take first item from a playlist
        data = data['entries'][0]
    id, title, local_filename = data['id'], data['title'], ytdl.prepare_filename(data)
    local_filename = local_filename[:local_filename.rfind(".")] + ".mp3"
    file_path = os.path.join(MUSIC_PATH, local_filename)
    os.replace(local_filename, file_path)
    downloaded_songs[id] = (title, file_path)
    write_downloaded_song(SONG_FILE, [id, title, file_path])
    return title, file_path

def play_next(ctx):
    global current_song, is_looping
    # If looping, take current song that just finished and add it back to the queue
    if is_looping and current_song and not ctx.message.guild.voice_client.is_playing():
        song_queue.append(current_song)
        # print(len(song_queue))
    # If current song is finished and there's something queued, play it
    if len(song_queue) >= 1 and not ctx.message.guild.voice_client.is_playing():
        current_song = song_queue.popleft()
        title, file_path = current_song
        asyncio.run_coroutine_threadsafe(ctx.send(f'**Now playing:** :notes: {title} :notes:'), loop=bot.loop)
        ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=file_path), after=lambda e: play_next(ctx))
    # No current song
    elif len(song_queue) == 0:
        current_song = None

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

@bot.command(name='leave', help='Leaves the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("Stop bullying me, I'm not in a voice channel :(")

@bot.command(name='play', help='Plays a song')
async def play(ctx, *args):
    await join(ctx)
    try:
        ids = [get_yt_id(url) for url in args]
        valid_ids, valid_urls = [], []
        if len(args) == 0:
            await ctx.send("No arguments provided.  Please provide a url or search query.")
            return
        elif any(ids):
            await ctx.send("Please wait -- validating urls")
            for id, url in zip(ids, args):
                if id:
                    valid_ids.append(id)
                    valid_urls.append(url)
                else:
                    await ctx.send(f"{url} is not a valid youtube url.  Ignoring and processing other urls...")
        else:
            id, url = yt_search(args)
            valid_ids.append(id)
            valid_urls.append(url)
            # print(f"id: {id}, url: {url}")

        for id, url in zip(valid_ids, valid_urls):
            # Check if we've already downloaded the song, download it now if we haven't
            if id in downloaded_songs:
                title, file_path = downloaded_songs[id]
                # print("File exists, got info")
            else:
                await ctx.send(f'Please wait -- downloading song')
                title, file_path = await download_song(url)
                # print("File doesn't exist, downloaded it")
                
            song_queue.append((title, file_path))
            # print(song_queue)
            await ctx.send(f"Successfully added :notes: {title} :notes: to the queue.")
        
        play_next(ctx)
    except Exception as e:
        # print("THIS IS THE ERROR\n" + str(e))
        # print(type(e))
        await ctx.send("An error occurred.  I blame Devin.")

@bot.command(name='playall', help='Plays all downloaded songs')
async def playall(ctx):
    await join(ctx)
    song_queue.extend(downloaded_songs.values())
    # print(song_queue)
    await ctx.send("Successfully added all downloaded songs to the queue.")
    play_next(ctx)

@bot.command(name='loop', help='Loops the queue until used again')
async def loop(ctx):
    global is_looping, current_song
    is_looping = not is_looping
    loop_msg = "Looping the queue until this command is used again." if is_looping else "No longer looping the queue."
    await ctx.send(loop_msg)

@bot.command(name='showqueue', help='Shows the current queue and if looping is on.')
async def showqueue(ctx):
    global is_looping, current_song
    loop_msg = f"The queue is {'' if is_looping else 'not '}looping.\n"
    curr_song_msg = f"Current song: {current_song[0] if current_song else 'None'}\n"
    queue_count_msg = f"Number of songs in queue: {len(song_queue)}\n"
    # print(song_queue)
    MAX_SHOWN_SONGS = 10
    if len(song_queue) > 0:
        queue_header = "Songs in queue:\n" if len(song_queue) <= MAX_SHOWN_SONGS else f"First {MAX_SHOWN_SONGS} songs:\n"
        queue_contents = "\n".join([f"{i + 1}. {title}" for i, (title, _) in enumerate(list(song_queue)[:MAX_SHOWN_SONGS])])
    else:
        queue_header, queue_contents = "", ""
    msg = loop_msg + curr_song_msg + queue_count_msg + queue_header + queue_contents
    # print(f"length of message: {len(msg)}")
    await ctx.send(msg)

@bot.command(name='remove', help='Removes the song at the given position in the queue. (1 is first)')
async def remove(ctx, position):
    position = int(position)
    if position > 0 and position <= len(song_queue):
        title, _ = song_queue[position - 1]
        del song_queue[position - 1]
        await ctx.send(f":notes: {title} :notes: at position {position} has been removed from the queue.")
    else:
        await ctx.send(f"Invalid position.  Please choose a position between 1 and {len(song_queue)}, inclusive.  Use the command \"-showqueue\" to show the current queue.")

@bot.command(name='skip', help='Skips the current song')
async def skip(ctx):
    global current_song
    if ctx.message.guild.voice_client.is_playing():
        curr_song_title, _ = current_song
        current_song = None
        ctx.message.guild.voice_client.stop()
        await ctx.send(f"Skipped :notes: {curr_song_title} :notes:")
    else:
        await ctx.send("smh there's nothing to skip")

@bot.command(name='clear', help='Clears the song queue')
async def clear(ctx):
    song_queue.clear()
    await ctx.send("Cleared the song queue.")

@bot.command(name='pause', help='Pauses the song')
async def pause(ctx):
    if ctx.message.guild.voice_client.is_playing():
        ctx.message.guild.voice_client.pause()
    else:
        await ctx.send("smh stop trying to pause the song when nothing is playing")
    
@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    if ctx.message.guild.voice_client.is_paused():
        ctx.message.guild.voice_client.resume()
    else:
        await ctx.send("smh there's nothing to play")

@bot.command(name='stop', help='Stops the song and clears the queue')
async def stop(ctx):
    global current_song
    if ctx.message.guild.voice_client.is_playing():
        current_song = None
        song_queue.clear()
        ctx.message.guild.voice_client.stop()
        await ctx.send("Stopped current song and cleared the song queue.")
    else:
        await ctx.send("smh there's nothing to stop")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)