#!/usr/bin/env bash
set -euo pipefail

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Unified DGX Spark Configuration Validator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

validate_config() {
    echo "🔍 Validating unified configuration..."
    
    local config_file="${SCRIPT_DIR}/unified-config.env"
    local local_config="${SCRIPT_DIR}/unified-config.local.env"
    
    if [[ ! -f "$config_file" ]]; then
        log_error "Main configuration file not found: $config_file"
        return 1
    fi
    log_success "Main configuration file found"
    
    if [[ -f "$local_config" ]]; then
        log_success "Local configuration override found"
        source "$local_config"
    else
        log_warning "No local configuration override (recommended for customization)"
        source "$config_file"
    fi
    
    # Validate required network settings
    if [[ -z "${CONTROL_PLANE_API_IP:-}" ]]; then
        log_error "CONTROL_PLANE_API_IP not set"
        return 1
    fi
    log_success "Control plane IP configured: ${CONTROL_PLANE_API_IP}"
    
    if [[ -z "${WORKER_NODE_SSH_TARGET:-}" ]]; then
        log_error "WORKER_NODE_SSH_TARGET not set"
        return 1
    fi
    log_success "Worker node SSH target configured: ${WORKER_NODE_SSH_TARGET}"
    
    # Validate model settings
    if [[ -z "${MODEL:-}" ]]; then
        log_error "MODEL not set"
        return 1
    fi
    log_success "Primary model configured: ${MODEL}"
    
    if [[ -z "${HF_TOKEN:-}" ]]; then
        log_warning "HF_TOKEN not set (required for gated models like Llama)"
    else
        log_success "HuggingFace token configured"
    fi
    
    return 0
}

validate_prerequisites() {
    echo "🔧 Checking prerequisites..."
    
    # Check required commands
    local required_commands=(kubectl helm docker ssh nvidia-smi)
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            log_success "$cmd found"
        else\n            log_error "$cmd not found"
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing_commands[*]}"
        return 1
    fi
    
    # Check GPU availability
    if nvidia-smi >/dev/null 2>&1; then
        local gpu_count=$(nvidia-smi --list-gpus | wc -l)
        log_success "$gpu_count GPUs detected"
    else
        log_error "No NVIDIA GPUs detected or nvidia-smi failed"
        return 1
    fi
    
    # Check InfiniBand (optional)
    if command -v ibdev2netdev >/dev/null 2>&1; then
        if ibdev2netdev >/dev/null 2>&1; then
            log_success "InfiniBand interfaces detected"
        else
            log_warning "InfiniBand tools present but no interfaces found"
        fi
    else
        log_warning "InfiniBand tools not found (high-speed fabric features will be limited)"
    fi
    
    return 0
}

validate_network_connectivity() {
    echo "🌐 Testing network connectivity..."
    
    source "${SCRIPT_DIR}/unified-config.local.env" 2>/dev/null || source "${SCRIPT_DIR}/unified-config.env"
    
    # Test SSH connectivity to worker
    if [[ -n "${WORKER_NODE_SSH_TARGET:-}" ]]; then
        if ssh -o ConnectTimeout=5 -o BatchMode=yes "${WORKER_NODE_SSH_USER:-${USER}}@${WORKER_NODE_SSH_TARGET}" "hostname" >/dev/null 2>&1; then
            log_success "SSH connectivity to worker node verified"
        else
            log_error "Cannot SSH to worker node: ${WORKER_NODE_SSH_TARGET}"
            log_error "Ensure SSH keys are configured and worker is accessible"
            return 1
        fi
    fi
    
    # Test network interfaces
    if [[ -n "${CONTROL_PLANE_INTERFACE:-}" ]]; then
        if ip link show "${CONTROL_PLANE_INTERFACE}" >/dev/null 2>&1; then
            log_success "Control plane interface exists: ${CONTROL_PLANE_INTERFACE}"
        else
            log_error "Control plane interface not found: ${CONTROL_PLANE_INTERFACE}"
            return 1
        fi
    fi
    
    if [[ -n "${FABRIC_CTRL_INTERFACE:-}" ]]; then
        if ip link show "${FABRIC_CTRL_INTERFACE}" >/dev/null 2>&1; then
            log_success "Fabric interface exists: ${FABRIC_CTRL_INTERFACE}"
        else
            log_warning "Fabric interface not found: ${FABRIC_CTRL_INTERFACE} (optional)"
        fi
    fi
    
    return 0
}

validate_storage() {
    echo "💾 Checking storage requirements..."
    
    source "${SCRIPT_DIR}/unified-config.local.env" 2>/dev/null || source "${SCRIPT_DIR}/unified-config.env"
    
    local storage_paths=(
        "${HF_CACHE:-/raid/hf-cache}"
        "${MODEL_CACHE:-/raid/model-cache}"
        "${AGENT_DATA:-/raid/agent-data}"
    )
    
    for path in "${storage_paths[@]}"; do
        local parent_dir=$(dirname "$path")
        if [[ -d "$parent_dir" ]]; then
            local available_space=$(df -h "$parent_dir" | awk 'NR==2 {print $4}')\n            log_success "Storage path parent accessible: $parent_dir ($available_space available)"
        else
            log_error "Storage path parent not found: $parent_dir"
            return 1
        fi
    done
    
    return 0
}

