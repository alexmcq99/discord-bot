import os
import pandas as pd

class Stats:
    def __init__(self, data_dir: str):
        self.data_dir: str = data_dir
        self.songs_file: str = os.path.join(data_dir, "songs.csv")
        self.song_requests_file: str = os.path.join(data_dir, "song_requests.csv")

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

    def read_songs(self):
        return pd.read_csv(self.songs_file)

    def read_song_requests(self):
        return pd.read_csv(self.song_requests_file)
    
    def write_song(self, song: list[str]):
        write_to_csv(self.song_requests_file, song)
    
    def write_song_request(self, song_request: list[str]):
        write_to_csv(self.song_requests_file, song_request)