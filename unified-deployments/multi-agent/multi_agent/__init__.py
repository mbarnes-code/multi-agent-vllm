"""
DGX Spark Multi-Agent System

A VLLM-based multi-agent framework for distributed inference on DGX Spark clusters.

Features:
- Swarm-style agent orchestration
- Specialized agents for coding, RAG, and image understanding
- Comprehensive coding tools adapted from claude-quickstarts
- Security-validated code execution
- Persistent memory storage
"""

__version__ = "0.2.0"

from .core import Swarm, Agent, Response, Result
from .agents import (
    SupervisorAgent,
    RAGAgent,
    ImageUnderstandingAgent,
    create_supervisor_agent,
    create_rag_agent,
    create_coding_agent,
    create_image_agent,
)

__all__ = [
    # Core
    "Swarm",
    "Agent",
    "Response",
    "Result",
    # Agent classes
    "SupervisorAgent",
    "RAGAgent",
    "ImageUnderstandingAgent",
    # Agent factory functions
    "create_supervisor_agent",
    "create_rag_agent",
    "create_coding_agent",
    "create_image_agent",
]
