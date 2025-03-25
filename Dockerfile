FROM python:3.9.7-alpine

WORKDIR /app

COPY requirements.txt .

RUN apk add --no-cache ffmpeg g++ postgresql-dev cargo gcc python3-dev libffi-dev musl-dev zlib-dev jpeg-dev

RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-u", "main.py"]