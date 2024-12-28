# Use CUDA base image for GPU support
FROM nvidia/cuda:12.6.3-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    cuda-command-line-tools-12-6 \
    cuda-nvrtc-12-6 \
    cuda-nvtx-12-6 \
    cuda-cupti-12-6 \
    cuda-nvprof-12-6 \
    && rm -rf /var/lib/apt/lists/*

# Set CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Create necessary directories
RUN mkdir -p /models /data /app

# Copy application code
COPY app /app/

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,video

# Expose port for node communication
EXPOSE 5555

# Run MAIA node
CMD ["python3", "-m", "maia.node"] 