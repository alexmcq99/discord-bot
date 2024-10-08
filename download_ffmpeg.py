import os
import shutil
import urllib.request
import zipfile

# Download zip file for ffmpeg
DOWNLOAD_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
zip_file, _ = urllib.request.urlretrieve(DOWNLOAD_URL)

# Extract ffmpeg.exe and place in root directory
OLD_PATH = "ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
with zipfile.ZipFile(zip_file, "r") as zip_ref:
    extracted = zip_ref.extract(OLD_PATH)

# Clean up files
NEW_PATH = "ffmpeg.exe"
os.rename(extracted, NEW_PATH)
shutil.rmtree(OLD_PATH.split("/", maxsplit=1)[0])
os.remove(zip_file)
