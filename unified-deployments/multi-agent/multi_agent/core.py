"""
Core Swarm implementation for VLLM-based multi-agent orchestration.

Adapted from OpenAI Swarm to work with VLLM's OpenAI-compatible API.
"""

import copy
import json
from collections import defaultdict
from typing import List, Callable, Union, Optional, Any, Dict
import inspect

from openai import OpenAI
from pydantic import BaseModel

import structlog

logger = structlog.get_logger()

__CTX_VARS_NAME__ = "context_variables"


class Agent(BaseModel):
    """Agent definition with instructions, model, and available functions."""
    
    name: str = "Agent"
    model: str = "gpt-oss-120b"
    instructions: Union[str, Callable[[dict], str]] = "You are a helpful agent."
    functions: List[Callable] = []
    tool_choice: Optional[str] = None
    parallel_tool_calls: bool = True
    
    class Config:
        arbitrary_types_allowed = True


class Response(BaseModel):
    """Response from agent execution."""
    
    messages: List[Dict[str, Any]] = []
    agent: Optional[Agent] = None
    context_variables: dict = {}
    
    class Config:
        arbitrary_types_allowed = True


class Result(BaseModel):
    """Result from a function call."""
    
    value: str = ""
    agent: Optional[Agent] = None
    context_variables: dict = {}
    
    class Config:
        arbitrary_types_allowed = True


def function_to_json(func: Callable) -> dict:
    """Convert a Python function to OpenAI function schema."""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(f"Failed to get signature for function {func.__name__}: {str(e)}")

    parameters = {}
    for param in signature.parameters.values():
        if param.name == __CTX_VARS_NAME__:
            continue
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            param_type = type_map.get(param.annotation, "string")
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect.Parameter.empty and param.name != __CTX_VARS_NAME__
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }


def merge_chunk(message: dict, delta: dict) -> None:
    """Merge streaming delta into message."""
    for key, value in delta.items():
        if key == "tool_calls":
            if "tool_calls" not in message:
                message["tool_calls"] = {}
            for tool_call in value:
                idx = tool_call.get("index", 0)
                if idx not in message["tool_calls"]:
                    message["tool_calls"][idx] = {
                        "function": {"arguments": "", "name": ""},
                        "id": "",
                        "type": "",
                    }
                tc = message["tool_calls"][idx]
                if "function" in tool_call:
                    if "arguments" in tool_call["function"]:
                        tc["function"]["arguments"] += tool_call["function"]["arguments"]
                    if "name" in tool_call["function"]:
                        tc["function"]["name"] = tool_call["function"]["name"]
                if "id" in tool_call:
                    tc["id"] = tool_call["id"]
                if "type" in tool_call:
                    tc["type"] = tool_call["type"]
        elif isinstance(value, str):
            message[key] = message.get(key, "") + value
        else:
            message[key] = value


