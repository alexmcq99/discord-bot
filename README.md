# discord-bot
Making a youtube/spotify music bot for personal discord server

## Set up development environment

Do the following steps to set up your dev environment to run the discord bot:
1. Set up your very own discord bot using this [tutorial](https://tinyurl.com/bdewbdxk).  Afterwards, you should have your own discord bot token and the bot itself should be added to any servers you want to use it or test it on.
2. Create a `.env` file in the root directory of this repository
3. Put your discord token into `.env` as an environment variable named `discord_token`.  The file should have only one line that looks like this:  
`discord_token = "<insert actual token here>"`  
This token will be loaded and used by `app.py`.
4. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if not already installed
5. Create a conda environment from `discord_bot_env.yml`

    `conda create -f discord_bot.yml`

    This will create a new conda environment called `discord_bot_env` containing all necessary packages.
6. Download [ffmpeg](ffmpeg.org) and place `ffmpeg.exe` in the root directory of this repository
7. Activate the conda environment with `conda activate discord_bot_env`

    After these steps, your dev environment should be good to go.  Run `python app.py` and look to see if your discord bot is online on any servers you've added it to.  Running commands in any text channel of a discord server of which bot is a member should work.

## Overview of functionality

The bot currently only supports playing music from youtube, given a url.  After using the `-play` command, the bot will download the audio as an mp3, storing it in the `music` directory, which it will create if it doesn't exist.  The bot will manage files it has already downloaded with `downloaded_songs.csv`, where it tracks the youtube id, title, and file path of all videos whose audio it's downloaded.  It just does this to avoid downloading any audio more than once.  

### Working commands

The bot currently supports the following commands, using the prefix "-" in a text channel:  
- `-join` -- joins the voice channel that the user is currently in, with an error message if the user is not in a channel
-  `-leave` -- leaves the voice channel the bot is currently in, with an error message if the bot is not in a channel
-  `-play <insert youtube url>` -- will download and play the audio of this youtube video, or just play it if it has already downloaded the audio; if there is already a song playing, it will download it (if necessary) and it to the queue to be played later
-  `-pause` -- will pause the current song, with an error message if nothing is playing
-  `-resume` -- will resume the current song, with an error message if nothing is paused
-  `-stop` -- will stop the current song, with an error message if nothing is playing; this is different from pausing because it cannot be resumed

### Known bugs and issues

- It can take 30 seconds to a minute to download a song, which is a pretty annoying delay
- Occasionally, when trying to download a song, the bot will give a 403 not authorized HTTP error, but will usually work when retrying
- When given a url to a playlist on youtube, the bot will just play the audio from the first video instead of queueing the entire playlist
- When running `-pause`, `-resume`, or `-stop`, `app.py` throws an error that `ctx`, the parameter for each command that contains relevant discord information, is None, but the commands still work and I have no idea why