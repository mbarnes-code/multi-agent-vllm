"""
Supervisor Agent - Routes requests to specialized agents.

The supervisor analyzes incoming requests and delegates to the appropriate
specialized agent (RAG, Coding, Image Understanding).
"""

from typing import Callable, Dict, Optional
from ..core import Agent, Result

SUPERVISOR_INSTRUCTIONS = """You are a Supervisor Agent coordinating a team of specialized AI agents.

Your role is to:
1. Analyze incoming user requests
2. Determine which specialized agent is best suited to handle the request
3. Route the request to the appropriate agent
4. Synthesize responses when multiple agents are needed

Available specialized agents:
- **RAG Agent**: For questions requiring knowledge retrieval, document search, or factual information
- **Coding Agent**: For code generation, debugging, code review, and software development tasks
- **Image Understanding Agent**: For image analysis, visual questions, and multimodal tasks

When routing requests:
- Be decisive - choose the most appropriate agent
- For ambiguous requests, ask clarifying questions
- For complex tasks, break them down and coordinate multiple agents
- Always explain your routing decision briefly

You have access to the following tools to transfer control to specialized agents:
- transfer_to_rag_agent: For knowledge and retrieval tasks
- transfer_to_coding_agent: For programming and development tasks
- transfer_to_image_agent: For visual and multimodal tasks

If a request doesn't clearly fit any specialized agent, handle it yourself as a general assistant."""


class SupervisorAgent:
    """Factory for creating supervisor agents with routing capabilities."""
    
    def __init__(
        self,
        model: str = "gpt-oss-120b",
        rag_agent: Optional[Agent] = None,
        coding_agent: Optional[Agent] = None,
        image_agent: Optional[Agent] = None,
    ):
        self.model = model
        self.rag_agent = rag_agent
        self.coding_agent = coding_agent
        self.image_agent = image_agent
        
    def _create_transfer_functions(self) -> list:
        """Create transfer functions for agent handoffs."""
        functions = []
        
        if self.rag_agent:
            def transfer_to_rag_agent() -> Result:
                """Transfer to RAG Agent for knowledge retrieval and document search tasks."""
                return Result(agent=self.rag_agent)
            functions.append(transfer_to_rag_agent)
            
        if self.coding_agent:
            def transfer_to_coding_agent() -> Result:
                """Transfer to Coding Agent for programming, code generation, and development tasks."""
                return Result(agent=self.coding_agent)
            functions.append(transfer_to_coding_agent)
            
        if self.image_agent:
            def transfer_to_image_agent() -> Result:
                """Transfer to Image Understanding Agent for visual analysis and multimodal tasks."""
                return Result(agent=self.image_agent)
            functions.append(transfer_to_image_agent)
            
        return functions
    
    def create(self) -> Agent:
        """Create the supervisor agent with routing functions."""
        return Agent(
            name="Supervisor",
            model=self.model,
            instructions=SUPERVISOR_INSTRUCTIONS,
            functions=self._create_transfer_functions(),
        )


def create_supervisor_agent(
    model: str = "gpt-oss-120b",
    rag_agent: Optional[Agent] = None,
    coding_agent: Optional[Agent] = None,
    image_agent: Optional[Agent] = None,
) -> Agent:
    """
    Create a supervisor agent with routing to specialized agents.
    
    Args:
        model: Model to use for the supervisor
        rag_agent: RAG agent for knowledge retrieval
        coding_agent: Coding agent for development tasks
        image_agent: Image agent for visual tasks
        
    Returns:
        Configured supervisor Agent
    """
    factory = SupervisorAgent(
        model=model,
        rag_agent=rag_agent,
        coding_agent=coding_agent,
        image_agent=image_agent,
    )
    return factory.create()
