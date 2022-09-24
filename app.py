import argparse
import asyncio
import atexit
import discord
from dotenv import load_dotenv
import os
from collections import deque
from contextlib import suppress
from discord.ext import commands
import json
from pytube import Search, YouTube
import random
import shutil
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from unidecode import unidecode
from urllib.parse import urlparse, parse_qs

# Read a json file to a dictionary
# Return an empty dictionary if not found
def read_json_file(file):
    try:
        with open(file) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        data = {}
    except Exception as e:
        print("Unexpected error in reading file: " + str(e))
    
    return data

# Write data back to disk as json file
# Done when bot exits, data is stored in dictionaries while running
def write_json_file(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Set up argument parser
parser = argparse.ArgumentParser(description="Set up music bot")
parser.add_argument("--reset", action="store_true", help="Delete music and metadata before starting the bot")
args = parser.parse_args()

# Get api tokens from .env
load_dotenv()
DISCORD_TOKEN = os.getenv("discord_token")
SPOTIPY_CLIENT_ID = os.getenv("spotipy_client_id")
SPOTIPY_CLIENT_SECRET = os.getenv("spotipy_client_secret")

# Constants
DURATION_LIMIT = 1800 # Any videos longer than this (30 minutes in seconds) will not be downloaded
MAX_SHOWN_SONGS = 20 # The maximum number of songs to show when displaying the song queue
SPOTIFY_SONG_LIMIT = 100 # The maximum number of songs to add from a spotify playlist

# Paths
MUSIC_PATH = "music" # Directory where music files are stored
SONG_FILE = "song_data.json" # File with metadata on downloaded songs
USER_FILE = "user_data.json" # File with usage data grouped by user
FFMPEG_PATH = "ffmpeg"

# Reset downloaded files and metadata if applicable
if (args.reset):
    shutil.rmtree(MUSIC_PATH)
    os.remove(SONG_FILE)
    os.remove(USER_FILE)

# Create directory if it doesn't exist
if not os.path.exists(MUSIC_PATH):
    os.makedirs(MUSIC_PATH)

# Read files into dictionaries
song_data = read_json_file(SONG_FILE)
user_data = read_json_file(USER_FILE)

# Spotify credentials and object
creds = SpotifyClientCredentials(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET)
spotify = spotipy.Spotify(client_credentials_manager=creds)

# Make bot
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

# Return list of search queries (strings to search) for each song in an album or playlist
# If given a link to a track, returns a list with a single element
def get_spotify_info(url):
    query = urlparse(url)
    _, type, id = query.path.split("/")
    search_list = []
    if type == "album":
        result = spotify.album(id)
        search_list = [f"{track['artists'][0]['name']} - {track['name']}" for track in result['tracks']['items']]
    elif type == "track":
        result = spotify.track(id)
        search_list = [f"{result['artists'][0]['name']} - {result['name']}"]
    elif type == "playlist":
        result = spotify.playlist_tracks(id, limit=SPOTIFY_SONG_LIMIT)
        search_list = [f"{item['track']['artists'][0]['name']} - {item['track']['name']}" for item in result['items']]
    return search_list

# YouTube

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


# Format time string given duration in seconds
def time_string(duration):
    hours = duration // 3600
    mins = (duration % 3600) // 60
    seconds = (duration % 3600) % 60
    return f"{str(hours).zfill(2)}:{str(mins).zfill(2)}:{str(seconds).zfill(2)}"

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

# Retrieves song metadata and stores it in the song_data dictionary
# Will optionally download the song file itself (since it's costly)
# Can take in an id or search query for parameter song_info, according to is_id
# Returns None if a search returns no results
def get_song(song_info, is_id=False, download=True):
    yt = None
    if not is_id: # Do youtube search to get id
        s = Search(unidecode(song_info))
        if len(s.results) == 0: # No results for search
            return None
        
        yt = s.results[0]
        id = yt.video_id
    else:
        id = song_info

    if id in song_data: # Get metadata if we already have it
        data = song_data[id]
    else: # Otherwise, retrieve it
        if not yt:
            yt = YouTube(yt_id_to_url(id))
        data = {
            "title": yt.title,
            "duration": yt.length,
            "downloaded": False,
            "file path": None,
            "request count": 0,
            "times played": 0
        }

    # Only download if we want to and haven't already downloaded it
    if download and not data["downloaded"]:
        if not yt:
            yt = YouTube(yt_id_to_url(id))
        stream = yt.streams.filter(only_audio=True).first()
        out_file = stream.download(output_path=MUSIC_PATH)
        base, _ = os.path.splitext(out_file)
        file_path = os.path.join(MUSIC_PATH, f"{base}.mp3")
        
        if not os.path.exists(file_path):
            os.rename(out_file, file_path)
        else:
            print("Attempted to download something that has already been downloaded.\n", data)

        data["file path"], data["downloaded"] = file_path, True
    
    song_data[id] = data
    return id

# Recursive callback to play the next song
# Used by the "-play" command
# This is the function that actually downloads and plays the next song in the queue
# If something is already playing, this function won't do anything
def play_next(ctx):
    global curr_song_id, is_looping
    # If looping, take current song that just finished and add it back to the queue
    if is_looping and curr_song_id and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        song_queue.append(curr_song_id)

    # If current song is finished and there's something queued, play it
    if len(song_queue) >= 1 and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        curr_song_id = song_queue.popleft()
        get_song(curr_song_id, is_id=True) # Downloads the song if not already downloaded
        data = song_data[curr_song_id]
        title, file_path = data["title"], data["file path"]
        asyncio.run_coroutine_threadsafe(ctx.send(f'**Now playing:** :notes: {title} :notes:'), loop=bot.loop)
        ctx.message.guild.voice_client.play(discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=file_path), after=lambda e: play_next(ctx))

        # Increase play count
        song_data[curr_song_id]["times played"] += 1

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
    
    songs_to_add = [] # List of songs to add to queue -- can be a youtube id or a search query
    using_id = False # Flag to check if we're working with youtube id or search queries

    # Determine if arguments are a youtube url, spotify url, or search query
    url = args[0]
    yt_id = yt_url_to_id(url) # This yt id will be valid if given a url
    if yt_id: # We have a youtube url
        songs_to_add.append(yt_id)
        using_id = True
    elif is_spotify_url(url): # We have a spotify url
        print("getting spotify data")
        songs_to_add.extend(get_spotify_info(url))
    else: # We have a search query
        songs_to_add.append(" ".join(args))

    print("getting song metadata and adding to queue")
    for song_info in songs_to_add:
        # Get song metadata without downloading
        # We download just before playing the song to avoid downloading one song while playing another
        id = get_song(song_info, is_id=using_id, download=False)
        if not id:
            await ctx.send(f"\"{song_info}\" did not yield any search results.")
            continue

        data = song_data[id]
        title, duration = data["title"], data["duration"]

        if duration > DURATION_LIMIT: # Check if song is too long
            await ctx.send(f":notes: {title} :notes: is too long to send.  Please request something shorter than {time_string(DURATION_LIMIT)}.")
            continue
        elif duration == 0: # Check if song is a livestream
            await ctx.send(f":notes: {title} :notes: is currently streaming live and cannot be downloaded.")
            continue

        # Update user usage data
        user = ctx.author.mention.replace("!", "")
        if user not in user_data:
            user_data[user] = {}
        user_data[user][id] = user_data[user].get(id, 0) + 1

        # Update request count for song
        song_data[id]["request count"] += 1

        # Add to queue and play the next song
        song_queue.append(id)
        await ctx.send(f"Successfully added :notes: {title} :notes: to the queue.")
        play_next(ctx)

