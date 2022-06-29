import asyncio
import atexit
import csv
import discord
from dotenv import load_dotenv
import os
import re
from collections import deque
from contextlib import suppress
from discord.ext import commands
import json
from pytube import YouTube
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

def read_downloaded_songs(song_file):
    try:
        with open(song_file, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            next(reader)
            data = {id: (title, path, int(duration), True) for id, title, path, duration in reader}
    except FileNotFoundError as e:
        write_downloaded_song(song_file, ["id", "title", "file_path", "duration"])
        data = {}
    except Exception as e:
        print("Unexpected error in reading file: " + str(e))

    return data

def write_downloaded_song(song_file, row):
    with open(song_file, mode="a", newline="", encoding="utf-8", errors="ignore") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def read_stats(stats_file):
    try:
        with open(stats_file) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        data = {}
    except Exception as e:
        print("Unexpected error in reading file: " + str(e))
    
    return data

def write_stats(stats_file, stats):
    with open(stats_file, "w") as f:
        json.dump(stats, f)

# get api token from .env
load_dotenv()
DISCORD_TOKEN = os.getenv("discord_token")
SPOTIPY_CLIENT_ID = os.getenv("spotipy_client_id")
SPOTIPY_CLIENT_SECRET = os.getenv("spotipy_client_secret")

creds = SpotifyClientCredentials(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET)
spotify = spotipy.Spotify(client_credentials_manager=creds)

# constants
MUSIC_PATH = "music"
DURATION_LIMIT = 1200 # in seconds, 20 minutes
TIMEOUT = 600 # in seconds, 10 minutes

# Forbidden song
STINKY_JACOB_ID = "ehLs7oGSE4g"

# Create directory if it doesn't exist
if not os.path.exists(MUSIC_PATH):
    os.makedirs(MUSIC_PATH)

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

USER_STATS_FILE = "user_stats.json"
user_stats = read_stats(USER_STATS_FILE)
print(user_stats)

SONG_STATS_FILE = "song_stats.json"
song_stats = read_stats(SONG_STATS_FILE)
print(song_stats)

song_queue = deque([])

is_looping = False

current_song = None

# youtube id to youtube url
def id_to_yt_url(id):
    return "https://www.youtube.com/watch?v=" + id

# search_query is a list of words
def yt_search(search_query):
    search_query = [s.encode('ascii', 'ignore').decode() for s in search_query]
    try:
        html = urlopen("https://www.youtube.com/results?search_query=" + "+".join(search_query))
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
    video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
    if len(video_ids) == 0:
        print(html.read().decode())
        return None
    id = video_ids[0]
    return id

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

def is_spotify_url(url):
    query = urlparse(url)
    return query.hostname == "open.spotify.com"

def get_spotify_info(url):
    query = urlparse(url)
    _, type, id = query.path.split("/")
    search_list = []
    if type == "album":
        result = spotify.album(id)
        search_list = [(track['artists'][0]['name'] + " " + track['name']).split() for track in result['tracks']['items']]
    elif type == "track":
        result = spotify.track(id)
        search_list = [(result['artists'][0]['name'] + " " + result['name']).split()]
    elif type == "playlist":
        result = spotify.playlist_tracks(id, limit=50)
        search_list = [(item['track']['artists'][0]['name'] + " " + item['track']['name']).split() for item in result['items']]
    return search_list

def get_song(id, download=True):
    yt = None
    if id in downloaded_songs:
        title, file_path, duration, downloaded = downloaded_songs[id]
    else:
        yt = YouTube(id_to_yt_url(id))
        title, duration = yt.title, yt.length
        file_path = os.path.join(MUSIC_PATH, f"{title}.mp3")
        downloaded = False

    if download and not downloaded:
        if not yt:
            yt = YouTube(id_to_yt_url(id))
        stream = yt.streams.filter(only_audio=True).first()
        out_file = stream.download(output_path=MUSIC_PATH)
        os.rename(out_file, file_path)
        downloaded = True
        write_downloaded_song(SONG_FILE, [id, title, file_path, duration])
    
    downloaded_songs[id] = (title, file_path, duration, downloaded)
    return title, file_path, duration, downloaded

# define bot commands
@bot.command(name='join', help='Joins the voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.author.mention} is not connected to a voice channel")
        return False
    else:
        channel = ctx.message.author.voice.channel
        if not ctx.voice_client:
            print("Joined a channel")
            await channel.connect()
        elif channel != ctx.voice_client.channel:
            print("Moved to a channel")
            await ctx.voice_client.move_to(channel)
        return True


@bot.command(name='leave', aliases=['die'], help='Leaves the voice channel')
async def leave(ctx):
    global current_song, is_looping
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_connected():
        current_song = None
        song_queue.clear()
        is_looping = False
        ctx.message.guild.voice_client.stop()
        await voice_client.disconnect()
    else:
        await ctx.send("Stop bullying me, I'm not in a voice channel :(")

# Recursive callback to play the next song
# Used by the "-play" command
def play_next(ctx):
    global current_song, is_looping
    # If looping, take current song that just finished and add it back to the queue
    if is_looping and current_song and not ctx.voice_client.is_playing():
        song_queue.append(current_song)
    # If current song is finished and there's something queued, play it
    if len(song_queue) >= 1 and not ctx.voice_client.is_playing():
        current_song = song_queue.popleft()
        title, file_path, _, _ = get_song(current_song)
        asyncio.run_coroutine_threadsafe(ctx.send(f'**Now playing:** :notes: {title} :notes:'), loop=bot.loop)
        ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=file_path), after=lambda e: play_next(ctx))
    # No current song
    elif len(song_queue) == 0:
        current_song = None

