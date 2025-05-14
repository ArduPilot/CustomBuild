FROM python:3.10.16-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git gosu

RUN groupadd -g 999 ardupilot && \
    useradd -u 999 -g 999 -m ardupilot --shell /bin/false && \
    mkdir /app && \
    chown ardupilot:ardupilot /app

COPY --chown=ardupilot:ardupilot . /app
WORKDIR /app/web
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "wsgi:application"]
