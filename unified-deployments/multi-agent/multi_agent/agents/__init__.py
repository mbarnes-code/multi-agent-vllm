"""
Pre-configured agents for DGX Spark multi-agent system.

Provides factory functions for creating specialized agents:
- Supervisor: Routes requests to appropriate agents
- RAG: Retrieval-augmented generation for knowledge queries
- Coding: Code generation, debugging, testing, and review (enhanced with tools from claude-quickstarts)
- Image: Image understanding and analysis
"""

from .supervisor import SupervisorAgent, create_supervisor_agent
from .rag import RAGAgent, create_rag_agent
from .coding import create_coding_agent
from .image_understanding import ImageUnderstandingAgent, create_image_agent

__all__ = [
    "SupervisorAgent",
    "create_supervisor_agent",
    "RAGAgent",
    "create_rag_agent",
    "create_coding_agent",
    "ImageUnderstandingAgent",
    "create_image_agent",
]
