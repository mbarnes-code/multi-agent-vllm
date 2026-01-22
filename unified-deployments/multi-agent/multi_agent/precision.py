"""
Neuro-SAN Precision Enhancement Module

Implements voting mechanisms, consensus building, and error pattern classification
adapted from the neuro-san-benchmarking research for multi-agent systems.

Key features:
- Multi-agent voting with configurable thresholds
- Graceful degradation when consensus cannot be reached
- Structured trace logging for post-hoc analysis
- Error pattern classification and handling
- Performance/precision balance configuration
"""

import asyncio
import json
import logging
import os
import time
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import structlog

from .core import Agent, Response, Result

logger = structlog.get_logger()


class ErrorPattern(Enum):
    """Comprehensive error pattern classification adapted from neuro-san research."""
    
    # Core neuro-san error patterns
    MALFORMED_FINAL = "malformed_final"  # Parsing failures in final response
    NON_INDEPENDENT_SUBPROBLEMS = "non_independent_subproblems"  # Logical dependency violations
    AMBIGUOUS_COMPOSITION_OP = "ambiguous_composition_op"  # Unclear combination instructions
    ATOMIC_MISCALC = "atomic_miscalc"  # Basic calculation/reasoning errors
    COMPOSED_MISCALC = "composed_miscalc"  # Sub-problem combination errors
    
    # System-level error patterns
    TIMEOUT_ERROR = "timeout_error"  # Timeout during execution
    CONSENSUS_FAILURE = "consensus_failure"  # Failed to reach consensus
    AGENT_UNAVAILABLE = "agent_unavailable"  # Agent not responding
    VALIDATION_ERROR = "validation_error"  # Cross-agent validation failures
    
    # Performance-related patterns
    LOW_CONFIDENCE = "low_confidence"  # Response confidence below threshold
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # Memory/CPU limits reached
    NETWORK_ERROR = "network_error"  # Network connectivity issues
    
    # Task decomposition patterns
    DECOMPOSITION_DEPTH_EXCEEDED = "decomposition_depth_exceeded"  # Too many recursive levels
    TASK_COMPLEXITY_MISMATCH = "task_complexity_mismatch"  # Complexity assessment error
    DEPENDENCY_CYCLE = "dependency_cycle"  # Circular task dependencies
    
    # Agent coordination patterns
    COORDINATION_FAILURE = "coordination_failure"  # Multi-agent coordination breakdown
    CONTEXT_LOSS = "context_loss"  # Information lost between agent transfers
    INCONSISTENT_STATE = "inconsistent_state"  # Agent state inconsistencies
    
    # Data quality patterns
    INSUFFICIENT_CONTEXT = "insufficient_context"  # Missing required context
    CORRUPTED_INPUT = "corrupted_input"  # Malformed or corrupted input data
    SCHEMA_VIOLATION = "schema_violation"  # Data doesn't match expected schema
    
    @classmethod
    def classify_error(cls, error_text: str, operation_context: str = "") -> 'ErrorPattern':
        """
        Automatically classify an error based on error message and context.
        
        Args:
            error_text: The error message or description
            operation_context: Context about the operation that failed
            
        Returns:
            Most appropriate ErrorPattern
        """
        error_lower = error_text.lower()
        context_lower = operation_context.lower()
        
        # Timeout patterns
        if any(keyword in error_lower for keyword in ["timeout", "timed out", "deadline"]):
            return cls.TIMEOUT_ERROR
        
        # Network patterns
        if any(keyword in error_lower for keyword in ["network", "connection", "unreachable", "dns"]):
            return cls.NETWORK_ERROR
        
        # Consensus patterns
        if any(keyword in context_lower for keyword in ["consensus", "voting", "agreement"]):
            return cls.CONSENSUS_FAILURE
        
        # Validation patterns
        if any(keyword in context_lower for keyword in ["validation", "validate", "cross-agent"]):
            return cls.VALIDATION_ERROR
        
        # Parsing patterns
        if any(keyword in error_lower for keyword in ["parse", "malformed", "invalid format", "json", "syntax"]):
            return cls.MALFORMED_FINAL
        
        # Agent availability patterns
        if any(keyword in error_lower for keyword in ["unavailable", "not found", "missing agent", "offline"]):
            return cls.AGENT_UNAVAILABLE
        
        # Resource patterns
        if any(keyword in error_lower for keyword in ["memory", "cpu", "resource", "limit exceeded"]):
            return cls.RESOURCE_EXHAUSTION
        
        # Decomposition patterns
        if any(keyword in context_lower for keyword in ["decomposition", "recursive", "depth"]):
            return cls.DECOMPOSITION_DEPTH_EXCEEDED
        
        # Context patterns
        if any(keyword in error_lower for keyword in ["context", "missing", "insufficient"]):
            return cls.INSUFFICIENT_CONTEXT
        
        # Confidence patterns
        if any(keyword in error_lower for keyword in ["confidence", "uncertain", "low quality"]):
            return cls.LOW_CONFIDENCE
        
        # Default to atomic miscalculation for unclassified errors
        return cls.ATOMIC_MISCALC
    
    def get_recovery_strategy(self) -> Dict[str, Any]:
        """
        Get recommended recovery strategy for this error pattern.
        
        Returns:
            Dictionary containing recovery actions and parameters
        """
        recovery_strategies = {
            self.MALFORMED_FINAL: {
                "action": "retry_with_structured_prompt",
                "max_retries": 2,
                "use_schema_validation": True,
            },
            self.NON_INDEPENDENT_SUBPROBLEMS: {
                "action": "redecompose_task",
                "dependency_analysis": True,
                "max_depth_reduction": 1,
            },
            self.TIMEOUT_ERROR: {
                "action": "reduce_complexity_and_retry",
                "timeout_multiplier": 1.5,
                "parallel_execution": True,
            },
            self.CONSENSUS_FAILURE: {
                "action": "fallback_to_best_confidence",
                "require_minimum_votes": False,
                "confidence_threshold": 0.4,
            },
            self.AGENT_UNAVAILABLE: {
                "action": "route_to_alternative_agent",
                "check_agent_health": True,
                "fallback_agents": ["supervisor"],
            },
            self.VALIDATION_ERROR: {
                "action": "skip_validation_and_proceed",
                "log_validation_skip": True,
                "reduce_validation_level": True,
            },
            self.LOW_CONFIDENCE: {
                "action": "request_additional_validation",
                "increase_validator_count": True,
                "use_consensus_validation": True,
            },
            self.RESOURCE_EXHAUSTION: {
                "action": "reduce_task_complexity",
                "chunk_processing": True,
                "memory_optimization": True,
            },
            self.DECOMPOSITION_DEPTH_EXCEEDED: {
                "action": "reduce_decomposition_depth",
                "max_depth": 3,
                "merge_similar_subtasks": True,
            },
            self.INSUFFICIENT_CONTEXT: {
                "action": "request_additional_context",
                "context_expansion": True,
                "use_rag_enhancement": True,
            },
        }
        
        return recovery_strategies.get(self, {
            "action": "generic_retry",
            "max_retries": 1,
            "log_for_analysis": True,
        })


