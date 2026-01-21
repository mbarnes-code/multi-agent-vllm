#!/usr/bin/env bash
set -euo pipefail

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Unified DGX Spark Multi-Agent VLLM Installation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Single script to deploy complete multi-agent VLLM inference stack on
# 2 DGX Sparks including:
# - Kubernetes cluster setup with InfiniBand fabric
# - VLLM model serving with Ray distributed inference
# - Multi-agent chatbot with specialized agent types
# - Multi-modal inference capabilities (text, image, code generation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load unified configuration
if [ -f "${SCRIPT_DIR}/unified-config.local.env" ]; then
  source "${SCRIPT_DIR}/unified-config.local.env"
elif [ -f "${SCRIPT_DIR}/unified-config.env" ]; then
  source "${SCRIPT_DIR}/unified-config.env"
else
  echo "❌ Configuration file not found. Please ensure unified-config.env exists."
  exit 1
fi

# Colors and logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

log_success() {
    echo -e "${MAGENTA}[SUCCESS]${NC} $1"
}

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} $1"
}

# Error handling
cleanup_on_error() {
    log_error "Installation failed at step ${CURRENT_STEP}. Cleaning up..."
    # Add cleanup logic here if needed
    exit 1
}

trap cleanup_on_error ERR

# Utility functions
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check if running on DGX system
    if ! lspci | grep -i nvidia >/dev/null 2>&1; then
        log_error "No NVIDIA GPUs detected. This script is designed for DGX systems."
        exit 1
    fi
    
    # Check for required commands
    local required_commands=(kubectl helm docker ssh)
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done
    
    # Check InfiniBand interfaces
    if command -v ibdev2netdev >/dev/null 2>&1; then
        log_info "InfiniBand devices detected:"
        ibdev2netdev || true
    else
        log_warn "InfiniBand tools not found. High-speed fabric features may be limited."
    fi
    
    log_success "Prerequisites check passed"
}

display_banner() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║    🚀 DGX Spark Multi-Agent VLLM Deployment                     ║
║                                                                  ║
║    🔧 Kubernetes cluster setup                                  ║
║    🤖 VLLM model serving                                         ║
║    🧠 Multi-agent chatbot                                       ║
║    🎨 Multi-modal inference                                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF
}

display_configuration() {
    log_step "Configuration Summary:"
    echo "────────────────────────────────────────────────────────"
    echo "Network Configuration:"
    echo "  Control Plane: ${CONTROL_PLANE_API_IP}"
    echo "  Fabric Network: ${FABRIC_CTRL_IP:-"Not configured"}"
    echo "  Worker Node: ${WORKER_NODE_NAME} (${WORKER_NODE_IP})"
    echo ""
    echo "VLLM Configuration:"
    echo "  Primary Model: ${MODEL}"
    echo "  Tensor Parallel: ${TENSOR_PARALLEL}"
    echo "  GPU Memory Util: ${GPU_MEMORY_UTIL}"
    echo ""
    echo "Components to Deploy:"
    echo "  ✓ Kubernetes Cluster"
    echo "  $([ "${ENABLE_VLLM}" = "1" ] && echo "✓" || echo "✗") VLLM Model Serving"
    echo "  $([ "${ENABLE_MULTI_AGENT}" = "1" ] && echo "✓" || echo "✗") Multi-Agent Chatbot"
    echo "  $([ "${ENABLE_MULTIMODAL}" = "1" ] && echo "✓" || echo "✗") Multi-Modal Inference"
    echo "  $([ "${ENABLE_K8S_DASHBOARD}" = "1" ] && echo "✓" || echo "✗") Kubernetes Dashboard"
    echo "  $([ "${ENABLE_LONGHORN}" = "1" ] && echo "✓" || echo "✗") Longhorn Storage"
    echo "────────────────────────────────────────────────────────"
}

