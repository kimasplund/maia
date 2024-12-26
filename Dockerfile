ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install required packages
RUN apk add --no-cache \
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
    swig

# Set working directory
WORKDIR /app

# Copy package files
COPY manifest.json requirements.txt ./
COPY api/ api/
COPY core/ core/
COPY database/ database/
COPY utils/ utils/
COPY web/ web/

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Set environment variables
ENV PYTHONPATH=/app

CMD [ "/run.sh" ]

# Labels
LABEL \
    io.hass.name="MAIA - AI Assistant" \
    io.hass.description="MAIA (Modular AI Assistant) - A powerful AI assistant for Home Assistant" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" 