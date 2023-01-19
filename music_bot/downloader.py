from pebble import ThreadPool
# from pebble import ProcessPool
from .songs import SongRequest

class Downloader:
    def __init__(self):
        self.thread_pool: ThreadPool = ThreadPool()
        # self.thread_pool: ProcessPool = ProcessPool()

    def __del__(self):
        self.thread_pool.stop()
        self.thread_pool.join()

    def queue_downloads_if_necessary(self, song_requests: list[SongRequest]):
        print("queueing download if necessary")
        for song_request in song_requests:
            if not song_request.is_downloaded():
                print(f"{song_request} needs to be downloading. scheduling thread")
                song_request.song.download_future = self.thread_pool.schedule(song_request.download)
        print("Active? ", self.thread_pool.active)