"""
Cross-Agent Validation for Multi-Agent Precision Enhancement.

Implements validation mechanisms between different agents to ensure consistency,
accuracy, and quality of results across the multi-agent system.

Based on neuro-san precision principles:
- Cross-agent consensus validation
- Structured result comparison
- Error pattern detection
- Quality scoring across agent outputs
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from ..core import Agent, Response
from ..precision import PrecisionTracer, ErrorPattern, VotingConfig

class ValidationLevel(Enum):
    """Validation levels for cross-agent checks."""
    BASIC = "basic"           # Simple format and content checks
    SEMANTIC = "semantic"     # Semantic consistency checks  
    CONSENSUS = "consensus"   # Multi-agent consensus validation
    COMPREHENSIVE = "comprehensive"  # Full validation suite


@dataclass
class ValidationResult:
    """Result of cross-agent validation."""
    passed: bool
    confidence: float
    validation_level: ValidationLevel
    checks_performed: List[str]
    issues_found: List[str]
    recommendations: List[str]
    consensus_scores: Optional[Dict[str, float]] = None
    execution_time: Optional[float] = None


@dataclass
class CrossValidationTask:
    """Task for cross-agent validation."""
    primary_response: Response
    validation_agents: List[Agent]
    validation_level: ValidationLevel
    context: Dict[str, Any]
    timeout: float = 20.0


class CrossAgentValidator:
    """Cross-agent validation with precision enhancement patterns."""
    
    def __init__(
        self,
        voting_config: Optional[VotingConfig] = None,
        tracer: Optional[PrecisionTracer] = None,
    ):
        self.voting_config = voting_config or VotingConfig()
        self.tracer = tracer or PrecisionTracer()
        self.validation_history: List[ValidationResult] = []
    
    async def validate_response(
        self,
        primary_response: Response,
        validation_agents: List[Agent],
        validation_level: ValidationLevel = ValidationLevel.SEMANTIC,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> ValidationResult:
        """
        Perform cross-agent validation of a response.
        
        Args:
            primary_response: Response to validate
            validation_agents: List of agents to use for validation
            validation_level: Level of validation to perform
            context: Additional context for validation
            timeout: Timeout for validation process
            
        Returns:
            ValidationResult with detailed assessment
        """
        start_time = time.time()
        context = context or {}
        
        task = CrossValidationTask(
            primary_response=primary_response,
            validation_agents=validation_agents,
            validation_level=validation_level,
            context=context,
            timeout=timeout,
        )
        
        self.tracer.log_trace(
            operation="cross_validation_started",
            input_data={
                "validation_level": validation_level.value,
                "num_validators": len(validation_agents),
                "response_length": len(str(primary_response.content)) if primary_response.content else 0,
            }
        )
        
        try:
            if validation_level == ValidationLevel.BASIC:
                result = await self._basic_validation(task)
            elif validation_level == ValidationLevel.SEMANTIC:
                result = await self._semantic_validation(task)
            elif validation_level == ValidationLevel.CONSENSUS:
                result = await self._consensus_validation(task)
            elif validation_level == ValidationLevel.COMPREHENSIVE:
                result = await self._comprehensive_validation(task)
            else:
                raise ValueError(f"Unknown validation level: {validation_level}")
            
            result.execution_time = time.time() - start_time
            self.validation_history.append(result)
            
            self.tracer.log_trace(
                operation="cross_validation_completed",
                input_data={
                    "passed": result.passed,
                    "confidence": result.confidence,
                    "execution_time": result.execution_time,
                    "issues_count": len(result.issues_found),
                }
            )
            
            return result
            
        except Exception as e:
            error_result = ValidationResult(
                passed=False,
                confidence=0.0,
                validation_level=validation_level,
                checks_performed=["error_handling"],
                issues_found=[f"Validation error: {str(e)}"],
                recommendations=["Retry validation with different parameters"],
                execution_time=time.time() - start_time,
            )
            
            self.tracer.log_error(
                operation="cross_validation_failed",
                error=str(e),
                error_pattern=ErrorPattern.VALIDATION_ERROR
            )
            
            return error_result
    
    async def _basic_validation(self, task: CrossValidationTask) -> ValidationResult:
        """Perform basic validation checks."""
        checks_performed = []
        issues_found = []
        recommendations = []
        
        # Check 1: Response format validation
        checks_performed.append("response_format")
        if not task.primary_response or not task.primary_response.content:
            issues_found.append("Empty or missing response content")
        
        # Check 2: Content length validation
        checks_performed.append("content_length")
        content_length = len(str(task.primary_response.content)) if task.primary_response.content else 0
        if content_length < 10:
            issues_found.append("Response content appears too short")
        elif content_length > 50000:
            issues_found.append("Response content appears excessively long")
        
        # Check 3: Basic content quality
        checks_performed.append("basic_quality")
        content_str = str(task.primary_response.content).lower()
        
        quality_issues = []
        if "error" in content_str or "failed" in content_str:
            quality_issues.append("Contains error indicators")
        if content_str.count("todo") > 3:
            quality_issues.append("Multiple TODO items found")
        if not any(char.isalnum() for char in content_str):
            quality_issues.append("No alphanumeric content detected")
        
        if quality_issues:
            issues_found.extend(quality_issues)
            recommendations.append("Review content for completeness and quality")
        
        # Calculate confidence based on issues
        confidence = max(0.0, 1.0 - (len(issues_found) * 0.25))
        passed = confidence >= 0.5
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            validation_level=ValidationLevel.BASIC,
            checks_performed=checks_performed,
            issues_found=issues_found,
            recommendations=recommendations,
        )
    
    async def _semantic_validation(self, task: CrossValidationTask) -> ValidationResult:
        """Perform semantic validation with agent consultation."""
        checks_performed = []
        issues_found = []
        recommendations = []
        
        # First run basic validation
        basic_result = await self._basic_validation(task)
        checks_performed.extend(basic_result.checks_performed)
        issues_found.extend(basic_result.issues_found)
        recommendations.extend(basic_result.recommendations)
        
        # Semantic validation with first available agent
        if task.validation_agents:
            validation_agent = task.validation_agents[0]
            checks_performed.append("semantic_review")
            
            validation_prompt = f"""
