"""
Base tool definitions for the multi-agent framework.

Adapted from claude-quickstarts/agents/tools/base.py for use with
VLLM's OpenAI-compatible API.
"""

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union


@dataclass
class Tool(ABC):
    """
    Base class for all agent tools.
    
    Tools are callable functions that agents can use to interact with
    the environment, execute code, read/write files, etc.
    
    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        parameters: JSON Schema for the tool's parameters
    """
    
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_openai_function(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary format (alias for to_openai_function)."""
        return self.to_openai_function()
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        Execute the tool with provided parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            String result of the tool execution
        """
        pass
    
    def execute_sync(self, **kwargs) -> str:
        """Synchronous wrapper for execute."""
        return asyncio.run(self.execute(**kwargs))


class FunctionTool(Tool):
    """
    Tool that wraps a Python function.
    
    Automatically generates the parameter schema from the function signature.
    """
    
    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Create a tool from a Python function.
        
        Args:
            func: The function to wrap
            name: Override the function name
            description: Override the function docstring
        """
        self._func = func
        self._is_async = asyncio.iscoroutinefunction(func)
        
        # Extract name and description
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Execute {tool_name}"
        
        # Generate parameter schema from function signature
        parameters = self._generate_schema(func)
        
        super().__init__(
            name=tool_name,
            description=tool_description.strip(),
            parameters=parameters,
        )
    
    def _generate_schema(self, func: Callable) -> Dict[str, Any]:
        """Generate JSON Schema from function signature."""
        sig = inspect.signature(func)
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls", "context_variables"):
                continue
            
            # Determine type
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                param_type = type_map.get(param.annotation, "string")
            
            properties[param_name] = {"type": param_type}
            
            # Check if required
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute the wrapped function."""
        try:
            if self._is_async:
                result = await self._func(**kwargs)
            else:
                result = await asyncio.to_thread(self._func, **kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"


class ToolRegistry:
    """
    Registry for managing available tools.
    
    Provides methods for registering, retrieving, and executing tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def register_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tool:
        """Register a function as a tool."""
        tool = FunctionTool(func, name, description)
        self.register(tool)
        return tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_all(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Convert all tools to OpenAI function format."""
        return [tool.to_openai_function() for tool in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> str:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found"
        return await tool.execute(**kwargs)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __len__(self) -> int:
        return len(self._tools)


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Callable:
    """
    Decorator to convert a function into a Tool.
    
    Usage:
        @tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b
    """
    def decorator(func: Callable) -> FunctionTool:
        return FunctionTool(func, name, description)
    return decorator