class ErrorRecoveryManager:
    """Manages error pattern classification and recovery strategies."""
    
    def __init__(self, tracer: Optional[PrecisionTracer] = None):
        self.tracer = tracer or PrecisionTracer()
        self.recovery_attempts: Dict[str, int] = {}
        self.error_history: List[Tuple[ErrorPattern, str, float]] = []
    
    def handle_error(
        self,
        error: Exception,
        operation_context: str,
        operation_id: str,
    ) -> Dict[str, Any]:
        """
        Handle an error by classifying it and providing recovery strategy.
        
        Args:
            error: The exception that occurred
            operation_context: Context about the operation
            operation_id: Unique identifier for this operation
            
        Returns:
            Recovery strategy dictionary
        """
        # Classify the error pattern
        error_pattern = ErrorPattern.classify_error(str(error), operation_context)
        
        # Log the error
        self.tracer.log_error(
            operation=operation_context,
            error=str(error),
            error_pattern=error_pattern,
            metadata={
                "operation_id": operation_id,
                "error_type": type(error).__name__,
            }
        )
        
        # Track recovery attempts
        recovery_key = f"{operation_id}_{error_pattern.value}"
        self.recovery_attempts[recovery_key] = self.recovery_attempts.get(recovery_key, 0) + 1
        
        # Record error history
        self.error_history.append((error_pattern, operation_context, time.time()))
        
        # Get recovery strategy
        recovery_strategy = error_pattern.get_recovery_strategy()
        recovery_strategy["error_pattern"] = error_pattern.value
        recovery_strategy["operation_id"] = operation_id
        recovery_strategy["attempt_count"] = self.recovery_attempts[recovery_key]
        
        # Check if we've exceeded max retry attempts
        max_retries = recovery_strategy.get("max_retries", 3)
        if self.recovery_attempts[recovery_key] > max_retries:
            recovery_strategy = {
                "action": "escalate_to_human",
                "error_pattern": error_pattern.value,
                "total_attempts": self.recovery_attempts[recovery_key],
                "requires_intervention": True,
            }
        
        return recovery_strategy
    
    def get_error_analytics(self) -> Dict[str, Any]:
        """Get analytics about error patterns and recovery effectiveness."""
        if not self.error_history:
            return {"no_errors": True}
        
        # Error pattern frequency
        pattern_counts = Counter([error[0] for error in self.error_history])
        
        # Recovery success rate (simplified metric)
        total_recoveries = sum(self.recovery_attempts.values())
        successful_recoveries = len([key for key, count in self.recovery_attempts.items() if count <= 3])
        success_rate = successful_recoveries / len(self.recovery_attempts) if self.recovery_attempts else 0
        
        # Recent error trends (last hour)
        recent_errors = [error for error in self.error_history if time.time() - error[2] < 3600]
        
        return {
            "total_errors": len(self.error_history),
            "unique_operations_affected": len(self.recovery_attempts),
            "pattern_distribution": {pattern.value: count for pattern, count in pattern_counts.items()},
            "recovery_success_rate": success_rate,
            "recent_errors_count": len(recent_errors),
            "most_common_patterns": [pattern.value for pattern, count in pattern_counts.most_common(5)],
            "average_recovery_attempts": sum(self.recovery_attempts.values()) / len(self.recovery_attempts) if self.recovery_attempts else 0,
        }


