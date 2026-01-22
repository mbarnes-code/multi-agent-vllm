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
from .precision import create_precision_enhanced_swarm, VotingConfig, ErrorRecoveryManager
from .cross_validation import ValidationLevel
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

# Precision enhancement configuration
ENABLE_CONSENSUS_VOTING = os.getenv("ENABLE_CONSENSUS_VOTING", "true").lower() == "true"
WINNING_VOTE_COUNT = int(os.getenv("WINNING_VOTE_COUNT", "2"))
CONSENSUS_TIMEOUT = float(os.getenv("CONSENSUS_TIMEOUT", "20.0"))
PARALLEL_VOTING = os.getenv("PARALLEL_VOTING", "true").lower() == "true"

# Global state
swarm: Optional[Any] = None  # Will be PrecisionEnhancedSwarm
agents: Dict[str, Agent] = {}
sessions: Dict[str, Dict[str, Any]] = {}
supervisor_factory: Optional[Any] = None  # SupervisorAgent factory for consensus access
error_recovery_manager: Optional[ErrorRecoveryManager] = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message")
    session_id: str = Field(default="default", description="Session identifier")
    agent_type: Optional[str] = Field(default=None, description="Specific agent to use (supervisor, rag, coding, image)")
    stream: bool = Field(default=False, description="Enable streaming response")
    context_variables: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    enable_consensus: bool = Field(default=True, description="Enable consensus voting for routing")
    max_decomposition_depth: int = Field(default=3, description="Maximum recursive task decomposition depth")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Agent response")
    agent_name: str = Field(..., description="Name of responding agent")
    session_id: str = Field(..., description="Session identifier")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation messages")
    consensus_info: Optional[Dict[str, Any]] = Field(default=None, description="Consensus voting information")
    trace_summary: Optional[Dict[str, Any]] = Field(default=None, description="Precision trace summary")


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
    """Initialize all agents with precision enhancements."""
    global swarm, agents, supervisor_factory, error_recovery_manager
    
    logger.info("initializing_precision_enhanced_agents", vllm_endpoint=VLLM_ENDPOINT)
    
    # Initialize Precision-Enhanced Swarm with VLLM backend
    PrecisionEnhancedSwarm = create_precision_enhanced_swarm()
    swarm = PrecisionEnhancedSwarm(base_url=VLLM_ENDPOINT)
    
    # Configure voting for precision/performance balance
    voting_config = VotingConfig(
        winning_vote_count=WINNING_VOTE_COUNT,
        consensus_timeout_seconds=CONSENSUS_TIMEOUT,
        parallel_voting=PARALLEL_VOTING,
        early_termination=True,  # 40% performance consideration
        confidence_threshold=0.6,  # 60% precision focus
    )
    
    # Initialize error recovery manager
    error_recovery_manager = ErrorRecoveryManager()
    
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
    
    # Create precision-enhanced supervisor with consensus voting
    supervisor_agent = create_supervisor_agent(
        model=SUPERVISOR_MODEL,
        rag_agent=rag_agent,
        coding_agent=coding_agent,
        image_agent=image_agent,
        enable_consensus_voting=ENABLE_CONSENSUS_VOTING,
        voting_config=voting_config,
    )
    
    # Store supervisor factory for accessing consensus features
    from .agents.supervisor import SupervisorAgent
    supervisor_factory = SupervisorAgent(
        model=SUPERVISOR_MODEL,
        rag_agent=rag_agent,
        coding_agent=coding_agent,
        image_agent=image_agent,
        enable_consensus_voting=ENABLE_CONSENSUS_VOTING,
        voting_config=voting_config,
    )
    
    # Store agents
    agents = {
        "supervisor": supervisor_agent,
        "rag": rag_agent,
        "coding": coding_agent,
        "image": image_agent,
    }
    
    logger.info(
        "precision_enhanced_agents_initialized",
        agents=list(agents.keys()),
        consensus_voting=ENABLE_CONSENSUS_VOTING,
        voting_config=voting_config.__dict__
    )


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
        # Check if precision-enhanced routing is requested
        if (request.enable_consensus and 
            agent_type == "supervisor" and 
            ENABLE_CONSENSUS_VOTING and
            hasattr(swarm, 'run_with_consensus')):
            
            # Use precision-enhanced swarm with consensus voting
            available_agents = supervisor_factory.get_available_agents() if supervisor_factory else agents
            
            response = await swarm.run_with_consensus(
                agent=agent,
                messages=session["messages"],
                context_variables=session["context_variables"],
                available_agents=available_agents,
                enable_voting=True,
            )
            
            # Extract consensus information
            consensus_info = session["context_variables"].get("_voting_result")
            trace_summary = swarm.get_session_trace() if hasattr(swarm, 'get_session_trace') else None
            
        else:
            # Standard execution
            response = swarm.run(
                agent=agent,
                messages=session["messages"],
                context_variables=session["context_variables"],
                stream=False,
                debug=os.getenv("DEBUG", "false").lower() == "true",
            )
            consensus_info = None
            trace_summary = None
        
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
            consensus_info=consensus_info,
            trace_summary=trace_summary,
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
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


