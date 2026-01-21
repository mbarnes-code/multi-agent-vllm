"""
Tool execution utilities for the multi-agent system.

Adapted from claude-quickstarts/agents/utils/tool_util.py for use with
VLLM's OpenAI-compatible API.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ..tools.base import Tool, ToolRegistry


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]
    
    @classmethod
    def from_openai_format(cls, tool_call: Dict[str, Any]) -> "ToolCall":
        """Create from OpenAI function call format."""
        function = tool_call.get("function", {})
        args = function.get("arguments", "{}")
        
        # Parse arguments if string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        
        return cls(
            id=tool_call.get("id", ""),
            name=function.get("name", ""),
            arguments=args,
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_call_id: str
    content: str
    is_error: bool = False
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI tool result format."""
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


class ToolExecutor:
    """
    Executes tools and manages tool results.
    
    Supports both parallel and sequential execution of tool calls.
    """
    
    def __init__(
        self,
        tools: Optional[List[Tool]] = None,
        registry: Optional[ToolRegistry] = None,
        parallel: bool = True,
        max_concurrent: int = 10,
    ):
        """
        Initialize the tool executor.
        
        Args:
            tools: List of tools to register
            registry: Existing tool registry to use
            parallel: Whether to execute tools in parallel
            max_concurrent: Maximum concurrent tool executions
        """
        self.registry = registry or ToolRegistry()
        self.parallel = parallel
        self.max_concurrent = max_concurrent
        
        # Register provided tools
        if tools:
            for tool in tools:
                self.registry.register(tool)
    
    def register_tool(self, tool: Tool) -> None:
        """Register a tool."""
        self.registry.register(tool)
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tools schema."""
        return self.registry.to_openai_tools()
    
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call.
        
        Args:
            tool_call: The tool call to execute
            
        Returns:
            ToolResult with the execution result
        """
        tool = self.registry.get(tool_call.name)
        
        if tool is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: Tool '{tool_call.name}' not found",
                is_error=True,
            )
        
        try:
            result = await tool.execute(**tool_call.arguments)
            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(result),
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error executing {tool_call.name}: {str(e)}",
                is_error=True,
            )
    
    async def execute_tools(
        self,
        tool_calls: List[Union[ToolCall, Dict[str, Any]]],
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls.
        
        Args:
            tool_calls: List of tool calls (ToolCall objects or OpenAI format dicts)
            
        Returns:
            List of ToolResults
        """
        # Convert to ToolCall objects if needed
        calls = []
        for tc in tool_calls:
            if isinstance(tc, ToolCall):
                calls.append(tc)
            else:
                calls.append(ToolCall.from_openai_format(tc))
        
        if self.parallel:
            # Execute in parallel with concurrency limit
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def execute_with_semaphore(call: ToolCall) -> ToolResult:
                async with semaphore:
                    return await self.execute_tool(call)
            
            results = await asyncio.gather(
                *[execute_with_semaphore(call) for call in calls]
            )
        else:
            # Execute sequentially
            results = []
            for call in calls:
                result = await self.execute_tool(call)
                results.append(result)
        
        return list(results)
    
    def execute_tools_sync(
        self,
        tool_calls: List[Union[ToolCall, Dict[str, Any]]],
    ) -> List[ToolResult]:
        """Synchronous wrapper for execute_tools."""
        return asyncio.run(self.execute_tools(tool_calls))


async def execute_tools(
    tool_calls: List[Dict[str, Any]],
    tool_dict: Dict[str, Tool],
    parallel: bool = True,
) -> List[Dict[str, Any]]:
    """
    Execute tools and return results in OpenAI format.
    
    This is a convenience function for simple use cases.
    
    Args:
        tool_calls: List of tool calls in OpenAI format
        tool_dict: Dictionary mapping tool names to Tool objects
        parallel: Whether to execute in parallel
        
    Returns:
        List of tool results in OpenAI message format
    """
    executor = ToolExecutor(tools=list(tool_dict.values()), parallel=parallel)
    results = await executor.execute_tools(tool_calls)
    return [result.to_openai_format() for result in results]


def parse_tool_calls(response: Dict[str, Any]) -> List[ToolCall]:
    """
    Parse tool calls from an OpenAI API response.
    
    Args:
        response: The API response containing tool calls
        
    Returns:
        List of ToolCall objects
    """
    tool_calls = []
    
    # Handle different response formats
    if "choices" in response:
        for choice in response["choices"]:
            message = choice.get("message", {})
            calls = message.get("tool_calls", [])
            for tc in calls:
                tool_calls.append(ToolCall.from_openai_format(tc))
    elif "tool_calls" in response:
        for tc in response["tool_calls"]:
            tool_calls.append(ToolCall.from_openai_format(tc))
    
    return tool_calls


def format_tool_results_for_api(results: List[ToolResult]) -> List[Dict[str, Any]]:
    """
    Format tool results for sending back to the API.
    
    Args:
        results: List of ToolResult objects
        
    Returns:
        List of messages in OpenAI format
    """
    return [result.to_openai_format() for result in results]
