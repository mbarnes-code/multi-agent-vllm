"""
FastAPI server for the multi-agent system.

Provides REST API endpoints for interacting with the agent swarm.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from .core import Swarm, Agent, Response
from .agents import (
    create_supervisor_agent,
    create_rag_agent,
    create_coding_agent,
    create_image_agent,
)

logger = structlog.get_logger()

# Configuration from environment
VLLM_ENDPOINT = os.getenv("VLLM_ENDPOINT", "http://vllm-service.vllm-system.svc.cluster.local:8000/v1")
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", "gpt-oss-120b")
RAG_MODEL = os.getenv("RAG_MODEL", "gpt-oss-20b")
CODING_MODEL = os.getenv("CODING_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "microsoft/Phi-4")
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/tmp/coding_workspace")
ENABLE_CODE_EXECUTION = os.getenv("ENABLE_CODE_EXECUTION", "true").lower() == "true"

# Global state
swarm: Optional[Swarm] = None
agents: Dict[str, Agent] = {}
sessions: Dict[str, Dict[str, Any]] = {}


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message")
    session_id: str = Field(default="default", description="Session identifier")
    agent_type: Optional[str] = Field(default=None, description="Specific agent to use (supervisor, rag, coding, image)")
    stream: bool = Field(default=False, description="Enable streaming response")
    context_variables: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Agent response")
    agent_name: str = Field(..., description="Name of responding agent")
    session_id: str = Field(..., description="Session identifier")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation messages")


class AgentInfo(BaseModel):
    """Information about an available agent."""
    name: str
    model: str
    description: str
    capabilities: List[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    vllm_endpoint: str
    agents_loaded: List[str]
    version: str


def initialize_agents():
    """Initialize all agents with their configurations."""
    global swarm, agents
    
    logger.info("initializing_agents", vllm_endpoint=VLLM_ENDPOINT)
    
    # Initialize Swarm with VLLM backend
    swarm = Swarm(base_url=VLLM_ENDPOINT)
    
    # Create specialized agents
    rag_agent = create_rag_agent(
        model=RAG_MODEL,
        milvus_host=MILVUS_HOST,
        milvus_port=MILVUS_PORT,
    )
    
    coding_agent = create_coding_agent(
        model=CODING_MODEL,
        workspace_dir=WORKSPACE_DIR,
        enable_execution=ENABLE_CODE_EXECUTION,
    )
    
    image_agent = create_image_agent(
        model=IMAGE_MODEL,
    )
    
    # Create supervisor with access to all agents
    supervisor_agent = create_supervisor_agent(
        model=SUPERVISOR_MODEL,
        rag_agent=rag_agent,
        coding_agent=coding_agent,
        image_agent=image_agent,
    )
    
    # Store agents
    agents = {
        "supervisor": supervisor_agent,
        "rag": rag_agent,
        "coding": coding_agent,
        "image": image_agent,
    }
    
    logger.info("agents_initialized", agents=list(agents.keys()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    initialize_agents()
    yield
    # Shutdown
    logger.info("shutting_down")


# Create FastAPI app
app = FastAPI(
    title="DGX Spark Multi-Agent API",
    description="Multi-agent system powered by VLLM on DGX Spark",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    return HealthResponse(
        status="healthy",
        vllm_endpoint=VLLM_ENDPOINT,
        agents_loaded=list(agents.keys()),
        version="0.1.0",
    )


@app.get("/agents", response_model=List[AgentInfo])
async def list_agents():
    """List available agents and their capabilities."""
    agent_info = {
        "supervisor": AgentInfo(
            name="Supervisor",
            model=SUPERVISOR_MODEL,
            description="Routes requests to specialized agents",
            capabilities=["routing", "coordination", "general_assistance"],
        ),
        "rag": AgentInfo(
            name="RAG Agent",
            model=RAG_MODEL,
            description="Knowledge retrieval and document search",
            capabilities=["search", "retrieval", "summarization", "qa"],
        ),
        "coding": AgentInfo(
            name="Coding Agent",
            model=CODING_MODEL,
            description="Code generation and development tasks",
            capabilities=["code_generation", "debugging", "code_review", "testing"],
        ),
        "image": AgentInfo(
            name="Image Understanding Agent",
            model=IMAGE_MODEL,
            description="Visual analysis and multimodal tasks",
            capabilities=["image_analysis", "ocr", "visual_qa"],
        ),
    }
    return [agent_info[name] for name in agents.keys()]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the multi-agent system.
    
    The supervisor agent will route the request to the appropriate
    specialized agent, or you can specify an agent directly.
    """
    if swarm is None:
        raise HTTPException(status_code=503, detail="Agents not initialized")
    
    # Get or create session
    session = sessions.setdefault(request.session_id, {
        "messages": [],
        "context_variables": {},
    })
    
    # Update context
    session["context_variables"].update(request.context_variables)
    
    # Add user message to history
    session["messages"].append({
        "role": "user",
        "content": request.message,
    })
    
    # Select agent
    agent_type = request.agent_type or "supervisor"
    if agent_type not in agents:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type: {agent_type}. Available: {list(agents.keys())}",
        )
    
    agent = agents[agent_type]
    
    logger.info(
        "chat_request",
        session_id=request.session_id,
        agent=agent_type,
        message_length=len(request.message),
    )
    
    try:
        # Run agent
        response = swarm.run(
            agent=agent,
            messages=session["messages"],
            context_variables=session["context_variables"],
            stream=False,
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )
        
        # Update session with new messages
        session["messages"].extend(response.messages)
        session["context_variables"].update(response.context_variables)
        
        # Extract response text
        response_text = ""
        for msg in response.messages:
            if msg.get("role") == "assistant" and msg.get("content"):
                response_text = msg["content"]
                break
        
        return ChatResponse(
            response=response_text,
            agent_name=response.agent.name if response.agent else agent.name,
            session_id=request.session_id,
            messages=response.messages,
        )
        
    except Exception as e:
        logger.error("chat_error", error=str(e), session_id=request.session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream a response from the multi-agent system.
    
    Returns Server-Sent Events (SSE) with incremental response chunks.
    """
    if swarm is None:
        raise HTTPException(status_code=503, detail="Agents not initialized")
    
    # Get or create session
    session = sessions.setdefault(request.session_id, {
        "messages": [],
        "context_variables": {},
    })
    
    session["context_variables"].update(request.context_variables)
    session["messages"].append({
        "role": "user",
        "content": request.message,
    })
    
    agent_type = request.agent_type or "supervisor"
    if agent_type not in agents:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_type}")
    
    agent = agents[agent_type]
    
    async def generate():
        try:
            response_gen = swarm.run(
                agent=agent,
                messages=session["messages"],
                context_variables=session["context_variables"],
                stream=True,
            )
            
            for chunk in response_gen:
                if "content" in chunk:
                    yield f"data: {chunk['content']}\n\n"
                elif "response" in chunk:
                    # Final response
                    session["messages"].extend(chunk["response"].messages)
                    yield f"data: [DONE]\n\n"
                    
        except Exception as e:
            logger.error("stream_error", error=str(e))
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Clear a chat session."""
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session history."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@app.post("/code/execute")
async def execute_code(code: str, language: str = "python"):
    """
    Execute code directly (bypasses agent).
    
    Use with caution - this endpoint is for testing purposes.
    """
    if not ENABLE_CODE_EXECUTION:
        raise HTTPException(status_code=403, detail="Code execution is disabled")
    
    coding_agent = agents.get("coding")
    if not coding_agent:
        raise HTTPException(status_code=503, detail="Coding agent not available")
    
    # Find the execute_code function
    for func in coding_agent.functions:
        if func.__name__ == "execute_code":
            result = func(code=code, language=language)
            return {"result": result}
    
    raise HTTPException(status_code=500, detail="Execute function not found")


def main():
    """Run the server."""
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "multi_agent.server:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