@dataclass
class VotingConfig:
    """Configuration for voting mechanisms with 60% precision / 40% performance balance."""
    # Core voting parameters (from neuro-san defaults)
    winning_vote_count: int = 2  # Minimum votes needed for consensus
    candidate_count: int = 3  # Total voting attempts (2 * winning_vote_count - 1)
    max_voting_rounds: int = 3  # Maximum voting rounds before fallback
    
    # Performance/precision balance (60% precision / 40% performance)
    consensus_timeout_seconds: float = 20.0  # Timeout for consensus (balanced for performance)
    parallel_voting: bool = True  # Enable parallel execution for performance
    early_termination: bool = True  # Stop early when consensus reached
    confidence_threshold: float = 0.6  # Minimum confidence for single-agent decisions
    
    # Graceful degradation
    fallback_to_majority: bool = True  # Use majority vote if consensus fails
    fallback_to_best_confidence: bool = True  # Use highest confidence if majority fails
    allow_single_agent_fallback: bool = True  # Allow single agent response as last resort


@dataclass
class VotingResult:
    """Result from a voting operation."""
    consensus_reached: bool
    selected_response: Optional[str]
    selected_agent: Optional[Agent]
    vote_count: int
    confidence_score: float
    execution_time: float
    error_pattern: Optional[ErrorPattern]
    all_responses: List[Dict[str, Any]] = field(default_factory=list)
    trace_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEntry:
    """Structured trace entry for decision logging."""
    timestamp: float
    thread_id: int
    operation: str
    agent_name: Optional[str]
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    execution_time: float
    error_pattern: Optional[ErrorPattern] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PrecisionTracer:
    """Structured trace logging for multi-agent decision analysis."""
    
    def __init__(self, enable_logging: bool = True):
        self.enable_logging = enable_logging
        self.traces: List[TraceEntry] = []
        self.thread_id = threading.get_ident()
        self.session_start_time = time.time()
        
    def log_trace(
        self,
        operation: str,
        agent_name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
        error_pattern: Optional[ErrorPattern] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log a trace entry with structured data."""
        if not self.enable_logging:
            return
            
        entry = TraceEntry(
            timestamp=time.time(),
            thread_id=self.thread_id,
            operation=operation,
            agent_name=agent_name,
            input_data=input_data or {},
            output_data=output_data or {},
            execution_time=execution_time,
            error_pattern=error_pattern,
            metadata=metadata or {},
        )
        self.traces.append(entry)
        
        # Also log to structured logger if available
        try:
            import structlog
            logger = structlog.get_logger()
            logger.info(
                "precision_trace",
                operation=operation,
                agent_name=agent_name,
                execution_time=execution_time,
                error_pattern=error_pattern.value if error_pattern else None,
                thread_id=self.thread_id,
                metadata=metadata,
            )
        except ImportError:
            pass  # structlog not available
    
    def log_error(
        self,
        operation: str,
        error: str,
        error_pattern: ErrorPattern,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an error with associated pattern classification."""
        self.log_trace(
            operation=operation,
            agent_name=agent_name,
            input_data={"error": error},
            error_pattern=error_pattern,
            metadata={
                "error_severity": self._classify_error_severity(error_pattern),
                **(metadata or {})
            }
        )
    
    def _classify_error_severity(self, error_pattern: ErrorPattern) -> str:
        """Classify error severity based on pattern."""
        critical_patterns = {
            ErrorPattern.CONSENSUS_FAILURE,
            ErrorPattern.AGENT_UNAVAILABLE,
            ErrorPattern.VALIDATION_ERROR,
        }
        
        warning_patterns = {
            ErrorPattern.TIMEOUT_ERROR,
            ErrorPattern.LOW_CONFIDENCE,
            ErrorPattern.MALFORMED_FINAL,
        }
        
        if error_pattern in critical_patterns:
            return "critical"
        elif error_pattern in warning_patterns:
            return "warning"
        else:
            return "info"
        
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of all traces in this session."""
        total_time = time.time() - self.session_start_time
        error_counts = Counter([t.error_pattern for t in self.traces if t.error_pattern])
        operation_counts = Counter([t.operation for t in self.traces])
        
        # Calculate performance metrics
        execution_times = [t.execution_time for t in self.traces if t.execution_time > 0]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # Error analysis
        error_by_severity = {}
        for pattern, count in error_counts.items():
            severity = self._classify_error_severity(pattern)
            error_by_severity[severity] = error_by_severity.get(severity, 0) + count
        
        return {
            "session_info": {
                "duration": total_time,
                "thread_id": self.thread_id,
                "session_start": self.session_start_time,
            },
            "operation_summary": {
                "total_operations": len(self.traces),
                "operation_types": dict(operation_counts),
                "agents_used": list(set([t.agent_name for t in self.traces if t.agent_name])),
                "avg_execution_time": avg_execution_time,
            },
            "error_analysis": {
                "total_errors": sum(error_counts.values()),
                "error_patterns": {pattern.value: count for pattern, count in error_counts.items()},
                "error_by_severity": error_by_severity,
            },
            "performance_metrics": {
                "fastest_operation": min(execution_times) if execution_times else 0,
                "slowest_operation": max(execution_times) if execution_times else 0,
                "operation_percentiles": self._calculate_percentiles(execution_times) if execution_times else {},
            }
        }
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate percentile values for performance analysis."""
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        percentiles = {}
        for p in [50, 75, 90, 95, 99]:
            index = int((p / 100) * n)
            percentiles[f"p{p}"] = sorted_values[min(index, n - 1)]
        
        return percentiles
        
    def export_traces(self, format: str = "json") -> str:
        """Export traces for analysis."""
        if format == "json":
            return json.dumps([{
                "timestamp": t.timestamp,
                "thread_id": t.thread_id,
                "operation": t.operation,
                "agent_name": t.agent_name,
                "input_data": t.input_data,
                "output_data": t.output_data,
                "execution_time": t.execution_time,
                "error_pattern": t.error_pattern.value if t.error_pattern else None,
                "metadata": t.metadata,
            } for t in self.traces], indent=2)
        elif format == "csv":
            # Simple CSV export
            lines = ["timestamp,operation,agent_name,execution_time,error_pattern"]
            for t in self.traces:
                lines.append(f"{t.timestamp},{t.operation},{t.agent_name or ''},{t.execution_time},{t.error_pattern.value if t.error_pattern else ''}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_recent_traces(self, limit: int = 50) -> List[TraceEntry]:
        """Get the most recent trace entries."""
        return self.traces[-limit:] if self.traces else []
    
    def clear_traces(self):
        """Clear all trace entries (useful for memory management)."""
        self.traces.clear()
        self.session_start_time = time.time()
                "execution_time": t.execution_time,
                "error_pattern": t.error_pattern.value if t.error_pattern else None,
                "metadata": t.metadata,
            } for t in self.traces], indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")


