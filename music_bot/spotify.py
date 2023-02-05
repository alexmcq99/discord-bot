from asyncspotify import Client, ClientCredentialsFlow
from config import Config
import re
from urllib.parse import urlparse

def is_spotify_url(url):
        # https://open.spotify.com/track/405HNEYKGDifuMcAZvqrqA?si=f38076221d0246b5
        # https://open.spotify.com/album/643kxxjS5xPkzD4bR9vUn2?si=cuCeyEgYQm-pXKK7679ptQ
        # https://open.spotify.com/playlist/6FkEOJ76LyyajBjOoGvGXT?si=6ba13d149a1b4d1c
        pattern = re.compile(r"^https:\/\/open.spotify.com\/(?:track|album|playlist)\/[a-zA-Z0-9]+")
        return pattern.match(url)
        
def get_track_search_query(track):
    return f"{track.artists[0].name} - {track.name}"

class SpotifyClientWrapper:
    def __init__(self, config: Config) -> None:
        self.auth = ClientCredentialsFlow(client_id=config.spotipy_client_id, client_secret=config.spotipy_client_secret)

    # Return list of search queries (strings to search) for each song in an album or playlist
    # If given a link to a track, returns a list with a single element
    async def get_search_queries(self, url, tries=3):
        async with Client(self.auth) as sp_client:
            parse_result = urlparse(url)
            _, type, id = parse_result.path.split("/")
            tracks = []
            get = getattr(sp_client, f"get_{type}")
            result = None
            while not result and tries > 0:
                try:
                    result = await get(id)
                except Exception as e:
                    print("Exception when getting data from Spotify: ", e)
                    print("Trying again." if tries > 0 else "Out of tries.")
                    tries -= 1
            if not result:
                return result
            if type == "track":
                tracks.append(result)
            else:
                tracks.extend(result.tracks)
            search_list = [get_track_search_query(track) for track in tracks]
            return search_list

