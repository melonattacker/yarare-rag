FROM python:3.12-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ENV LANG=C.UTF-8

COPY . .

RUN useradd appuser
RUN chown -R appuser:appuser /app
USER appuser

CMD ["uwsgi", "--ini", "/app/uwsgi.ini"]