setup_kubernetes_cluster() {
    show_progress "Setting up Kubernetes cluster..."
    
    log_info "Initializing Kubernetes cluster with InfiniBand networking..."
    
    # Copy network configuration to dgx-spark-toolkit format
    cat > /tmp/network-override.env << EOF
CONTROL_PLANE_API_IP=${CONTROL_PLANE_API_IP}
CONTROL_PLANE_API_CIDR=${CONTROL_PLANE_API_CIDR}
CONTROL_PLANE_INTERFACE=${CONTROL_PLANE_INTERFACE}
CONTROL_PLANE_CONNECTION="${CONTROL_PLANE_CONNECTION}"
FABRIC_CTRL_IP=${FABRIC_CTRL_IP}
FABRIC_CTRL_CIDR=${FABRIC_CTRL_CIDR}
FABRIC_CTRL_INTERFACE=${FABRIC_CTRL_INTERFACE}
FABRIC_CTRL_CONNECTION="${FABRIC_CTRL_CONNECTION}"
WORKER_NODE_NAME=${WORKER_NODE_NAME}
WORKER_NODE_IP=${WORKER_NODE_IP}
WORKER_NODE_CIDR=${WORKER_NODE_CIDR}
WORKER_NODE_NETWORK=${WORKER_NODE_NETWORK}
WORKER_NODE_INTERFACE=${WORKER_NODE_INTERFACE}
WORKER_NODE_SSH_TARGET=${WORKER_NODE_SSH_TARGET}
WORKER_NODE_SSH_USER=${WORKER_NODE_SSH_USER}
ENABLE_K8S_DASHBOARD=${ENABLE_K8S_DASHBOARD}
ENABLE_LONGHORN=${ENABLE_LONGHORN}
EOF
    
    # Export for scripts
    export DGX_SPARK_NETWORK_CONFIG="/tmp/network-override.env"
    
    # Run Kubernetes cluster setup
    "${SCRIPT_DIR}/scripts/start-k8s-cluster.sh"
    
    # Wait for cluster to be ready
    log_info "Waiting for cluster to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=300s
    
    log_success "Kubernetes cluster setup complete"
}

create_namespaces() {
    show_progress "Creating Kubernetes namespaces..."
    
    local namespaces=(
        "vllm-system:VLLM model serving"
        "agents-system:Multi-agent chatbot"
        "multimodal-system:Multi-modal inference"
        "monitoring-system:Monitoring stack"
    )
    
    for ns_info in "${namespaces[@]}"; do
        local ns_name="${ns_info%%:*}"
        local ns_desc="${ns_info##*:}"
        
        log_info "Creating namespace: ${ns_name} (${ns_desc})"
        kubectl create namespace "${ns_name}" --dry-run=client -o yaml | kubectl apply -f -
        
        # Add GPU resource quota for compute namespaces
        if [[ "${ns_name}" =~ ^(vllm-system|agents-system|multimodal-system)$ ]]; then
            kubectl apply -f - << EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
  namespace: ${ns_name}
spec:
  hard:
    requests.nvidia.com/gpu: "8"
    limits.nvidia.com/gpu: "8"
EOF
        fi
    done
    
    log_success "Namespaces created successfully"
}

setup_persistent_storage() {
    show_progress "Setting up persistent storage..."
    
    # Create storage classes if not using Longhorn
    if [ "${ENABLE_LONGHORN}" != "1" ]; then
        kubectl apply -f - << EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
EOF
    fi
    
    # Create shared persistent volumes
    local pv_configs=(
        "hf-cache:${HF_CACHE}:${HF_CACHE_SIZE}"
        "model-cache:${MODEL_CACHE}:${MODEL_CACHE_SIZE}"
        "agent-data:${AGENT_DATA}:${AGENT_DATA_SIZE}"
    )
    
    for pv_info in "${pv_configs[@]}"; do
        local pv_name="${pv_info%%:*}"
        local pv_path="${pv_info#*:}"
        local pv_size="${pv_path#*:}"
        pv_path="${pv_path%%:*}"
        
        log_info "Creating persistent volume: ${pv_name}"
        
        # Ensure directory exists on both nodes
        sudo mkdir -p "${pv_path}"
        if [ -n "${WORKER_NODE_SSH_TARGET}" ]; then
            ssh "${WORKER_NODE_SSH_USER}@${WORKER_NODE_SSH_TARGET}" "sudo mkdir -p ${pv_path}"
        fi
        
        # Create PV manifest
        kubectl apply -f - << EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ${pv_name}
  labels:
    storage-type: shared-fast
spec:
  capacity:
    storage: ${pv_size}
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${PVC_STORAGE_CLASS:-fast-ssd}
  local:
    path: ${pv_path}
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - $(hostname)
          - ${WORKER_NODE_NAME}
EOF
    done
    
    log_success "Persistent storage configured"
}

