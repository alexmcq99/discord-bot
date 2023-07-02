from urllib.parse import urlparse

from asyncspotify import Client, ClientCredentialsFlow
from asyncspotify.exceptions import SpotifyException

class SpotifyWrapper:
    def __init__(self, spotipy_client_id: str, spotipy_client_secret: str) -> None:
        self.spotify_auth = ClientCredentialsFlow(client_id=spotipy_client_id, client_secret=spotipy_client_secret)
        # self.spotify_client = Client(self.spotify_auth)

    # Return list of search queries (strings to search) for each song in an album or playlist
    # If given a link to a track, returns a list with a single element
    async def get_search_queries(self, url, max_tries=3):
        async with Client(self.spotify_auth) as spotify_client:
            parse_result = urlparse(url)
            _, type, id = parse_result.path.split("/")
            tracks = []
            get_func = getattr(spotify_client, f"get_{type}")
            
            tries, result = 0, None
            while not result and tries < max_tries:
                try:
                    result = await get_func(id)
                except SpotifyException as e:
                    print("Exception when getting data from Spotify: ", e)
                
                tries += 1
            
            if result:
                print(f"Successfully got Spotify data after {tries} tries.")
            else:
                raise SpotifyException(f"Failed to get data from Spotify after {tries} tries.")
            
            if type == "track":
                tracks.append(result)
            else:
                tracks.extend(result.tracks)
            search_list = [f"{track.artists[0].name} - {track.name}" for track in tracks]
        return search_list

