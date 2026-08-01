FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg gosu python3 python3-numpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY tennis_reels.py /usr/local/bin/tennis_reels.py
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
