FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    icecast2 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/log/icecast2 \
    && chown -R icecast2:icecast /var/log/icecast2

EXPOSE 8000

USER icecast2

CMD ["icecast2", "-c", "/etc/icecast.xml"]
