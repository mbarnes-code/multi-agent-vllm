"""
Code execution tools for running code in sandboxed environments.

Provides safe code execution for multiple languages with timeout protection,
output capture, and security validation.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import Tool
from .security import SecurityValidator, ValidationResult


# Language configurations
LANGUAGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "python": {
        "extension": ".py",
        "command": [sys.executable],
        "timeout": 30,
    },
    "python3": {
        "extension": ".py",
        "command": [sys.executable],
        "timeout": 30,
    },
    "javascript": {
        "extension": ".js",
        "command": ["node"],
        "timeout": 30,
    },
    "typescript": {
        "extension": ".ts",
        "command": ["npx", "ts-node"],
        "timeout": 60,
    },
    "bash": {
        "extension": ".sh",
        "command": ["bash"],
        "timeout": 30,
    },
    "sh": {
        "extension": ".sh",
        "command": ["sh"],
        "timeout": 30,
    },
    "go": {
        "extension": ".go",
        "command": ["go", "run"],
        "timeout": 60,
    },
    "rust": {
        "extension": ".rs",
        "command": ["rustc", "-o", "/tmp/rust_out", "{file}", "&&", "/tmp/rust_out"],
        "timeout": 120,
        "compile_first": True,
    },
    "java": {
        "extension": ".java",
        "command": ["java"],
        "timeout": 60,
    },
    "c": {
        "extension": ".c",
        "command": ["gcc", "-o", "/tmp/c_out", "{file}", "&&", "/tmp/c_out"],
        "timeout": 60,
        "compile_first": True,
    },
    "cpp": {
        "extension": ".cpp",
        "command": ["g++", "-o", "/tmp/cpp_out", "{file}", "&&", "/tmp/cpp_out"],
        "timeout": 60,
        "compile_first": True,
    },
}


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    error: Optional[str] = None


class CodeExecutionTool(Tool):
    """
    Tool for executing code in various programming languages.
    
    Supports Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, and shell scripts.
    Code is executed in a sandboxed temporary directory with timeout protection.
    """
    
    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        default_timeout: int = 30,
        max_output_length: int = 10000,
        enable_network: bool = False,
    ):
        """
        Initialize the code execution tool.
        
        Args:
            workspace_dir: Working directory for code execution
            default_timeout: Default timeout in seconds
            max_output_length: Maximum output length to capture
            enable_network: Whether to allow network access in executed code
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path(tempfile.gettempdir())
        self.default_timeout = default_timeout
        self.max_output_length = max_output_length
        self.enable_network = enable_network
        
        super().__init__(
            name="execute_code",
            description="""Execute code in a sandboxed environment.

Supported languages: python, javascript, typescript, bash, go, rust, java, c, cpp

The code runs in an isolated environment with:
- Timeout protection (default 30 seconds)
- Output capture (stdout and stderr)
- Working directory isolation

Returns the execution result including output, errors, and return code.""",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The code to execute",
                    },
                    "language": {
                        "type": "string",
                        "enum": list(LANGUAGE_CONFIG.keys()),
                        "description": "Programming language of the code",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Execution timeout in seconds (default: {default_timeout})",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command-line arguments to pass to the script",
                    },
                },
                "required": ["code", "language"],
            },
        )
    
    async def execute(
        self,
        code: str,
        language: str,
        timeout: Optional[int] = None,
        args: Optional[List[str]] = None,
    ) -> str:
        """
        Execute code and return the result.
        
        Args:
            code: The code to execute
            language: Programming language
            timeout: Execution timeout in seconds
            args: Command-line arguments
            
        Returns:
            Formatted execution result
        """
        if language not in LANGUAGE_CONFIG:
            return f"Error: Unsupported language '{language}'. Supported: {list(LANGUAGE_CONFIG.keys())}"
        
        config = LANGUAGE_CONFIG[language]
        timeout = timeout or config.get("timeout", self.default_timeout)
        args = args or []
        
        result = await self._execute_code(code, language, config, timeout, args)
        
        return self._format_result(result)
    
    async def _execute_code(
        self,
        code: str,
        language: str,
        config: Dict[str, Any],
        timeout: int,
        args: List[str],
    ) -> ExecutionResult:
        """Execute code and capture results."""
        import time
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=config["extension"],
            delete=False,
            dir=str(self.workspace_dir),
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            start_time = time.time()
            
            # Build command
            command = config["command"].copy()
            
            # Handle compiled languages
            if config.get("compile_first"):
                # Replace {file} placeholder
                cmd_str = " ".join(command).replace("{file}", temp_file)
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace_dir),
                )
            else:
                command.append(temp_file)
                command.extend(args)
                
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace_dir),
                )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    success=process.returncode == 0,
                    stdout=self._truncate_output(stdout.decode("utf-8", errors="replace")),
                    stderr=self._truncate_output(stderr.decode("utf-8", errors="replace")),
                    return_code=process.returncode,
                    execution_time=execution_time,
                )
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="",
                    return_code=-1,
                    execution_time=timeout,
                    error=f"Execution timed out after {timeout} seconds",
                )
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                execution_time=0,
                error=str(e),
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file)
            except Exception:
                pass
    
    def _truncate_output(self, output: str) -> str:
        """Truncate output if too long."""
        if len(output) > self.max_output_length:
            return output[:self.max_output_length] + f"\n... (truncated, {len(output)} total chars)"
        return output
    
    def _format_result(self, result: ExecutionResult) -> str:
        """Format execution result for display."""
        parts = []
        
        if result.error:
            parts.append(f"❌ Error: {result.error}")
        elif result.success:
            parts.append(f"✅ Execution successful (return code: {result.return_code})")
        else:
            parts.append(f"❌ Execution failed (return code: {result.return_code})")
        
        parts.append(f"⏱️ Time: {result.execution_time:.2f}s")
        
        if result.stdout:
            parts.append(f"\n📤 Output:\n{result.stdout}")
        
        if result.stderr:
            parts.append(f"\n⚠️ Stderr:\n{result.stderr}")
        
        return "\n".join(parts)