@bot.command(name='play', help='Plays a song -- can take in a youtube link or a search query for youtube')
async def play(ctx, *args):
    joined = await join(ctx)
    if not joined:
        return

    songs_to_add = []
    if len(args) == 0:
        await ctx.send("No arguments provided.  Please provide a url or search query.")
        return
    
    # Case for youtube url
    id, url = get_yt_id(args[0]), args[0]
    search_arguments = []
    if id:
        songs_to_add.append(id)
    elif is_spotify_url(url): # Spotify url
        await ctx.send(f'Please wait -- getting Spotify data')
        search_arguments.extend(get_spotify_info(url))
    else:
        search_arguments.append(args)

    await ctx.send(f'Please wait -- getting Youtube data')
    for search_args in search_arguments:
        search_result = yt_search(search_args)
        if not search_result:
            print("\"" + " ".join(search_args) + "\" did not yield any search results")
        songs_to_add.append(search_result)

    for id in songs_to_add:
        # Check for forbidden song
        if id == STINKY_JACOB_ID:
            await ctx.send(f"**Attention {ctx.author.mention}!**  You have requested a forbidden song.  Reflect on your transgressions.")
            await ctx.author.move_to(None)
            await ctx.author.edit(nick="Banned for forbidden song")
            continue

        # Get song metadata without downloading
        title, _, duration, _ = get_song(id, download=False)

        if duration > DURATION_LIMIT: # Check if song is too long
            duration_str = f"{str(DURATION_LIMIT // 60).zfill(2)}:{str(DURATION_LIMIT % 60).zfill(2)}"
            await ctx.send(f":notes: {title} :notes: is too long to send.  Please request something shorter than {duration_str}.")
            continue
        elif duration == 0: # Check if song is a livestream
            await ctx.send(f":notes: {title} :notes: is currently streaming live and cannot be downloaded.")
            continue

        # Update user stats
        if ctx.author.mention not in user_stats:
            user_stats[ctx.author.mention] = {}
        user_stats[ctx.author.mention][id] = user_stats[ctx.author.mention].get(id, 0) + 1

        # Update song stats
        song_stats[id] = song_stats.get(id, 0) + 1

        # Add to queue and play the next song
        song_queue.append(id)
        await ctx.send(f"Successfully added :notes: {title} :notes: to the queue.")
        play_next(ctx)

@bot.command(name='playall', help='Plays all downloaded songs')
async def playall(ctx):
    await join(ctx)
    song_queue.extend(downloaded_songs.keys())
    await ctx.send("Successfully added all downloaded songs to the queue.")
    play_next(ctx)

@bot.command(name='loop', help='Loops the queue until used again')
async def loop(ctx):
    global is_looping, current_song
    is_looping = not is_looping
    loop_msg = "Looping the queue until this command is used again." if is_looping else "No longer looping the queue."
    await ctx.send(loop_msg)

