import aiocsv
import aiofiles
import aiosqlite
from config.config import Config
import csv
from datetime import datetime

async def write_to_csv(csv_file: str, row: list[str]):
    async with aiofiles.open(csv_file, mode="a", encoding="utf-8", newline="") as f:
        writer = aiocsv.AsyncWriter(f, quoting=csv.QUOTE_ALL)
        await writer.writerow(row)

class MusicDatabase():
    DROP_TABLE_SQL = "drop table if exists {0};"
    CREATE_SONGS_SQL = """create table if not exists songs(
        id text not null primary key,
        title text not null,
        channel_name text not null,
        duration int not null);"""
    CREATE_SONG_REQUESTS_SQL = """create table if not exists song_requests(
        requester_id integer not null,
        song_id text not null,
        timestamp text not null,
        foreign key(song_id) references songs(id));"""
    CREATE_SONG_PLAYS_SQL = """create table if not exists song_plays(
        requester_id integer not null,
        song_id text not null,
        timestamp text not null,
        duration int not null,
        foreign key(song_id) references songs(id));"""
    
    def __init__(self, config: Config):
        self.database_file_path: str = config.database_file_path
        self.table_names: list[str] = ["songs", "song_requests", "song_plays"]

    async def create_tables(self, drop_tables: bool = False):
        async with aiosqlite.connect(self.database_file_path) as conn:
            if drop_tables:
                print("Dropping tables")
                drop_statements = [self.DROP_TABLE_SQL.format(table_name) for table_name in self.table_names]
                try:
                    for drop_statement in drop_statements:
                        await conn.execute(drop_statement)
                except aiosqlite.Error as e:
                    print("Error in Table Drops: " + str(e))

            try:
                await conn.execute(self.CREATE_SONGS_SQL)
                await conn.execute(self.CREATE_SONG_REQUESTS_SQL)
                await conn.execute(self.CREATE_SONG_PLAYS_SQL)
            except aiosqlite.Error as e:
                print("Error in Table Creation: " + str(e))