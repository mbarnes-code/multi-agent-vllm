#!/usr/bin/env python3
"""
Enhanced Cluster Control UI for DGX Spark Multi-Agent VLLM Deployment
Extends the original dgx-spark-toolkit cluster UI with:
- VLLM model serving monitoring
- Multi-agent chatbot status
- Multi-modal inference tracking
- Real-time metrics dashboard
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, jsonify, request, redirect, url_for
import requests
import subprocess
from kubernetes import client, config
import yaml

# Add the original cluster-control-ui to path
sys.path.insert(0, str(Path(__file__).parent.parent / "dgx-spark-toolkit" / "cluster-control-ui"))

# Import original UI components
try:
    from app import app as original_app
    from app import *  # Import all original functions
except ImportError:
    # Create minimal Flask app if original not available
    original_app = Flask(__name__)
    logging.warning("Original cluster UI not available, using minimal version")

# Enhanced app with additional features
app = Flask(__name__, 
    template_folder=str(Path(__file__).parent.parent / "dgx-spark-toolkit" / "cluster-control-ui" / "templates"),
    static_folder=str(Path(__file__).parent.parent / "dgx-spark-toolkit" / "cluster-control-ui" / "static")
)

# Configuration
CONFIG = {
    'VLLM_NAMESPACE': 'vllm-system',
    'AGENTS_NAMESPACE': 'agents-system',
    'MULTIMODAL_NAMESPACE': 'multimodal-system',
    'UPDATE_INTERVAL': 30,  # seconds
    'HISTORY_RETENTION': 24 * 60 * 60,  # 24 hours in seconds
}

# Global state
metrics_history = {
    'vllm': [],
    'agents': [],
    'gpu': [],
    'network': []
}

# Initialize Kubernetes client
try:
    config.load_incluster_config()
except:
    try:
        config.load_kube_config()
    except:
        logging.warning("Could not load Kubernetes config")

k8s_v1 = client.CoreV1Api()
k8s_apps = client.AppsV1Api()
k8s_metrics = None

try:
    from kubernetes.client.api import custom_objects_api
    k8s_metrics = custom_objects_api.CustomObjectsApi()
except ImportError:
    logging.warning("Kubernetes metrics API not available")

def get_vllm_status() -> Dict:
    """Get VLLM service status and metrics"""
    status = {
        'healthy': False,
        'model': 'Unknown',
        'requests_per_second': 0,
        'active_sessions': 0,
        'gpu_utilization': 0,
        'queue_length': 0,
        'uptime': 'Unknown',
        'replicas': {'ready': 0, 'desired': 0}
    }
    
    try:
        # Get deployment status
        deployment = k8s_apps.read_namespaced_deployment(
            name='vllm-ray-head',
            namespace=CONFIG['VLLM_NAMESPACE']
        )
        
        status['replicas'] = {
            'ready': deployment.status.ready_replicas or 0,
            'desired': deployment.spec.replicas or 0
        }
        
        # Get service endpoint
        service = k8s_v1.read_namespaced_service(
            name='vllm-service',
            namespace=CONFIG['VLLM_NAMESPACE']
        )
        
        # Try to get VLLM metrics if accessible
        if service.status.load_balancer and service.status.load_balancer.ingress:
            external_ip = service.status.load_balancer.ingress[0].ip
            vllm_url = f"http://{external_ip}:8000"
            
            try:
                # Health check
                health_response = requests.get(f"{vllm_url}/health", timeout=5)
                if health_response.status_code == 200:
                    status['healthy'] = True
                
                # Model info
                models_response = requests.get(f"{vllm_url}/v1/models", timeout=5)
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    if models_data.get('data'):
                        status['model'] = models_data['data'][0].get('id', 'Unknown')
                
            except requests.RequestException:
                pass
        
    except Exception as e:
        logging.error(f"Error getting VLLM status: {e}")
    
    return status

def get_agents_status() -> Dict:
    """Get multi-agent system status"""
    status = {
        'backend_healthy': False,
        'database_healthy': False,
        'vector_db_healthy': False,
        'active_conversations': 0,
        'total_agents': 4,
        'agent_health': {
            'supervisor': True,
            'rag': True,
            'code_generation': True,
            'image_understanding': True
        }
    }
    
    try:
        # Check backend deployment
        deployment = k8s_apps.read_namespaced_deployment(
            name='agent-backend',
            namespace=CONFIG['AGENTS_NAMESPACE']
        )
        
        if deployment.status.ready_replicas and deployment.status.ready_replicas > 0:
            status['backend_healthy'] = True
        
        # Check PostgreSQL
        postgres_deployment = k8s_apps.read_namespaced_deployment(
            name='postgres',
            namespace=CONFIG['AGENTS_NAMESPACE']
        )
        
        if postgres_deployment.status.ready_replicas and postgres_deployment.status.ready_replicas > 0:
            status['database_healthy'] = True
        
        # Check Milvus (vector database)
        milvus_deployment = k8s_apps.read_namespaced_deployment(
            name='milvus',
            namespace=CONFIG['AGENTS_NAMESPACE']
        )
        
        if milvus_deployment.status.ready_replicas and milvus_deployment.status.ready_replicas > 0:
            status['vector_db_healthy'] = True
            
    except Exception as e:
        logging.error(f"Error getting agents status: {e}")
    
    return status

def get_gpu_metrics() -> Dict:
    """Get GPU utilization across the cluster"""
    metrics = {
        'total_gpus': 0,
        'allocated_gpus': 0,
        'utilization': [],
        'memory_usage': [],
        'temperature': []
    }
    
    try:
        # Get nodes with GPU resources
        nodes = k8s_v1.list_node()
        
        for node in nodes.items:
            if 'nvidia.com/gpu' in node.status.allocatable:
                gpu_count = int(node.status.allocatable['nvidia.com/gpu'])
                metrics['total_gpus'] += gpu_count
                
                # Get allocated GPUs from pods
                pods = k8s_v1.list_pod_for_all_namespaces(
                    field_selector=f'spec.nodeName={node.metadata.name}'
                )
                
                allocated = 0
                for pod in pods.items:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            gpu_req = container.resources.requests.get('nvidia.com/gpu')
                            if gpu_req:
                                allocated += int(gpu_req)
                
                metrics['allocated_gpus'] += allocated
        
        # Try to get nvidia-smi data if available
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,temperature.gpu', 
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line:
                        util, mem, temp = map(float, line.split(', '))
                        metrics['utilization'].append(util)
                        metrics['memory_usage'].append(mem)
                        metrics['temperature'].append(temp)
        
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            # nvidia-smi not available or failed
            pass
            
    except Exception as e:
        logging.error(f"Error getting GPU metrics: {e}")
    
    return metrics

def get_unified_status() -> Dict:
    """Get comprehensive system status"""
    return {
        'timestamp': datetime.now().isoformat(),
        'vllm': get_vllm_status(),
        'agents': get_agents_status(),
        'gpu': get_gpu_metrics(),
        'cluster': {
            'nodes_ready': 0,
            'pods_running': 0,
            'services_active': 0
        }
    }

# Enhanced routes
@app.route('/api/unified-status')
def api_unified_status():
    """API endpoint for unified system status"""
    return jsonify(get_unified_status())

@app.route('/api/vllm/models')
def api_vllm_models():
    """Get available VLLM models"""
    models = ['gpt-oss-120b', 'gpt-oss-20b', 'llama-3.1-8b-instruct']
    return jsonify({'models': models})

@app.route('/api/agents/chat', methods=['POST'])
def api_agents_chat():
    """Proxy chat requests to agent backend"""
    try:
        # Get agent backend service
        service = k8s_v1.read_namespaced_service(
            name='agent-backend',
            namespace=CONFIG['AGENTS_NAMESPACE']
        )
        
        if service.status.load_balancer and service.status.load_balancer.ingress:
            backend_ip = service.status.load_balancer.ingress[0].ip
            backend_url = f"http://{backend_ip}:8000"
            
            # Forward request to agent backend
            response = requests.post(
                f"{backend_url}/chat",
                json=request.json,
                timeout=30
            )
            
            return jsonify(response.json()), response.status_code
        else:
            return jsonify({'error': 'Agent backend not accessible'}), 503
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/unified-dashboard')
def unified_dashboard():
    """Enhanced dashboard with unified monitoring"""
    status = get_unified_status()
    return render_template('unified_dashboard.html', status=status)

# Background metrics collection
async def collect_metrics():
    """Background task to collect metrics"""
    while True:
        try:
            current_time = time.time()
            status = get_unified_status()
            
            # Add to history
            for category in ['vllm', 'agents', 'gpu']:
                metrics_history[category].append({
                    'timestamp': current_time,
                    'data': status[category]
                })
                
                # Clean old data
                cutoff = current_time - CONFIG['HISTORY_RETENTION']
                metrics_history[category] = [
                    m for m in metrics_history[category] 
                    if m['timestamp'] > cutoff
                ]
            
            await asyncio.sleep(CONFIG['UPDATE_INTERVAL'])
            
        except Exception as e:
            logging.error(f"Error in metrics collection: {e}")
            await asyncio.sleep(CONFIG['UPDATE_INTERVAL'])

@app.route('/api/metrics/history')
def api_metrics_history():
    """Get historical metrics data"""
    return jsonify(metrics_history)

# Copy original routes if available
if original_app:
    for rule in original_app.url_map.iter_rules():
        if rule.endpoint not in ['static', 'api_unified_status', 'api_vllm_models', 
                                'api_agents_chat', 'unified_dashboard', 'api_metrics_history']:
            try:
                view_func = original_app.view_functions[rule.endpoint]
                app.add_url_rule(
                    rule.rule,
                    endpoint=rule.endpoint,
                    view_func=view_func,
                    methods=rule.methods
                )
            except KeyError:
                pass

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start metrics collection in background
    import threading
    
    def run_metrics_collection():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_metrics())
    
    metrics_thread = threading.Thread(target=run_metrics_collection, daemon=True)
    metrics_thread.start()
    
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )