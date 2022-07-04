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
from unidecode import unidecode
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

# Read downloaded songs file
# Create the file and return an empty dictionary if it doesn't exist
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

# Write a song's metadata to the downloaded songs file after it's downloaded
def write_downloaded_song(song_file, row):
    with open(song_file, mode="a", newline="", encoding="utf-8", errors="ignore") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# Read a stats file
# Return an empty dictionary if not found
def read_stats(stats_file):
    try:
        with open(stats_file) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        data = {}
    except Exception as e:
        print("Unexpected error in reading file: " + str(e))
    
    return data

# Write stats back to disk
# Done when bot exits, stats are stored in dictionaries while running
def write_stats(stats_file, stats):
    with open(stats_file, "w") as f:
        json.dump(stats, f)

# get api tokens from .env
load_dotenv()
DISCORD_TOKEN = os.getenv("discord_token")
SPOTIPY_CLIENT_ID = os.getenv("spotipy_client_id")
SPOTIPY_CLIENT_SECRET = os.getenv("spotipy_client_secret")

# constants
DURATION_LIMIT = 1200 # Any videos longer than this (20 minutes in seconds) will not be downloaded
MAX_SHOWN_SONGS = 10 # The maximum number of songs to show when displaying the song queue

# paths
MUSIC_PATH = "music" # Directory where music files are stored
SONG_FILE = "downloaded_songs.csv" # File with metadata on downloaded songs
USER_STATS_FILE = "user_stats.json" # File with stats grouped by user
SONG_STATS_FILE = "song_stats.json" # File with stats grouped by song

# Create directory if it doesn't exist
if not os.path.exists(MUSIC_PATH):
    os.makedirs(MUSIC_PATH)

# Read files into dictionaries
downloaded_songs = read_downloaded_songs(SONG_FILE)
user_stats = read_stats(USER_STATS_FILE)
song_stats = read_stats(SONG_STATS_FILE)

# Spotify credentials and object
creds = SpotifyClientCredentials(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET)
spotify = spotipy.Spotify(client_credentials_manager=creds)

# make bot
intents = discord.Intents().default()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='-',intents=intents)

# Instantiate song queue and other relevant global variables
song_queue = deque([])
is_looping = False
curr_song_id = None

# Spotify

def is_spotify_url(url):
    query = urlparse(url)
    return query.hostname == "open.spotify.com"

# Return list of search queries for each song in an album or playlist
# Returns a list with a single search query for a single song
# Search queries are lists of words, so this method returns a list of lists of strings
def get_spotify_info(url):
    query = urlparse(url)
    _, type, id = query.path.split("/")
    search_list = []
    if type == "album":
        result = spotify.album(id)
        search_list = [track['artists'][0]['name'].split() + "-" + track['name'].split() for track in result['tracks']['items']]
    elif type == "track":
        result = spotify.track(id)
        search_list = [result['artists'][0]['name'].split() + "-" + result['name'].split()]
    elif type == "playlist":
        result = spotify.playlist_tracks(id, limit=50)
        search_list = [item['track']['artists'][0]['name'].split() + ["-"] + item['track']['name'].split() for item in result['items']]
    return search_list

# YouTube

# Returns youtube video id given a search query
# Will return the first video in the search results
# search_query is a list of words, like you would type when looking up a video
def yt_search(search_query):
    search_query = [unidecode(s) for s in search_query]
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

# Returns youtube video url given its id
def yt_id_to_url(id):
    return "https://www.youtube.com/watch?v=" + id

# Returns a youtube video id given its url
def yt_url_to_id(url, ignore_playlist=True):
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

# Retrieves song metadata and stores it in the downloaded_songs dictionary
# Will optionally download the song file itself (since it's costly)
def get_song(id, download=True):
    yt = None
    if id in downloaded_songs: # Get metadata if we already have it
        title, file_path, duration, downloaded = downloaded_songs[id]
    else: # Otherwise, retrieve it
        yt = YouTube(yt_id_to_url(id))
        title, duration = yt.title, yt.length
        file_path = None
        downloaded = False

    # Only download if we want to and haven't already downloaded it
    if download and not downloaded:
        if not yt:
            yt = YouTube(yt_id_to_url(id))
        stream = yt.streams.filter(only_audio=True).first()
        out_file = stream.download(output_path=MUSIC_PATH)
        base, _ = os.path.splitext(out_file)
        file_path = os.path.join(MUSIC_PATH, f"{base}.mp3")
        os.rename(out_file, file_path)
        downloaded = True

        # Write downloaded song metadata to downloaded songs file
        write_downloaded_song(SONG_FILE, [id, title, file_path, duration])
    
    data = (title, file_path, duration, downloaded)
    downloaded_songs[id] = data
    return data