deploy_vllm_serving() {
    show_progress "Deploying VLLM model serving..."
    
    if [ "${ENABLE_VLLM}" != "1" ]; then
        log_info "VLLM deployment disabled, skipping..."
        return
    fi
    
    log_info "Creating VLLM configuration..."
    
    # Create ConfigMap for VLLM configuration
    kubectl create configmap vllm-config -n vllm-system \
        --from-literal=MODEL="${MODEL}" \
        --from-literal=TENSOR_PARALLEL="${TENSOR_PARALLEL}" \
        --from-literal=GPU_MEMORY_UTIL="${GPU_MEMORY_UTIL}" \
        --from-literal=MAX_MODEL_LEN="${MAX_MODEL_LEN}" \
        --from-literal=RAY_VERSION="${RAY_VERSION}" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Create secret for HuggingFace token if provided
    if [ -n "${HF_TOKEN}" ]; then
        kubectl create secret generic hf-token -n vllm-system \
            --from-literal=token="${HF_TOKEN}" \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    # Deploy VLLM service using unified manifests
    kubectl apply -f "${SCRIPT_DIR}/storage-pvcs.yaml"
    kubectl apply -f "${SCRIPT_DIR}/vllm/vllm-deployment.yaml"
    
    # Wait for VLLM deployment
    log_info "Waiting for VLLM deployment to be ready..."
    kubectl wait --for=condition=available deployment/vllm-ray-head -n vllm-system --timeout=600s
    
    log_success "VLLM model serving deployed"
}

deploy_multiagent_chatbot() {
    show_progress "Deploying multi-agent chatbot..."
    
    if [ "${ENABLE_MULTI_AGENT}" != "1" ]; then
        log_info "Multi-agent deployment disabled, skipping..."
        return
    fi
    
    log_info "Creating multi-agent chatbot stack..."
    
    # Deploy agents using unified manifests
    kubectl apply -f "${SCRIPT_DIR}/agents/agents-deployment.yaml"
    
    # Wait for agent deployment
    log_info "Waiting for agent backend to be ready..."
    kubectl wait --for=condition=available deployment/agent-backend -n agents-system --timeout=600s
    
    log_success "Multi-agent chatbot deployed"
}

deploy_multimodal_inference() {
    show_progress "Deploying multi-modal inference..."
    
    if [ "${ENABLE_MULTIMODAL}" != "1" ]; then
        log_info "Multi-modal deployment disabled, skipping..."
        return
    fi
    
    if [ "${ENABLE_COMFYUI}" = "1" ]; then
        log_info "Deploying ComfyUI for image generation..."
        
        # Deploy ComfyUI from k8s-deployments
        kubectl apply -f "${SCRIPT_DIR}/k8s-deployments/image-gen/" -n multimodal-system
    fi
    
    log_success "Multi-modal inference deployed"
}

setup_monitoring() {
    show_progress "Setting up monitoring and observability..."
    
    if [ "${ENABLE_PROMETHEUS}" = "1" ] || [ "${ENABLE_GRAFANA}" = "1" ]; then
        log_info "Deploying monitoring stack..."
        
        # Deploy basic monitoring (simplified for this example)
        kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Service
metadata:
  name: cluster-monitoring
  namespace: monitoring-system
  labels:
    app: monitoring
spec:
  selector:
    app: monitoring
  ports:
  - name: grafana
    port: 3001
    targetPort: 3000
  - name: prometheus
    port: 9090
    targetPort: 9090
  type: LoadBalancer
EOF
    fi
    
    log_success "Monitoring stack deployed"
}

setup_cluster_ui() {
    show_progress "Setting up cluster management UI..."
    
    log_info "Starting enhanced cluster control UI..."
    
    # Copy enhanced UI to cluster-control-ui directory
    cp "${SCRIPT_DIR}/cluster-ui-enhanced.py" \
       "${SCRIPT_DIR}/cluster-control-ui/enhanced_app.py"
    
    # Start the enhanced UI
    cd "${SCRIPT_DIR}/cluster-control-ui"
    
    # Install additional dependencies for VLLM and agent monitoring
    pip install -r requirements.txt
    pip install kubernetes requests pyyaml flask
    
    # Start the enhanced UI in background
    nohup python enhanced_app.py > ui-enhanced.log 2>&1 &
    
    cd "${SCRIPT_DIR}"
    
    log_success "Enhanced cluster management UI started"
}

