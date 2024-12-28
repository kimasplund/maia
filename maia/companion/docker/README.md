# MAIA Companion Docker

This is a companion Docker setup for MAIA that provides GPU-accelerated processing capabilities, Valkey replication, and PostGIS read replica functionality.

## Prerequisites

- NVIDIA GPU with CUDA support
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed
- Docker and Docker Compose
- Access to your Home Assistant instance
- Access to your primary Valkey instance
- Access to your primary PostGIS database

## Features

- GPU-accelerated processing using NVIDIA CUDA and TensorRT
- Valkey replication for distributed data processing
- PostGIS read replica for local spatial data access
- Optimized PyTorch inference using TensorRT
- Automatic synchronization with primary instances

## Setup Instructions

1. Copy `.env.example` to `.env` and fill in your configuration:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your specific configuration:
   - Add your Home Assistant URL and supervisor token
   - Configure Valkey primary URL and token
   - Set up PostGIS connection details
   - Adjust GPU settings if needed

3. Create required directories:
   ```bash
   mkdir -p models data
   ```

4. Start the services:
   ```bash
   docker compose up -d
   ```

5. Verify the setup:
   ```bash
   docker compose logs -f
   ```

## Service Endpoints

- MAIA GPU Service: `http://localhost:8000`
- Valkey Replica: `http://localhost:8080`
- PostGIS Replica: `localhost:5432`

## GPU Optimization

The setup includes:
- CUDA 12.1 with cuDNN 8
- PyTorch with CUDA support
- TensorRT integration for optimized inference
- Automatic GPU memory management
- Support for multiple GPUs

## Monitoring

- GPU metrics: Use `nvidia-smi` on the host
- Container logs: `docker compose logs -f [service]`
- Application metrics: Available at `http://localhost:8000/metrics`

## Troubleshooting

1. GPU not detected:
   - Verify NVIDIA drivers are installed
   - Check NVIDIA Container Toolkit installation
   - Ensure Docker has GPU access

2. Replication issues:
   - Check network connectivity
   - Verify credentials in `.env`
   - Check primary instance accessibility

3. Performance issues:
   - Monitor GPU memory usage
   - Adjust `PYTORCH_CUDA_ALLOC_CONF` in `.env`
   - Check TensorRT optimization status

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- Use strong passwords for all services
- Regularly update dependencies and base images
- Monitor for security advisories 