# Precision Enhancement Endpoints

@app.get("/precision/config")
async def get_precision_config():
    """Get current precision enhancement configuration."""
    return {
        "consensus_voting_enabled": ENABLE_CONSENSUS_VOTING,
        "winning_vote_count": WINNING_VOTE_COUNT,
        "consensus_timeout": CONSENSUS_TIMEOUT,
        "parallel_voting": PARALLEL_VOTING,
        "precision_performance_ratio": "60/40",
    }


@app.get("/precision/traces/{session_id}")
async def get_session_traces(session_id: str):
    """Get precision traces for a specific session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if swarm and hasattr(swarm, 'export_traces'):
        traces = swarm.export_traces(format="json")
        return {"session_id": session_id, "traces": traces}
    
    return {"session_id": session_id, "traces": "Tracing not available"}


class TaskDecompositionRequest(BaseModel):
    """Request for recursive task decomposition."""
    task: str = Field(..., description="Complex task to decompose")
    max_depth: int = Field(default=3, description="Maximum decomposition depth")
    session_id: str = Field(default="default", description="Session identifier")


class TaskDecompositionResponse(BaseModel):
    """Response with decomposed task structure."""
    original_task: str
    decomposition_tree: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    estimated_complexity: float
    session_id: str


@app.post("/precision/decompose", response_model=TaskDecompositionResponse)
async def decompose_task(request: TaskDecompositionRequest):
    """
    Decompose a complex task into atomic, manageable subtasks.
    
    Uses recursive task decomposition inspired by neuro-san methodology
    to break down complex requests into verifiable atomic operations.
    """
    # This is a placeholder for future implementation of recursive task decomposition
    # Would integrate with the coding agent's recursive reasoning capabilities
    
    decomposition_tree = {
        "root": {
            "task": request.task,
            "complexity": "high",
            "subtasks": [
                {
                    "id": "subtask_1",
                    "description": f"Analyze requirements for: {request.task[:100]}...",
                    "complexity": "medium",
                    "agent": "rag",
                    "estimated_time": 30,
                },
                {
                    "id": "subtask_2", 
                    "description": f"Implement core functionality for: {request.task[:100]}...",
                    "complexity": "high",
                    "agent": "coding",
                    "estimated_time": 120,
                },
                {
                    "id": "subtask_3",
                    "description": f"Validate and test implementation",
                    "complexity": "medium", 
                    "agent": "coding",
                    "estimated_time": 60,
                }
            ]
        }
    }
    
    execution_plan = [
        {"step": 1, "subtask_id": "subtask_1", "agent": "rag", "parallel": False},
        {"step": 2, "subtask_id": "subtask_2", "agent": "coding", "parallel": False},
        {"step": 3, "subtask_id": "subtask_3", "agent": "coding", "parallel": False},
    ]
    
    return TaskDecompositionResponse(
        original_task=request.task,
        decomposition_tree=decomposition_tree,
        execution_plan=execution_plan,
        estimated_complexity=0.8,  # High complexity
        session_id=request.session_id,
    )


class ValidationRequest(BaseModel):
    """Request for cross-agent validation."""
    primary_response: str = Field(..., description="Primary agent response to validate")
    primary_agent: str = Field(..., description="Agent that generated the response")
    validation_level: str = Field(default="semantic", description="Validation level: basic, semantic, consensus, comprehensive")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for validation")
    validation_agents: List[str] = Field(default=["rag", "coding"], description="Agents to use for validation")
    session_id: str = Field(default="default", description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for validation")
    validation_agents: List[str] = Field(default=["rag", "coding"], description="Agents to use for validation")
    session_id: str = Field(default="default", description="Session identifier")


class ValidationResponse(BaseModel):
    """Response from cross-agent validation."""
    primary_response: str
    validation_passed: bool
    confidence: float
    validation_level: str
    checks_performed: List[str]
    issues_found: List[str]
    recommendations: List[str]
    consensus_scores: Optional[Dict[str, float]]
    execution_time: Optional[float]
    session_id: str


@app.post("/precision/validate", response_model=ValidationResponse)
async def validate_response(request: ValidationRequest):
    """
    Perform cross-agent validation of a response using the precision-enhanced validation system.
    
    Uses the CrossAgentValidator to validate correctness, completeness,
    and accuracy of a primary agent's response.
    """
    if swarm is None:
        raise HTTPException(status_code=503, detail="Agents not initialized")
    
    if supervisor_factory is None:
        raise HTTPException(status_code=503, detail="Supervisor factory not initialized")
    
    # Parse validation level
    try:
        validation_level = ValidationLevel(request.validation_level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid validation level: {request.validation_level}. Must be one of: basic, semantic, consensus, comprehensive"
        )
    
    # Create a Response object from the primary response
    primary_response = Response(
        messages=[{"role": "assistant", "content": request.primary_response}],
        agent=agents.get(request.primary_agent),
    )
    
    try:
        # Use supervisor's validation functionality
        validation_result = await supervisor_factory.validate_response(
            response=primary_response,
            validation_level=validation_level,
            context=request.context,
        )
        
        return ValidationResponse(
            primary_response=request.primary_response,
            validation_passed=validation_result.passed,
            confidence=validation_result.confidence,
            validation_level=validation_result.validation_level.value,
            checks_performed=validation_result.checks_performed,
            issues_found=validation_result.issues_found,
            recommendations=validation_result.recommendations,
            consensus_scores=validation_result.consensus_scores,
            execution_time=validation_result.execution_time,
            session_id=request.session_id,
        )
        
    except Exception as e:
        logger.error("Validation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# Legacy validation endpoint for backward compatibility
@app.post("/precision/validate/legacy", response_model=Dict[str, Any])
async def validate_response_legacy(request: ValidationRequest):
    """
    Legacy cross-agent validation endpoint.
    
    Maintained for backward compatibility with existing clients.
    """
    if swarm is None:
        raise HTTPException(status_code=503, detail="Agents not initialized")
    
    validation_results = {}
    
    # Validate with each requested agent
    for validator_name in request.validation_agents:
        if validator_name not in agents:
            continue
            
        validator_agent = agents[validator_name]
        
        # Create validation prompt
        validation_prompt = f"""
        Please review and validate the following response for accuracy, completeness, and correctness:

        Primary Agent: {request.primary_agent}
        Response to validate: {request.primary_response}

        Provide a validation score from 0.0 to 1.0 and explain your reasoning.
        Focus on factual accuracy, logical consistency, and completeness.
        """
        
        try:
            # Get validation from agent
            validation_response = swarm.run(
                agent=validator_agent,
                messages=[{"role": "user", "content": validation_prompt}],
                context_variables={},
            )
            
            # Extract validation score (simplified)
            validation_text = validation_response.messages[-1].get("content", "")
            
            # Parse score (simplified - would need more robust parsing)
            score = 0.7  # Default score
            if "0." in validation_text or "1.0" in validation_text:
                try:
                    import re
                    scores = re.findall(r'\b[01]\.\d+\b', validation_text)
                    if scores:
                        score = float(scores[0])
                except:
                    pass
            
            validation_results[validator_name] = {
                "score": score,
                "feedback": validation_text,
                "agent_model": validator_agent.model,
            }
            
        except Exception as e:
            validation_results[validator_name] = {
                "score": 0.0,
                "feedback": f"Validation failed: {str(e)}",
                "error": True,
            }
    
    # Calculate consensus score
    scores = [result["score"] for result in validation_results.values() if not result.get("error")]
    consensus_score = sum(scores) / len(scores) if scores else 0.0
    
    # Determine recommended action
    if consensus_score >= 0.8:
        recommended_action = "accept"
    elif consensus_score >= 0.6:
        recommended_action = "review"
    else:
        recommended_action = "reject"
        
    return {
        "primary_response": request.primary_response,
        "validation_results": validation_results,
        "consensus_score": consensus_score,
        "validation_summary": f"Consensus score: {consensus_score:.2f} from {len(scores)} validators",
        "recommended_action": recommended_action,
        "session_id": request.session_id,
    }


@app.get("/precision/validation-summary")
async def get_validation_summary():
    """
    Get summary of all cross-agent validation activities.
    
    Returns statistics about validation performance and usage.
    """
    if supervisor_factory is None:
        raise HTTPException(status_code=503, detail="Supervisor factory not initialized")
    
    try:
        summary = supervisor_factory.get_validation_summary()
        return summary
    except Exception as e:
        logger.error("Failed to get validation summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get validation summary: {str(e)}")


@app.get("/precision/trace-summary")
async def get_trace_summary():
    """
    Get precision enhancement trace summary.
    
    Returns detailed logging information about precision operations.
    """
    if supervisor_factory is None:
        raise HTTPException(status_code=503, detail="Supervisor factory not initialized")
    
    try:
        trace_summary = supervisor_factory.get_trace_summary()
        return trace_summary
    except Exception as e:
        logger.error("Failed to get trace summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get trace summary: {str(e)}")


@app.get("/precision/error-analytics")
async def get_error_analytics():
    """
    Get comprehensive error analytics and recovery statistics.
    
    Returns information about error patterns, recovery success rates,
    and recommendations for system optimization.
    """
    if error_recovery_manager is None:
        raise HTTPException(status_code=503, detail="Error recovery manager not initialized")
    
    try:
        analytics = error_recovery_manager.get_error_analytics()
        return {
            "error_analytics": analytics,
            "system_health": {
                "total_errors": analytics.get("total_errors", 0),
                "recovery_success_rate": analytics.get("recovery_success_rate", 0),
                "recent_error_trend": "stable" if analytics.get("recent_errors_count", 0) < 5 else "elevated",
                "most_problematic_patterns": analytics.get("most_common_patterns", [])[:3],
            },
            "recommendations": _generate_error_recommendations(analytics),
        }
    except Exception as e:
        logger.error("Failed to get error analytics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get error analytics: {str(e)}")


def _generate_error_recommendations(analytics: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on error analytics."""
    recommendations = []
    
    if analytics.get("no_errors"):
        return ["System operating normally - no errors detected"]
    
    success_rate = analytics.get("recovery_success_rate", 0)
    if success_rate < 0.7:
        recommendations.append("Consider increasing timeout values or improving error handling")
    
    recent_errors = analytics.get("recent_errors_count", 0)
    if recent_errors > 10:
        recommendations.append("High recent error rate detected - investigate system resources")
    
    common_patterns = analytics.get("most_common_patterns", [])
    if "timeout_error" in common_patterns:
        recommendations.append("Frequent timeouts detected - consider increasing consensus timeout")
    if "consensus_failure" in common_patterns:
        recommendations.append("Consensus issues detected - review agent availability and voting configuration")
    if "validation_error" in common_patterns:
        recommendations.append("Validation issues detected - review cross-agent validation settings")
    
    if not recommendations:
        recommendations.append("System performance within normal parameters")
    
    return recommendations


def main():
    """Main entry point for the FastAPI application."""
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "multi_agent.server:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