@bot.command(name='playall', help='Plays all downloaded songs')
async def playall(ctx):
    await join(ctx) # join the voice channel
    song_queue.extend([id for id, data in song_data.items() if data["downloaded"]]) # Add all downloaded songs to the queue
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
    curr_song_title = song_data[curr_song_id]["title"] if curr_song_id else 'None'
    curr_song_msg = f"Current song: {curr_song_title}\n" # Display the current song
    queue_count_msg = f"Number of songs in queue: {len(song_queue)}\n" # Display the length of the queue
    if len(song_queue) > 0: # Display only the first few songs
        queue_header = "Songs in queue:\n" if len(song_queue) <= MAX_SHOWN_SONGS else f"First {MAX_SHOWN_SONGS} songs:\n"
        queue_contents = "\n".join([f"{i}) {song_data[id]['title']}" for i, id in enumerate(list(song_queue)[:MAX_SHOWN_SONGS], 1)])
    else:
        queue_header, queue_contents = "", ""
    msg = loop_msg + curr_song_msg + queue_count_msg + queue_header + queue_contents
    await ctx.send(msg)

@bot.command(name='remove', aliases=['delete'], help='Removes the song at the given position in the queue (1 is first)')
async def remove(ctx, position):
    position = int(position)
    if position > 0 and position <= len(song_queue):
        title = song_data[song_queue[position - 1]]["title"]
        del song_queue[position - 1]
        await ctx.send(f":notes: {title} :notes: at position {position} has been removed from the queue.")
    else:
        await ctx.send(f"Invalid position.  Please choose a position between 1 and {len(song_queue)}, inclusive.  Use the command \"-showqueue\" to show the current queue.")