# Bot commands

# Returns a boolean detailing its success joining a channel
@bot.command(name='join', help='Joins the voice channel')
async def join(ctx):
    # Can only join a voice channel if the author of the command is connected to one
    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.author.mention} is not connected to a voice channel.")
        return False
    else:
        channel = ctx.message.author.voice.channel
        if not ctx.voice_client:
            await channel.connect()
        elif channel != ctx.voice_client.channel:
            await ctx.voice_client.move_to(channel)
        return True


@bot.command(name='leave', aliases=['die'], help='Leaves the voice channel')
async def leave(ctx):
    global curr_song_id, is_looping
    voice_client = ctx.voice_client

    # Stops the music and clears the queue before disconnecting
    if voice_client and voice_client.is_connected():
        curr_song_id = None
        song_queue.clear()
        is_looping = False
        ctx.message.guild.voice_client.stop()
        await voice_client.disconnect()
    else:
        await ctx.send("The bot is not currently in a voice channel.")

# Recursive callback to play the next song
# Used by the "-play" command
# This is the function that actually downloads and plays the next song in the queue
# If something is already playing, this function won't do anything
def play_next(ctx):
    global curr_song_id, is_looping
    # If looping, take current song that just finished and add it back to the queue
    if is_looping and curr_song_id and not ctx.voice_client.is_playing():
        song_queue.append(curr_song_id)
    # If current song is finished and there's something queued, play it
    if len(song_queue) >= 1 and not ctx.voice_client.is_playing():
        curr_song_id = song_queue.popleft()
        title, file_path, _, _ = get_song(curr_song_id) # Downloads the song if not already downloaded
        asyncio.run_coroutine_threadsafe(ctx.send(f'**Now playing:** :notes: {title} :notes:'), loop=bot.loop)
        ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=file_path), after=lambda e: play_next(ctx))
    # No current song
    elif len(song_queue) == 0:
        curr_song_id = None

@bot.command(name='play', help='Plays a song -- can take in a youtube link or a search query for youtube')
async def play(ctx, *args):
    # The bot has to join a channel before playing a song
    joined = await join(ctx)
    if not joined:
        return

    if len(args) == 0:
        await ctx.send("No arguments provided.  Please provide a url or search query.")
        return
    
    search_queries = [] # List of search queries (lists of words) to look up songs on youtube
    songs_to_add = [] # List of songs to add to queue

    # Determine if arguments are a youtube url, spotify url, or search query
    url = args[0]
    yt_id = yt_url_to_id(url) # This yt id will be valid if given a url
    if yt_id: # We have a youtube url
        songs_to_add.append(yt_id)
    elif is_spotify_url(url): # We have a spotify url
        search_queries.extend(get_spotify_info(url))
    else: # We have a search query
        search_queries.append(args)
    
    # Do youtube search on search queries to get ids
    for query in search_queries:
        search_result = yt_search(query)
        if not search_result:
            await ctx.send("\"" + " ".join(query) + "\" did not yield any search results.")
        songs_to_add.append(search_result)

    for song_id in songs_to_add:
        # Get song metadata without downloading
        # We download just before playing the song to avoid downloading one song while playing another
        title, _, duration, _ = get_song(song_id, download=False)

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
        user_stats[ctx.author.mention][song_id] = user_stats[ctx.author.mention].get(song_id, 0) + 1

        # Update song stats
        song_stats[song_id] = song_stats.get(song_id, 0) + 1

        # Add to queue and play the next song
        song_queue.append(song_id)
        await ctx.send(f"Successfully added :notes: {title} :notes: to the queue.")
        play_next(ctx)

@bot.command(name='playall', help='Plays all downloaded songs')
async def playall(ctx):
    await join(ctx) # join the voice channel
    song_queue.extend(downloaded_songs.keys()) # Add all downloaded songs to the queue
    await ctx.send("Successfully added all downloaded songs to the queue.")
    play_next(ctx) # play the next song in the queue

