FROM localhost/lineageos-gts3-device:ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends glslang-tools \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
