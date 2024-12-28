ARG BUILD_FROM
FROM ${BUILD_FROM}

# Add S6 entry point
COPY rootfs /
WORKDIR /

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
        opencv \
        opencv-dev \
        libffi-dev \
        openssl-dev \
        zlib-dev \
        jpeg-dev \
        ffmpeg \
        portaudio-dev \
        swig \
        netcat-openbsd \
        bluez \
        bluez-libs \
        bluez-dev \
        postgresql-dev \
        postgresql-libs \
    && python3 -m pip install --no-cache-dir --upgrade pip

# Create required directories
RUN mkdir -p /app /data /config

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Make scripts executable
RUN chmod a+x /etc/services.d/*/run \
    && chmod a+x /etc/cont-init.d/*

# Labels
LABEL \
    io.hass.name="MAIA - My AI Assistant" \
    io.hass.description="MAIA (My AI Assistant) - A powerful AI assistant for Home Assistant" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    io.hass.arch="aarch64|amd64|armhf|armv7|i386" \
    maintainer="Kim Asplund <kim.asplund@gmail.com>"

# Set default environment variables
ENV \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app 