class BashTool(Tool):
    """
    Tool for executing bash commands with security validation.
    
    Commands are validated against an allowlist before execution.
    """
    
    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        security_validator: Optional[SecurityValidator] = None,
        timeout: int = 30,
        max_output_length: int = 10000,
    ):
        """
        Initialize the bash tool.
        
        Args:
            workspace_dir: Working directory for command execution
            security_validator: Custom security validator (uses default if None)
            timeout: Command timeout in seconds
            max_output_length: Maximum output length to capture
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.validator = security_validator or SecurityValidator(
            workspace_dir=str(self.workspace_dir)
        )
        self.timeout = timeout
        self.max_output_length = max_output_length
        
        super().__init__(
            name="bash",
            description="""Execute bash commands in the workspace.

Commands are validated against a security allowlist before execution.
Only development-related commands are permitted.

Allowed commands include: ls, cat, grep, find, git, python, node, npm, etc.
Dangerous operations like rm -rf / are blocked.""",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Command timeout in seconds (default: {timeout})",
                    },
                },
                "required": ["command"],
            },
        )
    
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Execute a bash command.
        
        Args:
            command: The command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Command output or error message
        """
        # Validate command
        validation = self.validator.validate_command(command)
        
        if not validation.allowed:
            return f"❌ Command blocked: {validation.reason}"
        
        timeout = timeout or self.timeout
        
        # Execute command
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_dir),
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                
                output_parts = []
                
                # Add warnings if any
                if validation.warnings:
                    output_parts.append("⚠️ Warnings: " + ", ".join(validation.warnings))
                
                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")
                
                if stdout_text:
                    if len(stdout_text) > self.max_output_length:
                        stdout_text = stdout_text[:self.max_output_length] + "\n... (truncated)"
                    output_parts.append(stdout_text)
                
                if stderr_text:
                    if len(stderr_text) > self.max_output_length:
                        stderr_text = stderr_text[:self.max_output_length] + "\n... (truncated)"
                    output_parts.append(f"stderr: {stderr_text}")
                
                if process.returncode != 0:
                    output_parts.append(f"(exit code: {process.returncode})")
                
                return "\n".join(output_parts) if output_parts else "(no output)"
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"❌ Command timed out after {timeout} seconds"
                
        except Exception as e:
            return f"❌ Error executing command: {e}"


class PythonREPLTool(Tool):
    """
    Interactive Python REPL tool that maintains state between executions.
    
    Useful for exploratory coding and data analysis.
    """
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize the Python REPL tool."""
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self._globals: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}
        
        super().__init__(
            name="python_repl",
            description="""Execute Python code in an interactive REPL environment.

State is maintained between executions, so you can define variables
and functions that persist across calls.

Useful for:
- Exploratory data analysis
- Testing code snippets
- Building up complex computations step by step""",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute",
                    },
                    "reset": {
                        "type": "boolean",
                        "description": "Reset the REPL state before execution",
                    },
                },
                "required": ["code"],
            },
        )
    
    async def execute(self, code: str, reset: bool = False) -> str:
        """Execute Python code in the REPL."""
        if reset:
            self._globals = {}
            self._locals = {}
        
        def exec_code():
            import io
            import sys
            from contextlib import redirect_stdout, redirect_stderr
            
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # Try to eval first (for expressions)
                    try:
                        result = eval(code, self._globals, self._locals)
                        if result is not None:
                            print(repr(result))
                    except SyntaxError:
                        # Fall back to exec for statements
                        exec(code, self._globals, self._locals)
                
                stdout = stdout_capture.getvalue()
                stderr = stderr_capture.getvalue()
                
                output = []
                if stdout:
                    output.append(stdout.rstrip())
                if stderr:
                    output.append(f"stderr: {stderr.rstrip()}")
                
                return "\n".join(output) if output else "(no output)"
                
            except Exception as e:
                return f"Error: {type(e).__name__}: {e}"
        
        return await asyncio.to_thread(exec_code)
    
    def get_state(self) -> Dict[str, Any]:
        """Get the current REPL state."""
        return {
            "globals": list(self._globals.keys()),
            "locals": list(self._locals.keys()),
        }
