FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    icecast2 \
    && rm -rf /var/lib/apt/lists/* \
    && (groupadd -r icecast 2>/dev/null || true) \
    && (useradd -r -g icecast -s /bin/false icecast 2>/dev/null || true) \
    && mkdir -p /var/log/icecast \
    && chown -R icecast:icecast /var/log/icecast

EXPOSE 8000

# Icecast will drop privileges to icecast user via config
CMD ["icecast2", "-c", "/etc/icecast.xml"]