class ConsensusVoter:
    """Multi-agent consensus voting system with precision enhancements."""
    
    def __init__(self, config: VotingConfig = None, tracer: PrecisionTracer = None):
        self.config = config or VotingConfig()
        self.tracer = tracer or PrecisionTracer()
        
    async def vote_on_routing(
        self,
        message: str,
        available_agents: Dict[str, Agent],
        context_variables: Dict[str, Any] = None,
        swarm = None,
    ) -> VotingResult:
        """
        Multi-agent consensus voting for routing decisions.
        
        This replaces simple supervisor routing with multi-agent consensus
        to improve precision in agent selection.
        """
        start_time = time.time()
        context_variables = context_variables or {}
        
        self.tracer.log_trace(
            operation="vote_on_routing_start",
            input_data={
                "message": message,
                "available_agents": list(available_agents.keys()),
                "config": self.config.__dict__,
            }
        )
        
        try:
            # Get multiple routing opinions
            routing_votes = await self._collect_routing_votes(
                message, available_agents, context_variables, swarm
            )
            
            # Analyze votes for consensus
            result = await self._analyze_routing_votes(routing_votes, available_agents)
            
            self.tracer.log_trace(
                operation="vote_on_routing_complete",
                output_data={
                    "consensus_reached": result.consensus_reached,
                    "selected_agent": result.selected_agent.name if result.selected_agent else None,
                    "vote_count": result.vote_count,
                    "confidence_score": result.confidence_score,
                },
                execution_time=time.time() - start_time,
            )
            
            return result
            
        except asyncio.TimeoutError:
            self.tracer.log_trace(
                operation="vote_on_routing_timeout",
                execution_time=time.time() - start_time,
                error_pattern=ErrorPattern.TIMEOUT_ERROR,
            )
            return await self._handle_routing_timeout(available_agents)
            
        except Exception as e:
            self.tracer.log_trace(
                operation="vote_on_routing_error",
                execution_time=time.time() - start_time,
                error_pattern=ErrorPattern.CONSENSUS_FAILURE,
                metadata={"error": str(e)},
            )
            return await self._handle_routing_failure(available_agents, str(e))
    
    async def _collect_routing_votes(
        self,
        message: str,
        available_agents: Dict[str, Agent],
        context_variables: Dict[str, Any],
        swarm,
    ) -> List[Dict[str, Any]]:
        """Collect routing opinions from multiple perspectives."""
        votes = []
        
        # Create voting prompts for different perspectives
        voting_prompts = self._generate_routing_prompts(message, available_agents)
        
        if self.config.parallel_voting:
            # Parallel voting for performance
            tasks = []
            for i, prompt in enumerate(voting_prompts[:self.config.candidate_count]):
                task = self._get_single_routing_vote(prompt, available_agents, context_variables, swarm, i)
                tasks.append(task)
                
            try:
                votes = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self.config.consensus_timeout_seconds
                )
                # Filter out exceptions
                votes = [v for v in votes if not isinstance(v, Exception)]
            except asyncio.TimeoutError:
                logger.warning("parallel_voting_timeout", timeout=self.config.consensus_timeout_seconds)
                raise
                
        else:
            # Sequential voting
            for i, prompt in enumerate(voting_prompts[:self.config.candidate_count]):
                try:
                    vote = await asyncio.wait_for(
                        self._get_single_routing_vote(prompt, available_agents, context_variables, swarm, i),
                        timeout=self.config.consensus_timeout_seconds / self.config.candidate_count
                    )
                    votes.append(vote)
                    
                    # Early termination if we have enough consensus
                    if self.config.early_termination and len(votes) >= self.config.winning_vote_count:
                        if self._check_early_consensus(votes):
                            break
                            
                except asyncio.TimeoutError:
                    logger.warning("sequential_vote_timeout", vote_index=i)
                    continue
                    
        return votes
    
    def _generate_routing_prompts(self, message: str, available_agents: Dict[str, Agent]) -> List[str]:
        """Generate different perspective prompts for routing votes."""
        agent_descriptions = []
        for name, agent in available_agents.items():
            # Extract capability info from agent instructions
            agent_descriptions.append(f"- {name}: {self._extract_agent_capabilities(agent)}")
        
        agents_text = "\\n".join(agent_descriptions)
        
        prompts = [
            # Perspective 1: Task analysis focus
            f"""Analyze this user request and determine which agent is best suited to handle it.
            
User request: {message}

Available agents:
{agents_text}

Consider the primary task type and required capabilities. Respond with only the agent name that best matches the request.""",

            # Perspective 2: Domain expertise focus  
            f"""From a domain expertise perspective, which agent has the most relevant knowledge for this request?
            
User request: {message}

Available agents:
{agents_text}

Focus on which agent's specialized knowledge domain best aligns with the user's needs. Respond with only the agent name.""",

            # Perspective 3: Efficiency focus
            f"""Which agent can handle this request most efficiently while maintaining quality?

User request: {message}

Available agents:
{agents_text}

Consider both response quality and processing efficiency. Respond with only the agent name that offers the best balance.""",
        ]
        
        return prompts
    
    def _extract_agent_capabilities(self, agent: Agent) -> str:
        """Extract a brief capability summary from agent instructions."""
        instructions = agent.instructions
        if callable(instructions):
            instructions = instructions({})
        
        # Extract key phrases that indicate capabilities
        if "RAG" in agent.name or "knowledge" in instructions.lower():
            return "Knowledge retrieval, document search, factual information"
        elif "Coding" in agent.name or "code" in instructions.lower():
            return "Code generation, debugging, software development"
        elif "Image" in agent.name or "visual" in instructions.lower():
            return "Image analysis, visual tasks, multimodal processing"
        elif "Supervisor" in agent.name:
            return "Task coordination, agent orchestration"
        else:
            return "General assistance and coordination"
    
    async def _get_single_routing_vote(
        self,
        prompt: str,
        available_agents: Dict[str, Agent],
        context_variables: Dict[str, Any],
        swarm,
        vote_index: int,
    ) -> Dict[str, Any]:
        """Get a single routing vote from the supervisor agent."""
        try:
            # Use a simplified agent for voting to avoid recursion
            voting_agent = Agent(
                name=f"Router-{vote_index}",
                model="gpt-oss-20b",  # Use faster model for voting
                instructions=prompt,
                functions=[],
            )
            
            messages = [{"role": "user", "content": prompt}]
            
            # Get response from swarm
            if swarm:
                response = await asyncio.to_thread(
                    swarm.run,
                    agent=voting_agent,
                    messages=messages,
                    context_variables=context_variables,
                )
            else:
                # Fallback if no swarm available
                response = Response(
                    messages=[{"role": "assistant", "content": "supervisor"}],
                    agent=voting_agent,
                    context_variables=context_variables,
                )
            
            # Parse the routing decision
            content = response.messages[-1].get("content", "").strip().lower()
            selected_agent = self._parse_agent_selection(content, available_agents)
            
            # Calculate confidence based on response clarity
            confidence = self._calculate_confidence(content, selected_agent)
            
            return {
                "vote_index": vote_index,
                "selected_agent": selected_agent,
                "confidence": confidence,
                "raw_response": content,
                "timestamp": time.time(),
            }
            
        except Exception as e:
            logger.error("single_vote_error", vote_index=vote_index, error=str(e))
            return {
                "vote_index": vote_index,
                "selected_agent": None,
                "confidence": 0.0,
                "raw_response": "",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    def _parse_agent_selection(self, content: str, available_agents: Dict[str, Agent]) -> Optional[str]:
        """Parse agent name from voting response."""
        content = content.lower().strip()
        
        # Direct name match
        for agent_name in available_agents.keys():
            if agent_name.lower() in content:
                return agent_name
        
        # Keyword matching
        if any(word in content for word in ["code", "coding", "program", "development"]):
            return "coding"
        elif any(word in content for word in ["knowledge", "rag", "search", "document"]):
            return "rag"
        elif any(word in content for word in ["image", "visual", "picture", "photo"]):
            return "image"
        elif any(word in content for word in ["supervisor", "coordinate", "general"]):
            return "supervisor"
            
        return None
    
    def _calculate_confidence(self, response: str, selected_agent: Optional[str]) -> float:
        """Calculate confidence score based on response clarity and length."""
        if not selected_agent:
            return 0.0
        
        base_confidence = 0.7  # Base confidence for valid selection
        
        # Boost confidence for clear, decisive responses
        if len(response.split()) <= 3:  # Short, decisive answer
            base_confidence += 0.2
        elif any(word in response for word in ["clearly", "definitely", "obviously", "best"]):
            base_confidence += 0.1
        
        # Reduce confidence for hedged responses
        if any(word in response for word in ["maybe", "might", "could", "uncertain"]):
            base_confidence -= 0.2
            
        return max(0.0, min(1.0, base_confidence))
    
    def _check_early_consensus(self, votes: List[Dict[str, Any]]) -> bool:
        """Check if we have early consensus in votes."""
        if len(votes) < self.config.winning_vote_count:
            return False
            
        valid_votes = [v for v in votes if v.get("selected_agent")]
        if len(valid_votes) < self.config.winning_vote_count:
            return False
            
        # Count votes for each agent
        vote_counts = Counter([v["selected_agent"] for v in valid_votes])
        most_common_count = vote_counts.most_common(1)[0][1] if vote_counts else 0
        
        return most_common_count >= self.config.winning_vote_count
    
    async def _analyze_routing_votes(
        self, votes: List[Dict[str, Any]], available_agents: Dict[str, Agent]
    ) -> VotingResult:
        """Analyze collected votes to determine consensus."""
        if not votes:
            return VotingResult(
                consensus_reached=False,
                selected_response=None,
                selected_agent=None,
                vote_count=0,
                confidence_score=0.0,
                execution_time=0.0,
                error_pattern=ErrorPattern.CONSENSUS_FAILURE,
                all_responses=votes,
            )
        
        # Filter valid votes
        valid_votes = [v for v in votes if v.get("selected_agent") and v.get("selected_agent") in available_agents]
        
        if not valid_votes:
            return await self._handle_no_valid_votes(votes, available_agents)
        
        # Count votes by agent
        vote_counts = Counter([v["selected_agent"] for v in valid_votes])
        confidence_by_agent = defaultdict(list)
        
        for vote in valid_votes:
            agent = vote["selected_agent"]
            confidence = vote.get("confidence", 0.0)
            confidence_by_agent[agent].append(confidence)
        
        # Check for consensus (winning vote count threshold)
        most_common = vote_counts.most_common()
        top_agent, top_count = most_common[0]
        
        if top_count >= self.config.winning_vote_count:
            # Consensus reached
            avg_confidence = sum(confidence_by_agent[top_agent]) / len(confidence_by_agent[top_agent])
            
            return VotingResult(
                consensus_reached=True,
                selected_response=f"Consensus routing to {top_agent}",
                selected_agent=available_agents[top_agent],
                vote_count=top_count,
                confidence_score=avg_confidence,
                execution_time=0.0,
                all_responses=votes,
                trace_data={"vote_distribution": dict(vote_counts)},
            )
        
        # No consensus - try fallback strategies
        return await self._handle_no_consensus(vote_counts, confidence_by_agent, available_agents, votes)
    
    async def _handle_no_consensus(
        self,
        vote_counts: Counter,
        confidence_by_agent: Dict[str, List[float]],
        available_agents: Dict[str, Agent],
        all_votes: List[Dict[str, Any]],
    ) -> VotingResult:
        """Handle cases where no consensus was reached."""
        
        if self.config.fallback_to_majority and vote_counts:
            # Use majority vote
            top_agent, top_count = vote_counts.most_common(1)[0]
            avg_confidence = sum(confidence_by_agent[top_agent]) / len(confidence_by_agent[top_agent])
            
            return VotingResult(
                consensus_reached=False,
                selected_response=f"Majority fallback to {top_agent}",
                selected_agent=available_agents[top_agent],
                vote_count=top_count,
                confidence_score=avg_confidence * 0.8,  # Reduced confidence for fallback
                execution_time=0.0,
                all_responses=all_votes,
                trace_data={"fallback_reason": "majority_vote", "vote_distribution": dict(vote_counts)},
            )
        
        if self.config.fallback_to_best_confidence:
            # Use agent with highest average confidence
            best_agent = None
            best_confidence = 0.0
            
            for agent, confidences in confidence_by_agent.items():
                avg_conf = sum(confidences) / len(confidences)
                if avg_conf > best_confidence:
                    best_confidence = avg_conf
                    best_agent = agent
            
            if best_agent and best_confidence >= self.config.confidence_threshold:
                return VotingResult(
                    consensus_reached=False,
                    selected_response=f"Confidence fallback to {best_agent}",
                    selected_agent=available_agents[best_agent],
                    vote_count=1,
                    confidence_score=best_confidence * 0.7,  # Further reduced for confidence fallback
                    execution_time=0.0,
                    all_responses=all_votes,
                    trace_data={"fallback_reason": "best_confidence", "confidence_scores": dict(confidence_by_agent)},
                )
        
        # Final fallback to supervisor
        if self.config.allow_single_agent_fallback and "supervisor" in available_agents:
            return VotingResult(
                consensus_reached=False,
                selected_response="Fallback to supervisor for manual routing",
                selected_agent=available_agents["supervisor"],
                vote_count=0,
                confidence_score=0.5,
                execution_time=0.0,
                error_pattern=ErrorPattern.CONSENSUS_FAILURE,
                all_responses=all_votes,
                trace_data={"fallback_reason": "supervisor_fallback"},
            )
        
        # Complete failure
        return VotingResult(
            consensus_reached=False,
            selected_response=None,
            selected_agent=None,
            vote_count=0,
            confidence_score=0.0,
            execution_time=0.0,
            error_pattern=ErrorPattern.CONSENSUS_FAILURE,
            all_responses=all_votes,
            trace_data={"fallback_reason": "complete_failure"},
        )
    
    async def _handle_routing_timeout(self, available_agents: Dict[str, Agent]) -> VotingResult:
        """Handle timeout during routing consensus."""
        # Graceful degradation to supervisor
        if "supervisor" in available_agents:
            return VotingResult(
                consensus_reached=False,
                selected_response="Timeout fallback to supervisor",
                selected_agent=available_agents["supervisor"],
                vote_count=0,
                confidence_score=0.3,
                execution_time=self.config.consensus_timeout_seconds,
                error_pattern=ErrorPattern.TIMEOUT_ERROR,
                trace_data={"fallback_reason": "timeout"},
            )
        
        return VotingResult(
            consensus_reached=False,
            selected_response=None,
            selected_agent=None,
            vote_count=0,
            confidence_score=0.0,
            execution_time=self.config.consensus_timeout_seconds,
            error_pattern=ErrorPattern.TIMEOUT_ERROR,
            trace_data={"fallback_reason": "timeout_no_supervisor"},
        )
    
    async def _handle_routing_failure(self, available_agents: Dict[str, Agent], error: str) -> VotingResult:
        """Handle general failure during routing."""
        logger.error("routing_consensus_failure", error=error)
        
        # Try to fallback to any available agent
        if available_agents:
            fallback_agent = next(iter(available_agents.values()))
            return VotingResult(
                consensus_reached=False,
                selected_response=f"Error fallback to {fallback_agent.name}",
                selected_agent=fallback_agent,
                vote_count=0,
                confidence_score=0.2,
                execution_time=0.0,
                error_pattern=ErrorPattern.CONSENSUS_FAILURE,
                trace_data={"fallback_reason": "error_fallback", "error": error},
            )
        
        return VotingResult(
            consensus_reached=False,
            selected_response=None,
            selected_agent=None,
            vote_count=0,
            confidence_score=0.0,
            execution_time=0.0,
            error_pattern=ErrorPattern.CONSENSUS_FAILURE,
            trace_data={"fallback_reason": "complete_failure", "error": error},
        )
    
    async def _handle_no_valid_votes(self, votes: List[Dict[str, Any]], available_agents: Dict[str, Agent]) -> VotingResult:
        """Handle case where no votes were valid."""
        return VotingResult(
            consensus_reached=False,
            selected_response="No valid votes - fallback to supervisor",
            selected_agent=available_agents.get("supervisor"),
            vote_count=0,
            confidence_score=0.1,
            execution_time=0.0,
            error_pattern=ErrorPattern.MALFORMED_FINAL,
            all_responses=votes,
            trace_data={"fallback_reason": "no_valid_votes"},
        )


def create_precision_enhanced_swarm():
    """Factory function to create a precision-enhanced swarm with neuro-san capabilities."""
    from .core import Swarm
    
    class PrecisionEnhancedSwarm(Swarm):
        """Swarm with integrated neuro-san precision enhancements."""
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.voting_config = VotingConfig()
            self.tracer = PrecisionTracer()
            self.voter = ConsensusVoter(self.voting_config, self.tracer)
            
        async def run_with_consensus(
            self,
            agent: Agent,
            messages: List[Dict[str, Any]],
            context_variables: Dict[str, Any] = None,
            available_agents: Dict[str, Agent] = None,
            enable_voting: bool = True,
        ) -> Response:
            """Run swarm with precision-enhanced routing via consensus voting."""
            if enable_voting and available_agents and len(available_agents) > 1:
                # Get consensus on routing
                user_message = messages[-1].get("content", "") if messages else ""
                voting_result = await self.voter.vote_on_routing(
                    message=user_message,
                    available_agents=available_agents,
                    context_variables=context_variables,
                    swarm=self,
                )
                
                if voting_result.selected_agent:
                    # Use consensus-selected agent
                    selected_agent = voting_result.selected_agent
                    
                    # Add voting trace to context
                    context_variables = context_variables or {}
                    context_variables["_voting_result"] = {
                        "consensus_reached": voting_result.consensus_reached,
                        "confidence_score": voting_result.confidence_score,
                        "vote_count": voting_result.vote_count,
                        "error_pattern": voting_result.error_pattern.value if voting_result.error_pattern else None,
                    }
                    
                    # Execute with selected agent
                    response = self.run(
                        agent=selected_agent,
                        messages=messages,
                        context_variables=context_variables,
                    )
                    
                    # Enhance response with voting metadata
                    if hasattr(response, 'context_variables'):
                        response.context_variables.update(context_variables)
                    
                    return response
            
            # Fallback to normal execution
            return self.run(
                agent=agent,
                messages=messages,
                context_variables=context_variables,
            )
        
        def get_session_trace(self) -> Dict[str, Any]:
            """Get complete session trace for analysis."""
            return self.tracer.get_trace_summary()
        
        def export_traces(self, format: str = "json") -> str:
            """Export session traces."""
            return self.tracer.export_traces(format)
    
    return PrecisionEnhancedSwarm