"""
Pre-configured agents for DGX Spark multi-agent system.
"""

from .supervisor import SupervisorAgent, create_supervisor_agent
from .rag import RAGAgent, create_rag_agent
from .coding import CodingAgent, create_coding_agent
from .image_understanding import ImageUnderstandingAgent, create_image_agent

__all__ = [
    "SupervisorAgent",
    "create_supervisor_agent",
    "RAGAgent",
    "create_rag_agent",
    "CodingAgent",
    "create_coding_agent",
    "ImageUnderstandingAgent",
    "create_image_agent",
]
