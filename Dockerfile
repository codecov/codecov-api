FROM python:3.7-alpine

RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc \ 
 musl-dev \ 
 postgresql-dev \ 
 python3-dev \
 git

COPY requirements.txt ./requirements.txt
RUN pip install -r /requirements.txt

EXPOSE 8000

COPY . /app

WORKDIR /app

ENV CODECOV_YML='codecov.yml'

ENTRYPOINT ["./api.sh"]