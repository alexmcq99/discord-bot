from config.config import Config
import re
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import urlparse

def is_spotify_url(url):
        # https://open.spotify.com/track/405HNEYKGDifuMcAZvqrqA?si=f38076221d0246b5
        # https://open.spotify.com/album/643kxxjS5xPkzD4bR9vUn2?si=cuCeyEgYQm-pXKK7679ptQ
        # https://open.spotify.com/playlist/6FkEOJ76LyyajBjOoGvGXT?si=6ba13d149a1b4d1c
        pattern = re.compile(r"^https:\/\/open.spotify.com\/(?:track|album|playlist)\/[a-zA-Z0-9]+")
        return pattern.match(url)
        
class SpotifyClientWrapper:
    def __init__(self, config: Config) -> None:
        self.config = config
        creds = SpotifyClientCredentials(config.spotipy_client_id, config.spotipy_client_secret)
        self.spotify_client = Spotify(client_credentials_manager=creds)
        print("made client wrapper")

    # Return list of search queries (strings to search) for each song in an album or playlist
    # If given a link to a track, returns a list with a single element
    def get_search_queries(self, url):
        parse_result = urlparse(url)
        _, type, id = parse_result.path.split("/")
        search_list = []
        if type == "album":
            result = self.spotify_client.album(id)
            search_list = [f"{track['artists'][0]['name']} - {track['name']}" for track in result['tracks']['items']]
        elif type == "track":
            result = self.spotify_client.track(id)
            search_list = [f"{result['artists'][0]['name']} - {result['name']}"]
        else:
            result = self.spotify_client.playlist_tracks(id, limit=self.config.spotify_song_limit)
            search_list = [f"{item['track']['artists'][0]['name']} - {item['track']['name']}" for item in result['items']]
        return search_list

