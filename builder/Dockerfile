FROM ardupilot/ardupilot-dev-chibios:v0.1.4

RUN groupadd -g 999 ardupilot && \
    useradd -u 999 -g 999 -m ardupilot --shell /bin/false && \
    mkdir /app && \
    chown ardupilot:ardupilot /app && \
    mkdir /workdir && \
    chown ardupilot:ardupilot /workdir

COPY --chown=ardupilot:ardupilot . /app

WORKDIR /app
RUN pip install --no-cache-dir -r ./builder/requirements.txt

USER ardupilot
CMD ["python", "-m", "builder"]
