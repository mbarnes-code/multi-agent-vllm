# DGX Spark Multi-Agent System
# Dockerfile for the multi-agent backend service

FROM python:3.11-slim

LABEL maintainer="DGX Spark Team"
LABEL description="Multi-agent system for DGX Spark with VLLM backend"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install .

# Copy application code
COPY multi_agent/ ./multi_agent/

# Create workspace directory for coding agent
RUN mkdir -p /workspace && chmod 777 /workspace

# Set default environment variables
ENV VLLM_ENDPOINT="http://vllm-service.vllm-system.svc.cluster.local:8000/v1" \
    SUPERVISOR_MODEL="gpt-oss-120b" \
    RAG_MODEL="gpt-oss-20b" \
    CODING_MODEL="meta-llama/Llama-3.1-8B-Instruct" \
    IMAGE_MODEL="microsoft/Phi-4" \
    MILVUS_HOST="milvus" \
    MILVUS_PORT="19530" \
    WORKSPACE_DIR="/workspace" \
    ENABLE_CODE_EXECUTION="true" \
    HOST="0.0.0.0" \
    PORT="8000"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["python", "-m", "multi_agent.server"]