validate_manifests() {
    echo "📋 Validating Kubernetes manifests..."
    
    local manifest_dirs=(
        "${SCRIPT_DIR}/unified-deployments/vllm"
        "${SCRIPT_DIR}/unified-deployments/agents"
        "${SCRIPT_DIR}/unified-deployments"
    )
    
    for dir in "${manifest_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log_success "Manifest directory found: $dir"
            
            # Check YAML syntax
            for yaml_file in "$dir"/*.yaml; do
                if [[ -f "$yaml_file" ]]; then
                    if python3 -c "import yaml; yaml.safe_load(open('$yaml_file'))" >/dev/null 2>&1; then
                        log_success "YAML syntax valid: $(basename "$yaml_file")"
                    else
                        log_error "YAML syntax invalid: $(basename "$yaml_file")"
                        return 1
                    fi
                fi
            done
        else
            log_error "Manifest directory not found: $dir"
            return 1
        fi
    done
    
    return 0
}

test_configuration() {
    echo "🧪 Testing deployment configuration (dry-run)..."
    
    # Test configuration loading
    if "${SCRIPT_DIR}/deploy-unified.sh" --dry-run 2>/dev/null; then
        log_success "Deployment script configuration test passed"
    else
        log_error "Deployment script configuration test failed"
        return 1
    fi
    
    return 0
}

generate_summary() {
    echo ""
    echo "📊 Validation Summary"
    echo "===================="
    
    source "${SCRIPT_DIR}/unified-config.local.env" 2>/dev/null || source "${SCRIPT_DIR}/unified-config.env"
    
    echo "Configuration:"
    echo "  • Control Plane: ${CONTROL_PLANE_API_IP:-Not set}"
    echo "  • Worker Node: ${WORKER_NODE_SSH_TARGET:-Not set}"
    echo "  • Primary Model: ${MODEL:-Not set}"
    echo "  • Tensor Parallel: ${TENSOR_PARALLEL:-Not set}"
    echo ""
    echo "Components to Deploy:"
    echo "  • VLLM: $([ "${ENABLE_VLLM:-1}" = "1" ] && echo "✓" || echo "✗")"
    echo "  • Multi-Agent: $([ "${ENABLE_MULTI_AGENT:-1}" = "1" ] && echo "✓" || echo "✗")"
    echo "  • Multi-Modal: $([ "${ENABLE_MULTIMODAL:-1}" = "1" ] && echo "✓" || echo "✗")"
    echo "  • Dashboard: $([ "${ENABLE_K8S_DASHBOARD:-1}" = "1" ] && echo "✓" || echo "✗")"
    echo ""
}

main() {
    echo "🚀 Unified DGX Spark Configuration Validator"
    echo "============================================"
    echo ""
    
    local validation_steps=(
        validate_config
        validate_prerequisites  
        validate_network_connectivity
        validate_storage
        validate_manifests
    )\n    \n    local failed_steps=()\n    \n    for step in "${validation_steps[@]}"; do\n        if ! $step; then\n            failed_steps+=("$step")\n        fi\n        echo ""\n    done\n    \n    generate_summary\n    \n    if [[ ${#failed_steps[@]} -eq 0 ]]; then\n        echo "✅ All validations passed! Ready to deploy."\n        echo ""\n        echo "Next steps:"\n        echo "  1. Review configuration in unified-config.env"\n        echo "  2. Create unified-config.local.env for local overrides"\n        echo "  3. Run: ./deploy-unified.sh"\n        return 0\n    else\n        echo "❌ Validation failed. Please fix the following issues:"\n        for step in "${failed_steps[@]}"; do\n            echo "  • $step"\n        done\n        echo ""\n        echo "See README-unified.md for troubleshooting guidance."\n        return 1\n    fi\n}\n\n# Handle command line arguments\ncase "${1:-validate}" in\n    "validate" | "")\n        main\n        ;;\n    "config")\n        validate_config\n        ;;\n    "prereq")\n        validate_prerequisites\n        ;;\n    "network")\n        validate_network_connectivity\n        ;;\n    "storage")\n        validate_storage\n        ;;\n    "manifests")\n        validate_manifests\n        ;;\n    *)\n        echo "Usage: $0 {validate|config|prereq|network|storage|manifests}"\n        echo "  validate  - Run all validation checks (default)"\n        echo "  config    - Validate configuration files only"\n        echo "  prereq    - Check prerequisites only"\n        echo "  network   - Test network connectivity only"\n        echo "  storage   - Check storage requirements only"\n        echo "  manifests - Validate Kubernetes manifests only"\n        exit 1\n        ;;\nesac