@bot.command(name='showqueue', aliases=['queue', 'status'], help='Shows the current queue and if looping is on.')
async def showqueue(ctx):
    global is_looping, current_song
    loop_msg = f"The queue is {'' if is_looping else 'not '}looping.\n"
    curr_song_msg = f"Current song: {downloaded_songs[current_song][0] if current_song else 'None'}\n"
    queue_count_msg = f"Number of songs in queue: {len(song_queue)}\n"
    MAX_SHOWN_SONGS = 10
    if len(song_queue) > 0:
        queue_header = "Songs in queue:\n" if len(song_queue) <= MAX_SHOWN_SONGS else f"First {MAX_SHOWN_SONGS} songs:\n"
        queue_contents = "\n".join([f"{i + 1}. {downloaded_songs[id][0]}" for i, id in enumerate(list(song_queue)[:MAX_SHOWN_SONGS])])
    else:
        queue_header, queue_contents = "", ""
    msg = loop_msg + curr_song_msg + queue_count_msg + queue_header + queue_contents
    await ctx.send(msg)

@bot.command(name='remove', aliases=['delete'], help='Removes the song at the given position in the queue (1 is first)')
async def remove(ctx, position):
    position = int(position)
    if position > 0 and position <= len(song_queue):
        title = downloaded_songs[song_queue[position - 1]][0]
        del song_queue[position - 1]
        await ctx.send(f":notes: {title} :notes: at position {position} has been removed from the queue.")
    else:
        await ctx.send(f"Invalid position.  Please choose a position between 1 and {len(song_queue)}, inclusive.  Use the command \"-showqueue\" to show the current queue.")

@bot.command(name='skip', help='Skips the current song')
async def skip(ctx):
    global current_song
    if ctx.voice_client.is_playing():
        title = downloaded_songs[current_song][0]
        current_song = None
        ctx.voice_client.stop()
        await ctx.send(f"Skipped :notes: {title} :notes:")
    else:
        await ctx.send("smh there's nothing to skip")

@bot.command(name='clear', help='Clears the song queue')
async def clear(ctx):
    song_queue.clear()
    await ctx.send("Cleared the song queue.")

@bot.command(name='pause', help='Pauses the song')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
    else:
        await ctx.send("smh stop trying to pause the song when nothing is playing")
    
@bot.command(name='resume', aliases=['continue'], help='Resumes the song')
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

@bot.command(name='shuffle', help='Shuffles the queue randomly')
async def shuffle(ctx):
    global song_queue
    temp = list(song_queue)
    random.shuffle(temp)
    song_queue = deque(temp)
    await ctx.send("Shuffled the queue.")

def calculate_global_stats():
    global_stats = {}
    global_stats["Total requests"] = sum(song_stats.values())
    total_duration = sum([downloaded_songs[id][2] * song_stats[id] for id in song_stats])
    hours = total_duration // 3600
    mins = (total_duration % 3600) // 60
    seconds = (total_duration % 3600) % 60
    global_stats["Total duration of requested music"] = f"{str(hours).zfill(2)}:{str(mins).zfill(2)}:{str(seconds).zfill(2)}"
    most_popular = max(song_stats, key= lambda song: song_stats[song])
    global_stats["Most requested song"] = f"{downloaded_songs[most_popular][0]} with {song_stats[most_popular]} requests"
    user_requests = {user: sum(user_stats[user].values()) for user in user_stats}
    most_active = max(user_requests, key= lambda user: user_requests[user])
    global_stats["Most active user"] = f"{most_active} with {user_requests[most_active]} requests"
    return global_stats

@bot.command(name='stats', help='Retrieves usage statistics for the bot and its users')
async def stats(ctx):
    global_stats = calculate_global_stats()
    msg = "Global statistics:\n" + "\n".join([f"{name}: {value}" for name, value in global_stats.items()])
    await ctx.send(msg)

@commands.Cog.listener()
async def on_voice_state_update(member, before, after):
    if not member.id == bot.user.id:
        return
    elif before.channel is None:
        voice = after.channel.guild.voice_client
        time = 0
        while True:
            await asyncio.sleep(1)
            time = time + 1
            if voice.is_playing() and not voice.is_paused():
                time = 0
            if time == TIMEOUT:
                print("DISCONNECTING")
                await voice.disconnect()
            if not voice.is_connected():
                break

if __name__ == "__main__":
    atexit.register(lambda *args: write_stats(USER_STATS_FILE, user_stats))
    atexit.register(lambda *args: write_stats(SONG_STATS_FILE, song_stats))
    bot.run(DISCORD_TOKEN)