"""
Supervisor Agent - Routes requests to specialized agents with precision enhancements.

The supervisor analyzes incoming requests and delegates to the appropriate
specialized agent using multi-agent consensus voting for improved precision.

Enhanced features:
- Multi-agent consensus voting for routing decisions
- Graceful degradation when consensus cannot be reached
- Structured trace logging for decision analysis
- Error pattern classification and handling
- Cross-agent validation for response quality assurance
"""

import asyncio
from typing import Callable, Dict, Optional, List
from ..core import Agent, Result, Response
from ..precision import ConsensusVoter, VotingConfig, PrecisionTracer, ErrorPattern
from ..cross_validation import CrossAgentValidator, ValidationLevel, ValidationResult

SUPERVISOR_INSTRUCTIONS = """You are a Precision-Enhanced Supervisor Agent coordinating a team of specialized AI agents.

Your role is to:
1. Analyze incoming user requests with high precision
2. Use multi-agent consensus voting to determine the best specialized agent
3. Route requests based on voting results with confidence tracking
4. Synthesize responses when multiple agents are needed
5. Handle graceful degradation when consensus cannot be reached

Available specialized agents:
- **RAG Agent**: For questions requiring knowledge retrieval, document search, or factual information
- **Coding Agent**: For code generation, debugging, code review, and software development tasks
- **Image Understanding Agent**: For image analysis, visual questions, and multimodal tasks

Enhanced routing process:
- Multiple voting rounds with different analytical perspectives
- Consensus thresholds for high-confidence routing
- Fallback strategies for timeout or consensus failure
- Structured trace logging for post-hoc analysis

When making routing decisions:
- Be decisive and analytical in your assessment
- Consider task complexity and required precision
- Use confidence scores to guide fallback strategies
- Document decision rationale for trace analysis

You have access to the following tools to transfer control to specialized agents:
- transfer_to_rag_agent: For knowledge and retrieval tasks
- transfer_to_coding_agent: For programming and development tasks  
- transfer_to_image_agent: For visual and multimodal tasks
- transfer_with_consensus: For precision-enhanced routing with voting

If consensus voting fails or times out, provide clear reasoning and use the most appropriate fallback strategy."""


