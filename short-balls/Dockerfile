FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg python3 python3-numpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY tennis_reels.py /usr/local/bin/tennis_reels.py

ENTRYPOINT ["python3", "/usr/local/bin/tennis_reels.py"]
