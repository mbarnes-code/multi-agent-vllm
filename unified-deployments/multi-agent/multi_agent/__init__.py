"""
DGX Spark Multi-Agent System

A VLLM-based multi-agent framework for distributed inference on DGX Spark clusters.
"""

__version__ = "0.1.0"

from .core import Swarm, Agent, Response, Result
from .agents import (
    SupervisorAgent,
    RAGAgent,
    CodingAgent,
    ImageUnderstandingAgent,
)

__all__ = [
    "Swarm",
    "Agent",
    "Response",
    "Result",
    "SupervisorAgent",
    "RAGAgent",
    "CodingAgent",
    "ImageUnderstandingAgent",
]