@bot.command(name='skip', aliases=['next'], help='Skips the current song')
async def skip(ctx):
    global curr_song_id
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        curr_song_title = song_data[curr_song_id]["title"]
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
    elif not ctx.voice_client.is_paused():
        await ctx.send("No song is currently playing.")
    else:
        ctx.voice_client.resume()

@bot.command(name='stop', aliases=['cancel'], help='Stops the song and clears the queue')
async def stop(ctx):
    global curr_song_id, is_looping
    if not ctx.voice_client:
        await ctx.send("The bot is not currently in a voice channel.")
    elif not ctx.voice_client.is_playing():
        await ctx.send("No song is currently playing.")
    else:
        curr_song_id = None
        is_looping = False
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
    global_stats["Total requests"] = sum([data["request count"] for data in song_data.values()])

    # Total duration
    total_duration = sum([data["times played"] * data["duration"] for data in song_data.values()])
    global_stats["Total duration of played music"] = time_string(total_duration)

    # Most requested song
    if len(song_data) > 0:
        most_popular_id = max(song_data, key= lambda id: song_data[id]["request count"])
        most_popular_title = song_data[most_popular_id]["title"]
        request_count = song_data[most_popular_id]["request count"]
        msg = f"{most_popular_title} with {request_count} requests"
    else:
        msg = "N/A"
    global_stats["Most requested song"] = msg

    # Most played song
    if len(song_data) > 0:
        most_popular_id = max(song_data, key= lambda id: song_data[id]["times played"])
        most_popular_title = song_data[most_popular_id]["title"]
        request_count = song_data[most_popular_id]["times played"]
        msg = f"{most_popular_title} with {request_count} plays"
    else:
        msg = "N/A"
    global_stats["Most played song"] = msg

    # Most active user
    user_requests = {user: sum(user_data[user].values()) for user in user_data}
    if len(user_requests) > 0:
        most_active = max(user_requests, key= lambda user: user_requests[user])
        request_count = user_requests[most_active]
        msg = f"{most_active} with {request_count} requests"
    else:
        msg = "N/A"
    global_stats["Most active user"] = msg

    return global_stats

# Calculates user stats based off of the user stats dictionary
def calculate_user_stats(user):
    data = user_data[user]
    user_stats = {}

    # Total requests
    user_stats["Total requests"] = sum(data.values())

    # Total duration
    total_duration = sum([data[id] * song_data[id]["duration"] for id in data])
    user_stats["Total duration of requested music"] = time_string(total_duration)

    # Most requested song
    if len(data) > 0:
        most_popular_id = max(data, key= lambda song: data[song])
        most_popular_title = song_data[most_popular_id]["title"]
        request_count = data[most_popular_id]
        msg = f"{most_popular_title} with {request_count} requests"
    else:
        msg = "N/A"
    user_stats["Most requested song"] = msg

    return user_stats

def calculate_song_stats(song_info):
    s = Search(unidecode(song_info))
    if len(s.results) == 0: # No results for search
        return None
    yt = s.results[0]
    id = yt.video_id
    if id not in song_data:
        return None

    data = song_data[id]
    song_stats = {}

    # Title
    song_stats["Title"] = data["title"]

    # Duration
    song_stats["Duration"] = time_string(data["duration"])

    # Request Count
    song_stats["Request count"] = data["request count"]

    # Times played
    song_stats["Times played"] = data["times played"]

    return song_stats

@bot.command(name='stats', help='Retrieves usage statistics for the bot and its users.  Will print global statistics if given no arguments or will give user arguments if a user is mentioned as an argument.')
async def stats(ctx, *args):
    if len(args) == 0:
        global_stats = calculate_global_stats()
        msg = "Global statistics:\n" + "\n".join([f"{name}: {value}" for name, value in global_stats.items()])
    else:
        user = args[0]
        if len(args) == 0 or user in user_data: # Check if valid user
            user_stats = calculate_user_stats(user)
            msg = f"Statistics for user {user}:\n" + "\n".join([f"{name}: {value}" for name, value in user_stats.items()])
        else: # Search for song
            song_info = " ".join(args)
            song_stats = calculate_song_stats(song_info)
            if song_stats:
                msg = f"Statistics for queried song:\n" + "\n".join([f"{name}: {value}" for name, value in song_stats.items()])
            else:
                msg = "User or song not found."
    await ctx.send(msg)

if __name__ == "__main__":
    # Register hooks to write the data dictionaries to disk before exiting
    atexit.register(lambda *args: write_json_file(USER_FILE, user_data))
    atexit.register(lambda *args: write_json_file(SONG_FILE, song_data))

    # Run the bot
    bot.run(DISCORD_TOKEN)