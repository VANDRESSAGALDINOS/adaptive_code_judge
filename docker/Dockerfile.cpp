FROM debian:stable-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ time tini && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENTRYPOINT ["/usr/bin/tini", "--"]
