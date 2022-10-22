# discord-bot
A youtube/spotify music bot for a personal discord server

## Set up development environment

1. Set up your very own discord bot using this [tutorial](https://tinyurl.com/bdewbdxk).  Afterwards, you should have your own discord bot token and the bot itself should be added to any servers you want to use it or test it on.
2. Create a `.env` file in the root directory of this repository
3. Put your discord token into `.env` as an environment variable named `discord_token`.  The file should have only one line that looks like this:  
`discord_token = "<insert actual token here>"`  
This token will be loaded and used by `app.py`.
4. This bot also supports spotify with Python's [Spotipy](https://spotipy.readthedocs.io/en/master/) package, so you will need a spotify web API client id and client secret. Follow the instructions [here](https://medium.com/@maxtingle/getting-started-with-spotifys-api-spotipy-197c3dc6353b) to get them, adding them to `.env` as `spotipy_client_id` and `spotipy_client_secret`, just like with the discord token.
4. Create a virtual environment. The following section will detail how to create one using [Miniconda](https://docs.conda.io/en/latest/miniconda.html), which I prefer, but you can also directly install the dependencies, as long as you have [Python](https://www.python.org/downloads/) installed. Run `pip install -r requirements.txt` and skip the steps for Miniconda if you want to do this.
5. Download the correct [ffmpeg](https://github.com/BtbN/FFmpeg-Builds/releases) release for your operating system and place `ffmpeg.exe` from the `bin` directory of the downloaded package in the root directory of this repository. You can also run the script `download_ffmpeg.py` once your virtual environment is set up, which will do this automatically, for Windows.

### Set up Miniconda environment

1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if not already installed
2. Create a conda environment from `discord_bot_env.yml`

    `conda env create -f discord_bot_env.yml`

    This will create a new conda environment called `discord_bot_env` containing all necessary packages.
3. Activate the conda environment with `conda activate discord_bot_env`

After these steps, your dev environment should be good to go.  Run `python app.py` and look to see if your discord bot is online on any servers you've added it to.  Running commands in any text channel of a discord server of which the bot is a member should work.

## Overview of Functionality

The bot currently only supports playing music from youtube, given a url or a search query (string used in searching for a video on youtube).  The bot also supports queueing songs if another one is already playing, with more commands to display and modify the queue.

The bot stores all downloaded audio files in the `music` directory, which it will create if it doesn't exist already, and keeps track of metadata of the downloaded songs in `downloaded_songs.csv`.  It also keeps track of usage statistics, in `user_stats.json` and `song_stats.json`, with a command to display these stats.

### Commands with examples

The bot currently supports the following commands, using the prefix "-" in a text channel:  
- `-help` -- displays a help menu with information on each command
- `-join` -- joins the voice channel that the user is currently in, with an error message if the user is not in a channel
-  `-leave` -- leaves the voice channel the bot is currently in, with an error message if the bot is not in a channel
-  `-play <youtube url, search arguments, or spotify album, playlist, or track url>` -- will download and play the audio of this youtube video, or just play it if it has already downloaded the audio; if a spotify url, it will download and play all songs in the album or playlist; if there is already a song playing, the bot will add it to the queue to be downloaded and played later
   -  `-play https://youtu.be/dQw4w9WgXcQ`
   -  `-play rick astley never gonna give you up`
   -  -play https://open.spotify.com/playlist/6FkEOJ76LyyajBjOoGvGXT?si=ac9e408b47ce470d
-  `-pause` -- will pause the current song, with an error message if nothing is playing
-  `-resume` -- will resume the current song, with an error message if nothing is paused
-  `-stop` -- will stop the current song, with an error message if nothing is playing; this is different from pausing because it cannot be resumed
-  `-loop` -- will tell the bot to keep looping the queue until this command is used again
-  `-clear` -- will clear the queue, not affecting the song currently playing
-  `-skip` -- will skip the song currently playing and play the next one in the queue
-  `-showqueue` -- will display whether or not the queue is looping, what the current song is, how many songs are in the queue, and the first 10 songs in the queue
-  `-remove <position in queue to remove>` -- will remove the song at the given position in the queue (1 is first), with an error message for an invalid position; use the `showqueue` command to see the contents of the queue
   -  `-remove 2`
-  `-playall` -- will play (queue) all songs that are downloaded
-  `stats <user>` -- will display global usage statistics for bot, including information such as who has played the most songs and what song has been played the most; takes in arguments for a specific user or song
   -  `-stats` -- gets global statistics
   -  `-stats @Alex` -- gets statistics for user "@Alex"
   -  `-stats toto africa` -- gets statistics for Africa by Toto, if applicable
-  `-shuffle` -- shuffles the queue

## Known issues
- When given a url to a playlist on youtube, the bot will just play the audio from the first video instead of queueing the entire playlist

## Future work
- Add sharding to make the bot scalable if it ever becomes publicly available
- Add scripts for linux and windows to automate setting up developer environment
- Move stats to remote database instead of in local files