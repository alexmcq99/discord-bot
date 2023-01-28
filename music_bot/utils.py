import aiocsv
import aiofiles
import csv

async def write_to_csv(csv_file: str, row: list[str]):
    async with aiofiles.open(csv_file, mode="a", encoding="utf-8", newline="") as f:
        writer = aiocsv.AsyncWriter(f, quoting=csv.QUOTE_ALL)
        await writer.writerow(row)