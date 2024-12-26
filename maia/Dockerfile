ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install required packages
RUN \
    apk add --no-cache \
        python3 \
        py3-pip \
        gcc \
        g++ \
        make \
        cmake \
        git \
        linux-headers \
        python3-dev \
        redis \
        opencv \
        opencv-dev \
        libffi-dev \
        openssl-dev \
        zlib-dev \
        jpeg-dev \
        ffmpeg \
        portaudio-dev \
        swig \
    && python3 -m pip install --no-cache-dir --upgrade pip

# Set working directory
WORKDIR /app

# Copy application files
COPY rootfs /

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Make scripts executable
RUN chmod a+x /etc/services.d/*/run

# Labels
LABEL \
    io.hass.name="MAIA - My AI Assistant" \
    io.hass.description="MAIA (My AI Assistant) - A powerful AI assistant for Home Assistant" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    io.hass.arch="aarch64|amd64|armhf|armv7|i386" \
    maintainer="Kim Asplund <kim.asplund@gmail.com>" 