display_deployment_summary() {
    log_step "Deployment Summary"
    
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 Deployment Complete! 🎉                   ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║                                                                  ║"
    echo "║  📊 Management Interfaces:                                       ║"
    echo "║    • Cluster Control UI: http://$(hostname -I | awk '{print $1}'):5000      ║"
    echo "║    • Kubernetes Dashboard: https://${CONTROL_PLANE_API_IP}:6443        ║"
    echo "║    • Ray Dashboard: http://${CONTROL_PLANE_API_IP}:8265               ║"
    echo "║                                                                  ║"
    echo "║  🤖 AI Services:                                                 ║"
    echo "║    • VLLM API: http://${CONTROL_PLANE_API_IP}:8000                    ║"
    echo "║    • Agent Backend: http://${CONTROL_PLANE_API_IP}:8001               ║"
    echo "║    • Agent Frontend: http://${CONTROL_PLANE_API_IP}:3000              ║"
    if [ "${ENABLE_COMFYUI}" = "1" ]; then
    echo "║    • ComfyUI: http://${CONTROL_PLANE_API_IP}:8188                     ║"
    fi
    echo "║                                                                  ║"
    echo "║  🔍 Monitoring:                                                  ║"
    if [ "${ENABLE_GRAFANA}" = "1" ]; then
    echo "║    • Grafana: http://${CONTROL_PLANE_API_IP}:3001                     ║"
    fi
    if [ "${ENABLE_PROMETHEUS}" = "1" ]; then
    echo "║    • Prometheus: http://${CONTROL_PLANE_API_IP}:9090                  ║"
    fi
    echo "║                                                                  ║"
    echo "║  📁 Storage:                                                     ║"
    echo "║    • HF Cache: ${HF_CACHE}                                      ║"
    echo "║    • Model Cache: ${MODEL_CACHE}                                ║"
    echo "║    • Agent Data: ${AGENT_DATA}                                  ║"
    echo "║                                                                  ║"
    echo "║  🚀 Quick Start:                                                 ║"
    echo "║    kubectl get pods --all-namespaces                            ║"
    echo "║    kubectl logs -f deployment/vllm-server -n vllm-system        ║"
    echo "║                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    
    # Save deployment info
    cat > "${SCRIPT_DIR}/deployment-info.json" << EOF
{
  "deployment_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "configuration": {
    "control_plane_ip": "${CONTROL_PLANE_API_IP}",
    "worker_node": "${WORKER_NODE_NAME}",
    "model": "${MODEL}",
    "tensor_parallel": ${TENSOR_PARALLEL},
    "components": {
      "vllm": ${ENABLE_VLLM},
      "multi_agent": ${ENABLE_MULTI_AGENT},
      "multimodal": ${ENABLE_MULTIMODAL}
    }
  },
  "endpoints": {
    "vllm_api": "http://${CONTROL_PLANE_API_IP}:8000",
    "cluster_ui": "http://$(hostname -I | awk '{print $1}'):5000",
    "ray_dashboard": "http://${CONTROL_PLANE_API_IP}:8265"
  }
}
EOF
    
    log_info "Deployment information saved to deployment-info.json"
}

# Main installation flow
main() {
    display_banner
    check_prerequisites
    display_configuration
    
    # Confirm before proceeding
    echo ""
    read -p "🤔 Do you want to proceed with this configuration? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled by user."
        exit 0
    fi
    
    # Execute deployment steps
    setup_kubernetes_cluster
    create_namespaces
    setup_persistent_storage
    deploy_vllm_serving
    deploy_multiagent_chatbot
    deploy_multimodal_inference
    setup_monitoring
    setup_cluster_ui
    
    display_deployment_summary
    
    log_success "🎉 DGX Spark Multi-Agent VLLM deployment completed successfully!"
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy" | "install")
        main
        ;;
    "status")
        kubectl get pods --all-namespaces
        kubectl get services --all-namespaces
        ;;
    "logs")
        kubectl logs -f deployment/vllm-server -n vllm-system
        ;;
    "cleanup")
        log_warn "This will remove all deployed components. Are you sure?"
        read -p "Type 'DELETE' to confirm: " -r
        if [[ $REPLY == "DELETE" ]]; then
            kubectl delete namespace vllm-system agents-system multimodal-system monitoring-system
            log_info "Cleanup completed"
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|status|logs|cleanup}"
        echo "  deploy   - Deploy the complete stack (default)"
        echo "  status   - Show deployment status"
        echo "  logs     - Show VLLM server logs"
        echo "  cleanup  - Remove all components"
        exit 1
        ;;
esac