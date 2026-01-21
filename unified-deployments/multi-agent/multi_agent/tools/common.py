"""
Common tools available to all agents.
"""

from datetime import datetime
from typing import Optional


def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web for information.
    
    Args:
        query: Search query
        num_results: Number of results to return
    """
    # In production, integrate with a search API
    return f"""Web search for: "{query}"

Note: Web search is not currently configured.
To enable web search, configure a search API (e.g., Tavily, SerpAPI, or Brave Search).

For now, please rely on the knowledge base or provide the information directly."""


def get_current_time(timezone: str = "UTC") -> str:
    """
    Get the current date and time.
    
    Args:
        timezone: Timezone name (default: UTC)
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
    except (ImportError, KeyError):
        now = datetime.utcnow()
        timezone = "UTC"
    
    return f"Current time ({timezone}): {now.strftime('%Y-%m-%d %H:%M:%S')}"


def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.
    
    Args:
        expression: Mathematical expression to evaluate
    """
    # Safe evaluation using ast
    import ast
    import operator
    
    # Allowed operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    def eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Invalid constant: {node.value}")
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(operand)
        elif isinstance(node, ast.Expression):
            return eval_node(node.body)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")
    
    try:
        tree = ast.parse(expression, mode='eval')
        result = eval_node(tree)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating '{expression}': {str(e)}"
