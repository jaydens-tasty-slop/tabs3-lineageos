FROM localhost/lineageos-gts3-build:ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends adb ffmpeg heimdall-flash python3-pytest \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
CMD ["bash", "-c", "adb start-server && exec sleep infinity"]
