FROM python:3.13.5-slim-bookworm

WORKDIR /usr/src/app

COPY ./serveur/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./serveur/. .
RUN rm common
COPY ../common ./common

CMD [ "python", "-u", "main.py" ]