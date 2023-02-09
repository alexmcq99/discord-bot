from datetime import datetime, timedelta

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

def time_str_to_seconds(time_str: str):
    hours, minutes, seconds = parse_time_str(time_str)
    return hours * 3600 + minutes * 60 + seconds
    
def parse_time_str(time_str: str):
    time_units = time_str.split(":")
    seconds = int(time_units[-1])
    minutes = int(time_units[-2]) if len(time_units) > 1 else 0
    hours = int(time_units[-3]) if len(time_units) > 2 else 0
    return hours, minutes, seconds

def format_time_str(seconds: int, minutes: int = 0, hours: int = 0) -> str:
    if isinstance(seconds, float):
        seconds = round(seconds)
    extra_minutes, seconds = divmod(seconds, 60)
    minutes += extra_minutes
    extra_hours, minutes = divmod(minutes, 60)
    hours += extra_hours
    return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"

def format_datetime(timestamp: datetime) -> str:
    return timestamp.strftime(TIME_FORMAT)

def format_timedelta(delta: timedelta) -> int:
    return round(delta.total_seconds())