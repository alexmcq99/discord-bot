FROM python:3.10-slim-buster
RUN apt-get update -y
RUN apt-get install -y ffmpeg
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]