class SupervisorAgent:
    """Factory for creating precision-enhanced supervisor agents with voting capabilities."""
    
    def __init__(
        self,
        model: str = "gpt-oss-120b",
        rag_agent: Optional[Agent] = None,
        coding_agent: Optional[Agent] = None,
        image_agent: Optional[Agent] = None,
        enable_consensus_voting: bool = True,
        voting_config: Optional[VotingConfig] = None,
        enable_cross_validation: bool = True,
    ):
        self.model = model
        self.rag_agent = rag_agent
        self.coding_agent = coding_agent
        self.image_agent = image_agent
        self.enable_consensus_voting = enable_consensus_voting
        self.enable_cross_validation = enable_cross_validation
        self.voting_config = voting_config or VotingConfig()
        self.tracer = PrecisionTracer()
        
        # Initialize consensus voter if enabled
        if self.enable_consensus_voting:
            self.voter = ConsensusVoter(self.voting_config, self.tracer)
        else:
            self.voter = None
            
        # Initialize cross-agent validator if enabled
        if self.enable_cross_validation:
            self.validator = CrossAgentValidator(self.voting_config, self.tracer)
        else:
            self.validator = None
        
    def _create_transfer_functions(self) -> list:
        """Create transfer functions for agent handoffs with consensus voting."""
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
        
        # Add precision-enhanced consensus transfer function
        if self.enable_consensus_voting and self.voter:
            def transfer_with_consensus(
                message: str,
                context_variables: Optional[Dict] = None,
            ) -> Result:
                """
                Use multi-agent consensus voting to determine the best agent for this request.
                
                This function employs the neuro-san inspired voting mechanism to achieve
                higher precision in routing decisions through multiple analytical perspectives.
                """
                # This is a placeholder - actual implementation will be handled
                # by the swarm's consensus voting mechanism
                self.tracer.log_trace(
                    operation="consensus_transfer_requested",
                    input_data={"message": message, "context_variables": context_variables}
                )
                
                # For now, return supervisor to trigger consensus voting in the swarm layer
                return Result(
                    value="Consensus voting requested - will be handled by precision-enhanced swarm",
                    context_variables={
                        "_consensus_requested": True,
                        "_original_message": message,
                        **(context_variables or {})
                    }
                )
            
            functions.append(transfer_with_consensus)
            
        return functions
    
    def create(self) -> Agent:
        """Create the precision-enhanced supervisor agent with routing functions."""
        agent = Agent(
            name="Supervisor",
            model=self.model,
            instructions=SUPERVISOR_INSTRUCTIONS,
            functions=self._create_transfer_functions(),
        )
        
        # Add precision enhancement metadata
        agent._precision_config = {
            "consensus_voting_enabled": self.enable_consensus_voting,
            "voting_config": self.voting_config.__dict__,
            "available_agents": {
                "rag": self.rag_agent is not None,
                "coding": self.coding_agent is not None,
                "image": self.image_agent is not None,
            }
        }
        
        return agent
    
    def get_available_agents(self) -> Dict[str, Agent]:
        """Get dictionary of all available agents for consensus voting."""
        agents = {}
        
        if self.rag_agent:
            agents["rag"] = self.rag_agent
        if self.coding_agent:
            agents["coding"] = self.coding_agent
        if self.image_agent:
            agents["image"] = self.image_agent
            
        return agents
    
    def get_available_agents_list(self) -> List[Agent]:
        """Get list of available agents for validation."""
        agents = []
        if self.rag_agent:
            agents.append(self.rag_agent)
        if self.coding_agent:
            agents.append(self.coding_agent)
        if self.image_agent:
            agents.append(self.image_agent)
        return agents
    
    async def validate_response(
        self,
        response: Response,
        validation_level: ValidationLevel = ValidationLevel.SEMANTIC,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """
        Perform cross-agent validation of a response using available agents.
        
        Args:
            response: Response to validate
            validation_level: Level of validation to perform
            context: Additional context for validation
            
        Returns:
            ValidationResult with detailed assessment
        """
        if not self.validator:
            # Create basic validation result when cross-validation is disabled
            return ValidationResult(
                passed=True,
                confidence=0.8,
                validation_level=ValidationLevel.BASIC,
                checks_performed=["cross_validation_disabled"],
                issues_found=[],
                recommendations=["Cross-validation is disabled"],
            )
        
        validation_agents = self.get_available_agents_list()
        
        self.tracer.log_trace(
            operation="supervisor_validation_start",
            input_data={
                "validation_level": validation_level.value,
                "available_validators": len(validation_agents),
                "context_keys": list((context or {}).keys()),
            }
        )
        
        try:
            result = await self.validator.validate_response(
                primary_response=response,
                validation_agents=validation_agents,
                validation_level=validation_level,
                context=context,
                timeout=self.voting_config.consensus_timeout,
            )
            
            self.tracer.log_trace(
                operation="supervisor_validation_complete",
                input_data={
                    "passed": result.passed,
                    "confidence": result.confidence,
                    "issues_found": len(result.issues_found),
                }
            )
            
            return result
            
        except Exception as e:
            self.tracer.log_error(
                operation="supervisor_validation_failed",
                error=str(e),
                error_pattern=ErrorPattern.VALIDATION_ERROR
            )
            
            # Return error validation result
            return ValidationResult(
                passed=False,
                confidence=0.0,
                validation_level=validation_level,
                checks_performed=["error_handling"],
                issues_found=[f"Validation error: {str(e)}"],
                recommendations=["Retry validation with different parameters"],
            )
    
    def get_validation_summary(self) -> Dict:
        """Get cross-agent validation summary."""
        if self.validator:
            return self.validator.get_validation_summary()
        return {"validation_disabled": True}
    
    def get_trace_summary(self) -> Dict:
        """Get precision enhancement trace summary."""
        return self.tracer.get_trace_summary()


def create_supervisor_agent(
    model: str = "gpt-oss-120b",
    rag_agent: Optional[Agent] = None,
    coding_agent: Optional[Agent] = None,
    image_agent: Optional[Agent] = None,
    enable_consensus_voting: bool = True,
    voting_config: Optional[VotingConfig] = None,
    enable_cross_validation: bool = True,
) -> Agent:
    """
    Create a precision-enhanced supervisor agent with routing to specialized agents.
    
    Args:
        model: Model to use for the supervisor
        rag_agent: RAG agent for knowledge retrieval
        coding_agent: Coding agent for development tasks
        image_agent: Image agent for visual tasks
        enable_consensus_voting: Enable multi-agent consensus voting for precision
        voting_config: Configuration for voting mechanisms
        enable_cross_validation: Enable cross-agent validation for response quality
        
    Returns:
        Supervisor agent with precision enhancements
    """
    factory = SupervisorAgent(
        model=model,
        rag_agent=rag_agent,
        coding_agent=coding_agent,
        image_agent=image_agent,
        enable_consensus_voting=enable_consensus_voting,
        voting_config=voting_config,
        enable_cross_validation=enable_cross_validation,
    )
    return factory.create()
        
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