class Swarm:
    """
    Multi-agent orchestration system using VLLM backend.
    
    Supports agent handoffs, tool calling, and streaming responses.
    """
    
    def __init__(
        self,
        client: Optional[OpenAI] = None,
        base_url: Optional[str] = None,
        api_key: str = "not-needed",
    ):
        """
        Initialize Swarm with VLLM-compatible OpenAI client.
        
        Args:
            client: Pre-configured OpenAI client
            base_url: VLLM API endpoint (e.g., http://localhost:8000/v1)
            api_key: API key (not required for local VLLM)
        """
        if client:
            self.client = client
        else:
            self.client = OpenAI(
                base_url=base_url or "http://localhost:8000/v1",
                api_key=api_key,
            )
        logger.info("swarm_initialized", base_url=base_url)

    def get_chat_completion(
        self,
        agent: Agent,
        history: List[Dict],
        context_variables: dict,
        model_override: Optional[str] = None,
        stream: bool = False,
        debug: bool = False,
    ):
        """Get chat completion from VLLM."""
        context_variables = defaultdict(str, context_variables)
        
        # Resolve instructions
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        
        messages = [{"role": "system", "content": instructions}] + history
        
        if debug:
            logger.debug("chat_completion_request", messages=messages)

        # Build tools from agent functions
        tools = [function_to_json(f) for f in agent.functions] if agent.functions else None
        
        # Hide context_variables from model
        if tools:
            for tool in tools:
                params = tool["function"]["parameters"]
                params["properties"].pop(__CTX_VARS_NAME__, None)
                if __CTX_VARS_NAME__ in params.get("required", []):
                    params["required"].remove(__CTX_VARS_NAME__)

        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "stream": stream,
        }
        
        if tools:
            create_params["tools"] = tools
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls
            if agent.tool_choice:
                create_params["tool_choice"] = agent.tool_choice

        return self.client.chat.completions.create(**create_params)

    def handle_function_result(self, result: Any, debug: bool = False) -> Result:
        """Process function return value into Result."""
        if isinstance(result, Result):
            return result
        if isinstance(result, Agent):
            return Result(
                value=json.dumps({"assistant": result.name}),
                agent=result,
            )
        try:
            return Result(value=str(result))
        except Exception as e:
            error_msg = f"Failed to cast response to string: {result}. Error: {str(e)}"
            if debug:
                logger.error("function_result_error", error=error_msg)
            raise TypeError(error_msg)

    def handle_tool_calls(
        self,
        tool_calls: List,
        functions: List[Callable],
        context_variables: dict,
        debug: bool = False,
    ) -> Response:
        """Execute tool calls and return results."""
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(messages=[], agent=None, context_variables={})

        for tool_call in tool_calls:
            name = tool_call.function.name
            
            if name not in function_map:
                if debug:
                    logger.warning("tool_not_found", tool_name=name)
                partial_response.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error: Tool {name} not found.",
                })
                continue

            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
                
            if debug:
                logger.debug("tool_call", tool_name=name, args=args)

            func = function_map[name]
            
            # Pass context_variables if function accepts it
            if __CTX_VARS_NAME__ in inspect.signature(func).parameters:
                args[__CTX_VARS_NAME__] = context_variables

            try:
                raw_result = func(**args)
                result = self.handle_function_result(raw_result, debug)
            except Exception as e:
                logger.error("tool_execution_error", tool_name=name, error=str(e))
                result = Result(value=f"Error executing {name}: {str(e)}")

            partial_response.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result.value,
            })
            partial_response.context_variables.update(result.context_variables)
            
            if result.agent:
                partial_response.agent = result.agent

        return partial_response

    def run(
        self,
        agent: Agent,
        messages: List[Dict],
        context_variables: dict = None,
        model_override: Optional[str] = None,
        stream: bool = False,
        debug: bool = False,
        max_turns: int = 10,
        execute_tools: bool = True,
    ) -> Response:
        """
        Run agent conversation loop.
        
        Args:
            agent: Starting agent
            messages: Conversation history
            context_variables: Shared context across agents
            model_override: Override agent's default model
            stream: Enable streaming (returns generator)
            debug: Enable debug logging
            max_turns: Maximum conversation turns
            execute_tools: Whether to execute tool calls
            
        Returns:
            Response with messages, final agent, and context
        """
        if stream:
            return self.run_and_stream(
                agent=agent,
                messages=messages,
                context_variables=context_variables or {},
                model_override=model_override,
                debug=debug,
                max_turns=max_turns,
                execute_tools=execute_tools,
            )

        active_agent = agent
        context_variables = copy.deepcopy(context_variables or {})
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns and active_agent:
            completion = self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=False,
                debug=debug,
            )

            message = completion.choices[0].message
            
            if debug:
                logger.debug("completion_received", message=message.model_dump())

            # Add sender info
            message_dict = message.model_dump()
            message_dict["sender"] = active_agent.name
            history.append(message_dict)

            if not message.tool_calls or not execute_tools:
                if debug:
                    logger.debug("turn_ended", reason="no_tool_calls" if not message.tool_calls else "tools_disabled")
                break

            # Handle tool calls
            partial_response = self.handle_tool_calls(
                message.tool_calls,
                active_agent.functions,
                context_variables,
                debug,
            )
            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            
            if partial_response.agent:
                active_agent = partial_response.agent
                if debug:
                    logger.info("agent_handoff", new_agent=active_agent.name)

        return Response(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
        )

    def run_and_stream(
        self,
        agent: Agent,
        messages: List[Dict],
        context_variables: dict = None,
        model_override: Optional[str] = None,
        debug: bool = False,
        max_turns: int = 10,
        execute_tools: bool = True,
    ):
        """Run agent with streaming responses."""
        active_agent = agent
        context_variables = copy.deepcopy(context_variables or {})
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns:
            message = {
                "content": "",
                "sender": active_agent.name,
                "role": "assistant",
                "function_call": None,
                "tool_calls": defaultdict(
                    lambda: {
                        "function": {"arguments": "", "name": ""},
                        "id": "",
                        "type": "",
                    }
                ),
            }

            completion = self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=True,
                debug=debug,
            )

            yield {"delim": "start"}
            
            for chunk in completion:
                delta = chunk.choices[0].delta
                if delta.role == "assistant":
                    yield {"role": "assistant", "sender": active_agent.name}
                if delta.content:
                    yield {"content": delta.content}
                    message["content"] += delta.content
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if tc.id:
                            message["tool_calls"][idx]["id"] = tc.id
                        if tc.type:
                            message["tool_calls"][idx]["type"] = tc.type
                        if tc.function:
                            if tc.function.name:
                                message["tool_calls"][idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                message["tool_calls"][idx]["function"]["arguments"] += tc.function.arguments
                                
            yield {"delim": "end"}

            # Convert tool_calls dict to list
            message["tool_calls"] = list(message["tool_calls"].values()) if message["tool_calls"] else None
            
            if debug:
                logger.debug("stream_message_complete", message=message)
                
            history.append(message)

            if not message["tool_calls"] or not execute_tools:
                break

            # Handle tool calls
            from openai.types.chat.chat_completion_message_tool_call import (
                ChatCompletionMessageToolCall,
                Function,
            )
            
            tool_calls = [
                ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type=tc["type"],
                    function=Function(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in message["tool_calls"]
            ]

            partial_response = self.handle_tool_calls(
                tool_calls,
                active_agent.functions,
                context_variables,
                debug,
            )
            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            
            if partial_response.agent:
                active_agent = partial_response.agent

        yield {
            "response": Response(
                messages=history[init_len:],
                agent=active_agent,
                context_variables=context_variables,
            )
        }