Please review the following response for semantic correctness and quality:

ORIGINAL TASK/CONTEXT: {task.context.get('original_request', 'Not provided')}

RESPONSE TO VALIDATE:
{task.primary_response.content}

Assess the response for:
1. Relevance to the task
2. Semantic correctness
3. Completeness of answer
4. Quality and clarity

Respond with a JSON object containing:
- "semantic_issues": list of semantic problems found
- "relevance_score": float between 0.0-1.0
- "completeness_score": float between 0.0-1.0
- "clarity_score": float between 0.0-1.0
- "overall_assessment": brief summary
"""
            
            try:
                # This would be implemented in the actual agent execution
                # For now, simulate semantic validation
                semantic_scores = await self._simulate_semantic_validation(
                    task.primary_response, task.context
                )
                
                if semantic_scores["relevance_score"] < 0.6:
                    issues_found.append("Low relevance to original task")
                if semantic_scores["completeness_score"] < 0.6:
                    issues_found.append("Response appears incomplete")
                if semantic_scores["clarity_score"] < 0.6:
                    issues_found.append("Response lacks clarity")
                
                if semantic_scores["semantic_issues"]:
                    issues_found.extend(semantic_scores["semantic_issues"])
                
                # Calculate overall confidence
                semantic_confidence = (
                    semantic_scores["relevance_score"] * 0.4 +
                    semantic_scores["completeness_score"] * 0.3 +
                    semantic_scores["clarity_score"] * 0.3
                )
                
                confidence = min(basic_result.confidence, semantic_confidence)
                
            except Exception as e:
                issues_found.append(f"Semantic validation failed: {str(e)}")
                confidence = basic_result.confidence * 0.7
        else:
            confidence = basic_result.confidence
            recommendations.append("No validation agents available for semantic review")
        
        passed = confidence >= 0.6 and len([issue for issue in issues_found if "semantic" in issue.lower()]) == 0
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            validation_level=ValidationLevel.SEMANTIC,
            checks_performed=checks_performed,
            issues_found=issues_found,
            recommendations=recommendations,
        )
    
    async def _consensus_validation(self, task: CrossValidationTask) -> ValidationResult:
        """Perform consensus validation across multiple agents."""
        checks_performed = []
        issues_found = []
        recommendations = []
        consensus_scores = {}
        
        # Start with semantic validation
        semantic_result = await self._semantic_validation(task)
        checks_performed.extend(semantic_result.checks_performed)
        issues_found.extend(semantic_result.issues_found)
        recommendations.extend(semantic_result.recommendations)
        
        # Consensus validation with multiple agents
        if len(task.validation_agents) >= 2:
            checks_performed.append("multi_agent_consensus")
            
            validation_results = []
            
            for i, agent in enumerate(task.validation_agents):
                agent_score = await self._get_agent_validation_score(
                    agent, task.primary_response, task.context, f"validator_{i}"
                )
                validation_results.append(agent_score)
                consensus_scores[f"agent_{i}"] = agent_score
            
            # Calculate consensus metrics
            mean_score = sum(validation_results) / len(validation_results)
            score_variance = sum((score - mean_score) ** 2 for score in validation_results) / len(validation_results)
            consensus_agreement = 1.0 - min(score_variance * 4, 1.0)  # Normalize variance to agreement
            
            consensus_scores["mean_score"] = mean_score
            consensus_scores["variance"] = score_variance
            consensus_scores["agreement"] = consensus_agreement
            
            # Check for consensus issues
            if consensus_agreement < self.voting_config.confidence_threshold:
                issues_found.append(f"Low consensus agreement: {consensus_agreement:.2f}")
            
            if score_variance > 0.3:
                issues_found.append("High variance in agent assessments")
                recommendations.append("Consider additional validation or clarification")
            
            # Final confidence combines semantic and consensus
            consensus_confidence = mean_score * consensus_agreement
            confidence = min(semantic_result.confidence, consensus_confidence)
            
        else:
            confidence = semantic_result.confidence
            recommendations.append("Insufficient agents for meaningful consensus validation")
        
        passed = (
            confidence >= 0.7 and
            len([issue for issue in issues_found if "consensus" in issue.lower() or "variance" in issue.lower()]) == 0
        )
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            validation_level=ValidationLevel.CONSENSUS,
            checks_performed=checks_performed,
            issues_found=issues_found,
            recommendations=recommendations,
            consensus_scores=consensus_scores,
        )
    
    async def _comprehensive_validation(self, task: CrossValidationTask) -> ValidationResult:
        """Perform comprehensive validation with all available checks."""
        checks_performed = []
        issues_found = []
        recommendations = []
        
        # Run consensus validation (which includes semantic and basic)
        consensus_result = await self._consensus_validation(task)
        checks_performed.extend(consensus_result.checks_performed)
        issues_found.extend(consensus_result.issues_found)
        recommendations.extend(consensus_result.recommendations)
        
        # Additional comprehensive checks
        checks_performed.append("comprehensive_analysis")
        
        # Domain-specific validation based on context
        domain = task.context.get("domain", "general")
        
        if domain == "coding":
            code_issues = await self._validate_code_response(task.primary_response)
            if code_issues:
                issues_found.extend(code_issues)
                
        elif domain == "rag" or domain == "knowledge":
            fact_issues = await self._validate_factual_response(task.primary_response, task.context)
            if fact_issues:
                issues_found.extend(fact_issues)
        
        # Final comprehensive assessment
        comprehensive_penalty = len(issues_found) * 0.05
        confidence = max(0.0, consensus_result.confidence - comprehensive_penalty)
        
        passed = confidence >= 0.75 and len(issues_found) <= 2
        
        if not passed:
            recommendations.insert(0, "Response requires significant improvements before acceptance")
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            validation_level=ValidationLevel.COMPREHENSIVE,
            checks_performed=checks_performed,
            issues_found=issues_found,
            recommendations=recommendations,
            consensus_scores=consensus_result.consensus_scores,
        )
    
    async def _simulate_semantic_validation(
        self, response: Response, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate semantic validation (would use actual agent in production)."""
        content = str(response.content).lower()
        
        # Simulate relevance scoring
        task_keywords = context.get("keywords", [])
        if task_keywords:
            keyword_matches = sum(1 for keyword in task_keywords if keyword.lower() in content)
            relevance_score = min(1.0, keyword_matches / len(task_keywords))
        else:
            relevance_score = 0.8  # Default when no keywords available
        
        # Simulate completeness scoring
        content_length = len(content)
        if content_length < 50:
            completeness_score = 0.3
        elif content_length < 200:
            completeness_score = 0.6
        else:
            completeness_score = 0.9
        
        # Simulate clarity scoring
        if "unclear" in content or "confusing" in content:
            clarity_score = 0.4
        elif any(word in content for word in ["clearly", "specifically", "detailed"]):
            clarity_score = 0.9
        else:
            clarity_score = 0.7
        
        semantic_issues = []
        if "error" in content:
            semantic_issues.append("Contains error references")
        if content.count("todo") > 2:
            semantic_issues.append("Multiple incomplete sections")
        
        return {
            "semantic_issues": semantic_issues,
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "clarity_score": clarity_score,
            "overall_assessment": f"Simulated assessment with {len(semantic_issues)} issues found"
        }
    
    async def _get_agent_validation_score(
        self, agent: Agent, response: Response, context: Dict[str, Any], agent_id: str
    ) -> float:
        """Get validation score from a specific agent."""
        try:
            # Simulate agent validation scoring
            # In production, this would send a validation request to the agent
            
            content_quality = 0.8
            if "comprehensive" in str(response.content).lower():
                content_quality += 0.1
            if "error" in str(response.content).lower():
                content_quality -= 0.2
            
            # Add some variability based on agent_id for realistic consensus testing
            agent_variance = hash(agent_id) % 20 / 100  # -0.1 to +0.1 variance
            
            return max(0.0, min(1.0, content_quality + agent_variance - 0.1))
            
        except Exception:
            return 0.5  # Default score if agent validation fails
    
    async def _validate_code_response(self, response: Response) -> List[str]:
        """Validate code-specific aspects of response."""
        issues = []
        content = str(response.content)
        
        # Basic code validation
        if "```" not in content and any(keyword in content.lower() for keyword in ["function", "class", "def", "import"]):
            issues.append("Code content not properly formatted with code blocks")
        
        if content.count("TODO") > 3:
            issues.append("Excessive TODO comments in code")
        
        if "syntax error" in content.lower():
            issues.append("Contains syntax error references")
        
        return issues
    
    async def _validate_factual_response(self, response: Response, context: Dict[str, Any]) -> List[str]:
        """Validate factual/knowledge-based aspects of response."""
        issues = []
        content = str(response.content).lower()
        
        # Check for uncertainty indicators
        uncertainty_words = ["maybe", "possibly", "might", "not sure", "unclear"]
        uncertainty_count = sum(1 for word in uncertainty_words if word in content)
        
        if uncertainty_count > 3:
            issues.append("High uncertainty in factual claims")
        
        # Check for source citations
        if context.get("require_sources", False):
            if not any(indicator in content for indicator in ["source:", "reference:", "according to"]):
                issues.append("Missing source citations for factual claims")
        
        return issues
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation activities."""
        if not self.validation_history:
            return {"total_validations": 0}
        
        total_validations = len(self.validation_history)
        passed_validations = sum(1 for result in self.validation_history if result.passed)
        
        avg_confidence = sum(result.confidence for result in self.validation_history) / total_validations
        avg_execution_time = sum(
            result.execution_time for result in self.validation_history if result.execution_time
        ) / total_validations
        
        return {
            "total_validations": total_validations,
            "passed_validations": passed_validations,
            "success_rate": passed_validations / total_validations,
            "average_confidence": avg_confidence,
            "average_execution_time": avg_execution_time,
            "validation_levels_used": list(set(result.validation_level for result in self.validation_history)),
        }


def create_cross_agent_validator(
    voting_config: Optional[VotingConfig] = None,
    tracer: Optional[PrecisionTracer] = None,
) -> CrossAgentValidator:
    """
    Create a cross-agent validator with precision enhancement capabilities.
    
    Args:
        voting_config: Configuration for voting mechanisms
        tracer: Precision tracer for logging
        
    Returns:
        Configured CrossAgentValidator
    """
    return CrossAgentValidator(voting_config=voting_config, tracer=tracer)