@bot.command(name='loop', help='Loops the queue until used again')
async def loop(ctx):
    global is_looping, curr_song_id
    is_looping = not is_looping
    loop_msg = "Looping the queue until this command is used again." if is_looping else "No longer looping the queue."
    await ctx.send(loop_msg)

@bot.command(name='showqueue', aliases=['queue', 'status'], help='Shows the current queue and if looping is on.')
async def showqueue(ctx):
    global is_looping, curr_song_id
    loop_msg = f"The queue is {'' if is_looping else 'not '}looping.\n" # Display if the queue is looping
    curr_song_title = downloaded_songs[curr_song_id][0] if curr_song_id else 'None'
    curr_song_msg = f"Current song: {curr_song_title}\n" # Display the current song
    queue_count_msg = f"Number of songs in queue: {len(song_queue)}\n" # Display the length of the queue
    if len(song_queue) > 0: # Display only the first few songs
        queue_header = "Songs in queue:\n" if len(song_queue) <= MAX_SHOWN_SONGS else f"First {MAX_SHOWN_SONGS} songs:\n"
        queue_contents = "\n".join([f"{i}) {downloaded_songs[id][0]}" for i, id in enumerate(list(song_queue)[:MAX_SHOWN_SONGS], 1)])
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
    global curr_song_id
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        curr_song_title = downloaded_songs[curr_song_id][0]
        curr_song_id = None
        ctx.voice_client.stop()
        await ctx.send(f"Skipped :notes: {curr_song_title} :notes:")

@bot.command(name='clear', help='Clears the song queue')
async def clear(ctx):
    song_queue.clear()
    await ctx.send("Cleared the song queue.")

@bot.command(name='pause', help='Pauses the song')
async def pause(ctx):
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        ctx.voice_client.pause()
    
@bot.command(name='resume', aliases=['continue'], help='Resumes the song')
async def resume(ctx):
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        ctx.voice_client.resume()

@bot.command(name='stop', help='Stops the song and clears the queue')
async def stop(ctx):
    global curr_song_id
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        curr_song_id = None
        song_queue.clear()
        ctx.message.guild.voice_client.stop()
        await ctx.send("Stopped current song and cleared the song queue.")

@bot.command(name='shuffle', help='Shuffles the queue randomly')
async def shuffle(ctx):
    global song_queue
    temp = list(song_queue)
    random.shuffle(temp)
    song_queue = deque(temp)
    await ctx.send("Shuffled the queue.")

# Calculates global statistics based off of the stats dictionaries
def calculate_global_stats():
    global_stats = {}

    # Total requests
    global_stats["Total requests"] = sum(song_stats.values())

    # Total duration
    total_duration = sum([downloaded_songs[id][2] * song_stats[id] for id in song_stats])
    hours = total_duration // 3600
    mins = (total_duration % 3600) // 60
    seconds = (total_duration % 3600) % 60
    global_stats["Total duration of requested music"] = f"{str(hours).zfill(2)}:{str(mins).zfill(2)}:{str(seconds).zfill(2)}"

    # Most requested song
    if 
    most_popular_id = max(song_stats, key= lambda song: song_stats[song])
    most_popular_title = downloaded_songs[most_popular_id][0] if len(song_stats) > 0 else "N/A"
    num_plays = song_stats[most_popular_id] if len(song_stats) > 0 else 0
    global_stats["Most requested song"] = f"{most_popular} with {num_plays} requests"
    user_requests = {user: sum(user_stats[user].values()) for user in user_stats}
    most_active = max(user_requests, key= lambda user: user_requests[user]) if len(user_requests) > 0 else "N/A"
    num_requests = user_requests[most_active] if len(user_requests) > 0 else 0
    global_stats["Most active user"] = f"{most_active} with {num_requests} requests"
    return global_stats

@bot.command(name='stats', help='Retrieves usage statistics for the bot and its users')
async def stats(ctx):
    global_stats = calculate_global_stats()
    msg = "Global statistics:\n" + "\n".join([f"{name}: {value}" for name, value in global_stats.items()])
    await ctx.send(msg)

if __name__ == "__main__":
    # Register hooks to write the stats dictionaries to disk before exiting
    atexit.register(lambda *args: write_stats(USER_STATS_FILE, user_stats))
    atexit.register(lambda *args: write_stats(SONG_STATS_FILE, song_stats))

    # Run the bot
    bot.run(DISCORD_TOKEN)