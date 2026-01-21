# Quick Start Guide - Unified Deployment

## Prerequisites

Before deploying, ensure you have:

- 2 DGX Spark systems with NVIDIA H100/A100 GPUs
- Ubuntu 22.04+ with CUDA drivers installed
- Network connectivity between DGX Sparks (LAN + optional InfiniBand)
- Required tools: `kubectl`, `helm`, `docker`, `ssh`
- SSH key-based authentication configured between nodes

## Testing the Deployment (Dry-Run)

**Always test your configuration before deploying:**

```bash
# 1. Validate configuration files
./validate-config.sh config

# 2. Validate Kubernetes manifests
./validate-config.sh manifests

# 3. Run full dry-run (no actual changes)
./deploy-unified.sh --dry-run
```

The dry-run will show you exactly what would be deployed without making any changes.

## Configuration

### 1. Create Local Configuration

```bash
# Copy the default configuration
cp unified-config.env unified-config.local.env

# Edit your local settings (this file is gitignored)
nano unified-config.local.env
```

### 2. Required Settings

Update these in `unified-config.local.env`:

```bash
# Network Configuration
CONTROL_PLANE_API_IP=192.168.1.100      # Your control plane IP
WORKER_NODE_SSH_TARGET=192.168.1.101    # Worker node IP
FABRIC_CTRL_IP=10.10.10.1               # InfiniBand IP (optional)

# Model Configuration  
MODEL="openai/gpt-oss-120b"             # Primary model
HF_TOKEN="hf_xxxxxxxxxxxxx"             # HuggingFace token (for gated models)

# Storage Paths
HF_CACHE="/raid/hf-cache"               # Model cache location
MODEL_CACHE="/raid/model-cache"         # Additional model storage
```

### 3. Validate Configuration

```bash
# Run all validation checks
./validate-config.sh

# Or run specific checks
./validate-config.sh config       # Configuration only
./validate-config.sh prereq       # Prerequisites only
./validate-config.sh network      # Network connectivity
./validate-config.sh storage      # Storage paths
./validate-config.sh manifests    # YAML manifests
```

## Deployment

### Full Deployment

```bash
# Deploy the complete stack
./deploy-unified.sh deploy
```

This will deploy:
1. Kubernetes cluster with InfiniBand fabric
2. Persistent storage volumes
3. VLLM model serving with Ray
4. Multi-agent chatbot system
5. Multi-modal inference capabilities
6. Monitoring stack (Prometheus/Grafana)
7. Enhanced cluster management UI

### Selective Deployment

You can disable specific components by setting environment variables:

```bash
# Deploy only VLLM, skip agents
ENABLE_MULTI_AGENT=0 ./deploy-unified.sh deploy

# Deploy without monitoring
ENABLE_PROMETHEUS=0 ENABLE_GRAFANA=0 ./deploy-unified.sh deploy
```

## Post-Deployment

### Check Status

```bash
# View all pods and services
./deploy-unified.sh status

# Or use kubectl directly
kubectl get pods --all-namespaces
kubectl get services --all-namespaces
```

### View Logs

```bash
# VLLM logs
kubectl logs -f deployment/vllm-ray-head -n vllm-system

# Agent backend logs
kubectl logs -f deployment/agent-backend -n agents-system

# Or use the convenience command
./deploy-unified.sh logs
```

### Access Services

After deployment, access your services:

```bash
# Get your control plane IP
CONTROL_IP=$(hostname -I | awk '{print $1}')

# Service URLs
echo "Cluster UI: http://${CONTROL_IP}:5000"
echo "VLLM API: http://${CONTROL_IP}:8000"
echo "Ray Dashboard: http://${CONTROL_IP}:8265"
echo "Agent Backend: http://${CONTROL_IP}:8001"
```

## Testing the Deployment

### Test VLLM API

```bash
curl -X POST "http://${CONTROL_IP}:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-120b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

### Test Multi-Agent System

```bash
curl -X POST "http://${CONTROL_IP}:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a Python function to calculate fibonacci numbers",
    "session_id": "test123"
  }'
```

## Troubleshooting

### Deployment Failed?

1. **Check logs:**
   ```bash
   ./deploy-unified.sh logs
   ```

2. **Verify prerequisites:**
   ```bash
   ./validate-config.sh prereq
   ```

3. **Check network connectivity:**
   ```bash
   ./validate-config.sh network
   ```

4. **Review configuration:**
   ```bash
   ./validate-config.sh config
   ```

### Common Issues

**Issue: VLLM pod not starting**
```bash
# Check GPU availability
kubectl describe nodes | grep nvidia.com/gpu

# Check HuggingFace token
kubectl get secret hf-token -n vllm-system -o yaml

# View detailed logs
kubectl logs deployment/vllm-ray-head -n vllm-system --previous
```

**Issue: Worker node not joining**
```bash
# Test SSH connectivity
ssh ${WORKER_NODE_SSH_USER}@${WORKER_NODE_SSH_TARGET} "hostname"

# Check network interfaces
./validate-config.sh network
```

**Issue: Storage issues**
```bash
# Check storage paths
./validate-config.sh storage

# Verify PVCs
kubectl get pvc --all-namespaces
```

## Cleanup

To remove all deployed components:

```bash
./deploy-unified.sh cleanup
# Type 'DELETE' to confirm
```

## Getting Help

1. Review the detailed test report: `TESTING_REPORT.md`
2. Check the main README: `README.md`
3. Review configuration: `unified-config.env`

## Advanced Usage

### Custom Agents

To add a new agent type, edit:
- `unified-deployments/agents/agents-deployment.yaml`
- Update agent routing logic
- Redeploy agents: `kubectl apply -f unified-deployments/agents/`

### Performance Tuning

Adjust GPU memory utilization:
```bash
# In unified-config.local.env
GPU_MEMORY_UTIL=0.85  # Lower if experiencing OOM errors
```

Adjust tensor parallelism:
```bash
# In unified-config.local.env
TENSOR_PARALLEL=4  # Must match available GPUs
```

### Monitoring

Access monitoring interfaces:
- Grafana: `http://${CONTROL_IP}:3001`
- Prometheus: `http://${CONTROL_IP}:9090`
- Ray Dashboard: `http://${CONTROL_IP}:8265`

---

For detailed technical information, see `TESTING_REPORT.md` and `README.md`.
