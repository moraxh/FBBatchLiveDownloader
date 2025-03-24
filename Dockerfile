FROM python:3.9.7-alpine

WORKDIR /app

COPY requirements.txt .

RUN apk add --no-cache ffmpeg

RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-u", "main.py"]
