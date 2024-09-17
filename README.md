# discord-bot
A YouTube/Spotify music bot for a personal discord server.

## Set up dev environment

1. Set up your very own discord bot using this [tutorial](https://tinyurl.com/bdewbdxk).  Afterwards, you should have your own discord bot token and the bot itself should be added to any servers you want to use it or test it on.
2. Create a `.env` file in the root directory of this repository
3. Put your discord token into `.env` as an environment variable named `discord_token`.  The file should have only one line that looks like this:  
`discord_token = "<insert actual token here>"`  
This token will be loaded and used by `app.py`.
4. This bot also supports spotify with Python's [Spotipy](https://spotipy.readthedocs.io/en/master/) package, so you will need a spotify web API client id and client secret. Follow the instructions [here](https://medium.com/@maxtingle/getting-started-with-spotifys-api-spotipy-197c3dc6353b) to get them, adding them to `.env` as `spotipy_client_id` and `spotipy_client_secret`, just like with the discord token.
5. Install dependencies. The [next section](#set-up-miniconda-environment) will detail how to create a virtual environment using [Miniconda](https://docs.conda.io/en/latest/miniconda.html), which I prefer, but you can also directly install the dependencies, as long as you have a compatible version of [Python](https://www.python.org/downloads/) installed. I used [Python 3.12.4](https://www.python.org/downloads/release/python-3124/). Run `pip install -r requirements.txt` and skip the section below if you want to do this.
6. Download the correct [ffmpeg](https://github.com/BtbN/FFmpeg-Builds/releases) release for your operating system and place `ffmpeg.exe` from the `bin` directory of the downloaded package in the root directory of this repository. You can also run the script `download_ffmpeg.py` once your virtual environment is set up, which will do this automatically, for Windows.

### Set up Miniconda environment

1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if not already installed
2. Create a conda environment from `discord_bot_env.yaml`

    `conda env create -f discord_bot_env.yaml`

    This will create a new conda environment called `discord_bot_env` containing all necessary packages.
3. Activate the conda environment with `conda activate discord_bot_env`

After these steps, your dev environment should be good to go.  Run `python run_bot.py` and look to see if your discord bot is online on any servers you've added it to.  Running commands in any text channel of a discord server of which the bot is a member should work.

## Overview of Functionality

The bot supports playing music from YouTube videos, YouTube playlists, and Spotify tracks, albums, and playlists. The bot also supports queueing songs (or collections of songs) if another one is already playing, with more commands to display and modify the queue. The bot's audio player automatically plays the next song from the queue as old songs finish and new ones are added.

### Commands with examples

The bot currently supports the following commands, using the prefix `-` (configurable) in a text channel:  
- `-help` -- Displays a help menu with information on each command.
- `-join` -- Joins the voice channel that the user is currently in, with an error message if the user is not in a channel.
-  `-leave` -- Leaves the voice channel the bot is currently in, with an error message if the bot is not in a channel. Also stops the audio player and clears the song queue.
-  `-play <YouTube video id/url, YouTube search arguments, YouTube playlist url, or Spotify track, album, or playlist url/uri>` -- Adds song (or collection of songs) to the queue. If given a YouTube video url, or Spotify track url, that video/track will be played. If given YouTube search arguments, the first video from a YouTube search will be played. If given a YouTube playlist, Spotify album, or Spotify playlist, all videos/tracks from the album/playlist will be added to the queue.
   -  YouTube video id:  `-play dQw4w9WgXcQ`
   -  YouTube video url: `-play https://youtu.be/dQw4w9WgXcQ`
   -  YouTube search arguments: `-play rick astley never gonna give you up`
   -  Spotify track url: `-play https://open.spotify.com/track/4PTG3Z6ehGkBFwjybzWkR8?si=b36de52ad3b44600`
   -  Spotify track uri: `play spotify:track:4PTG3Z6ehGkBFwjybzWkR8`
   -  Spotify album url: `-play https://open.spotify.com/album/6qb9MDR0lfsN9a2pw77uJy?si=41N7G0jgQ9SMnO82xeAUcQ`
   -  Spotify album uri: `-play spotify:album:6qb9MDR0lfsN9a2pw77uJy`
   -  Spotify playlist url: `-play https://open.spotify.com/playlist/37i9dQZEVXbNG2KDcFcKOF?si=62415e0eb4f34ad1`
   -  Spotify playlist uri: `-play spotify:playlist:37i9dQZEVXbNG2KDcFcKOF`
-  `-playnext <YouTube video id/url, YouTube search arguments, YouTube playlist url, or Spotify track, album, or playlist url/uri>` -- Behaves the same as the `-play` command, except that the song (or collection of songs) is added to the front of the queue instead of the end.
-  `-pause` -- Pauses the current song, with an error message if nothing is playing.
-  `-resume` -- Resumes (unpauses) the current song, with an error message if nothing is paused.
-  `-stop` -- Completely stops the audio player, with an error message if nothing is playing. Also clears the queue.
-  `-loop` -- Enable looping the queue until this command is used again.
-  `-clear` -- Clears the queue, not affecting the song currently playing.
-  `-skip` -- Skips the song currently playing and plays the next one in the queue.
-  `-back` -- Goes back to the previous song, if there was one.
-  `-queue` -- Displays how many songs are in the queue and the first 25 songs (configurable).
-  `-now` -- Shows the song that's currently playing, if any.
-  `-status` -- Shows the current status of the bot. I.e., shows the queue, what song is currently playing, and if the queue is looping or not.
-  `-remove <position in queue to remove or YouTube search arguments>` -- Removes the song at the given position in the queue (1 is first), with an error message for an invalid position. Use the `queue` command to see each song and its position in the queue. If given YouTube search arguments, the bot searches for a song in the queue that matches the arguments and removes it if found.
   -  `-remove 2`
   -  `-remove rich astley never gonna give you up`
-  `stats <user mention> <YouTube video id/url or YouTube search arguments>` -- Displays usage statistics for bot, including information such as who has played the most songs and what song has been played the most. Takes in arguments for a specific user, song or both. Only available when the `record_stats` configuration flag is set. 
   -  `-stats` -- Gets statistics for the entire guild (server).
   -  `-stats @Alex` -- Gets statistics for the user mentioned, Alex.
   -  `-stats toto africa` -- Gets statistics for Africa by Toto.
   -  `-stats @Alex toto africa` -- Gets statistics for Alex requesting/playing Africa by Toto.
-  `-shuffle` -- Randomly shuffles the queue.

## Configuration

The bot can be configured in `config/config.yaml` to adjust its behavior. These flags are then read into `config/config.py`, where defaults are set if flags are not present.

`config/config.yaml`, as currently checked in, is mostly empty, with just one flag, `enable_multiprocessing`, set to `true`. See the [Concurrency](#concurrency) section for more details on this flag. The rest will have their default values.

### Configuration Flags

#### Discord 
- `command_prefix` -- The string prefix for commands for the music bot. Useful to change if multiple bots in the same discord server have the same command prefix. If not present, defaults to `-`.

#### Music
- `max_displayed_songs` -- The max amount of songs displayed at one time when displaying the queue or summarizing a YouTube playlist, Spotify Album, or Spotify playlist. If not present, defaults to `25`.
- `playlist_song_limit` -- The max amount of songs retrieved when playing a YouTube playlist, Spotify album, or Spotify playlist. If not present, defaults to infinity (`math.inf` in Python).
- `yt_search_playlist_song_limit` -- The max amount of songs retrieved when creating a YouTube playlist from a search query. This is currently only used when removing a song from the queue given a YouTube search query, when we want to get the first few YouTube search results to look for in the queue. Defaults to `5` if not present.
- `inactivity_timeout` -- The timeout duration, in seconds, for the music bot to wait in a discord voice channel for a song to be played. If no song is played, the bot will disconnect from the channel. Defaults to `600` (10 minutes) if not present.

#### Usage Data and Stats
- `data_dir` -- The directory to store the usage database in. Defaults to `data` if not present.
- `usage_database_filename` -- The filename for the usage database, to be stored in `data_dir`. Defaults to `usage.db` if not present.
- `figure_dir` -- The directory to store figures created for the `stats` command.
- `enable_usage_database` -- Enables writing to and reading from the usage database. If enabled, the music bot will record usage data and use it to calculate statistics. The `stats` command is only available if set to `True`. Defaults to `False` if not present.
- `reset_usage_database` -- Whether or not to reset (clear) the usage database's data. If not present, defaults to `False`.
- `enable_stats_usage_graph` -- Enables creating a graph of usage data for the `stats` command, such as requests for a particular song over time. Created graphs will be stored in `figure_dir`. Defaults to `False` if not present.
  - Note: this feature is still in development. There may be some bugs, so use at your own risk.

#### Concurrency
- `enable_multiprocessing` -- Enables the use of multiprocessing for processing YouTube playlists, Spotify albums, and Spotify playlists, through `concurrent.futures.ProcessPoolExecutor`. Considerably improves performance in this scenario. If disabled, a `concurrent.futures.ThreadPoolExecutor` will be used instead. Defaults to `False` if not present.
- `process_pool_workers` -- The max number of workers that the `ProcessPoolExecutor` will have, if `enable_multiprocessing` is `True`. Defaults to `None` if not present, which will instantiate the `ProcessPoolExecutor` with `os.cpu_count()` workers.
- `thread_pool_workers` -- The max number of workers that the `ThreadPoolExecutor` will have if `enable_multiprocessing` is `False`. Defaults to `4` if not present.

**Important Note**: if `enable_multiprocessing` is set to `False`, the bot may lag significantly while streaming audio and processing a playlist simultaneously.

This is because processing playlists is quite computationally expensive, and Python's global interpreter lock (GIL) prevents multithreading from achieving the true parallel execution that multiprocessing is capable of, so the threads processing playlist entries end up fighting for scheduling time with the thread that's streaming audio.

`thread_pool_workers` defaults to `4` because any higher degree of parallelism causes insufferable audio lag, at least when running the bot on my machine. More thread pool workers means less scheduling time for the thread that's streaming the audio.


## Future work
- Add sharding to make the bot scalable
- Add scripts for linux and windows to automate setting up developer environment