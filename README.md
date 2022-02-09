# discord-bot
Making a youtube/spotify music bot for personal discord server

## Set up development environment

Do the following steps to set up your dev environment to run the discord bot:
1. Set up your very own discord bot using this [tutorial](https://tinyurl.com/bdewbdxk)
2. Create a `.env` file in the root directory of this repository
3. Put your discord token into `.env` as an environment variable named `discord_token`.  The file should have only one line that looks like this:  
`discord_token = "<insert actual token here>"`  
This token will be loaded and used by `app.py`.
4. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if not already installed
5. Create a conda environment from `discord_bot_env.yml`

    `conda create -f discord_bot.yml`

    This will create a new conda environment called `discord_bot_env` containing all necessary packages.
6. Download [ffmpeg](ffmpeg.org) and place `ffmpeg.exe` in the root directory of this repository
7. Activate the conda environment

    After these steps, your dev environment should be good to go.
