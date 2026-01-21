"""
Prompt templates for the multi-agent coding system.

Provides system prompts and templates for various coding tasks.
"""

from pathlib import Path
from typing import Optional

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")
    return prompt_path.read_text()


def get_coding_system_prompt() -> str:
    """Get the main coding agent system prompt."""
    return load_prompt("coding_system")


def get_code_review_prompt() -> str:
    """Get the code review prompt."""
    return load_prompt("code_review")


def get_feature_dev_prompt() -> str:
    """Get the feature development prompt."""
    return load_prompt("feature_dev")


def get_code_architect_prompt() -> str:
    """Get the code architect prompt."""
    return load_prompt("code_architect")


def get_debugging_prompt() -> str:
    """Get the debugging prompt."""
    return load_prompt("debugging")


__all__ = [
    "load_prompt",
    "get_coding_system_prompt",
    "get_code_review_prompt",
    "get_feature_dev_prompt",
    "get_code_architect_prompt",
    "get_debugging_prompt",
]
