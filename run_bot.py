from music_bot import Song

so_much_more_url = "https://youtu.be/AVYgaMsEuvw"
song = Song(so_much_more_url, "music", "ffmpeg")
song.guilds_queued.add(0)
song.download()