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
        table_names = ["songs", "song_requests", "song_plays"]
        self.drop_table_statements: list[str] = [self.DROP_TABLE_SQL.format(table_name) for table_name in table_names]
        self.create_table_statements: list[str] = [self.CREATE_SONGS_SQL, self.CREATE_SONG_REQUESTS_SQL, self.CREATE_SONG_PLAYS_SQL]

    async def create_tables(self, drop_tables: bool) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            if drop_tables:
                print("Dropping tables")
                await self.execute_sql_statements(conn, self.drop_table_statements)

            await self.execute_sql_statements(conn, self.create_table_statements)
    
    async def insert_song(self, song: tuple[str, str, str, int]) -> None:
        async with aiosqlite.connect(self.database_file_path) as conn:
            pass
    
    async def execute_sql_statements(self, conn: aiosqlite.Connection, sql_statements: list[str]) -> None:
        for sql_statement in sql_statements:
            await self.execute_sql_statement(sql_statement)

    async def execute_sql_statement(self, conn: aiosqlite.Connection, sql_statement: str) -> None:
        try:
            await conn.execute(sql_statement)
        except aiosqlite.Error as e:
            print(f"Error in SQL statement {sql_statement}: " + str(e))