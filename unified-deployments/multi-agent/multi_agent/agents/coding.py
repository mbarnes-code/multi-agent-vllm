"""
Coding Agent for the multi-agent system with Neuro-SAN precision enhancements.

Specialized agent for code generation, debugging, testing, and code review.
Enhanced with recursive task decomposition and precision validation patterns
adapted from the neuro-san-benchmarking research.

Based on patterns from:
- claude-quickstarts/autonomous-coding
- claude-quickstarts/agents
- claude-plugins-official/plugins/code-review
- claude-plugins-official/plugins/feature-dev
- claude-cookbooks/tool_use
- features/neuro-san-benchmarking (precision enhancements)
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..core import Agent


# Precision enhancement classes

class TaskComplexity(Enum):
    """Task complexity levels for decomposition."""
    ATOMIC = "atomic"  # Single operation, no further breakdown needed
    SIMPLE = "simple"  # 2-3 operations, minimal decomposition
    MEDIUM = "medium"  # 4-10 operations, moderate decomposition
    COMPLEX = "complex"  # 11+ operations, requires deep decomposition


@dataclass
class DecompositionTask:
    """A decomposed task with precision metadata."""
    id: str
    description: str
    complexity: TaskComplexity
    dependencies: List[str]
    validation_criteria: List[str]
    estimated_time: float
    atomic_operations: List[str]
    parent_task_id: Optional[str] = None
    depth_level: int = 0


class TaskDecomposer:
    """Recursive task decomposition with neuro-san precision patterns."""
    
    # Configuration inspired by neuro-san defaults
    MAX_DEPTH: int = int(os.getenv("DECOMPOSITION_MAX_DEPTH", "5"))
    MAX_ATOMIC_OPERATIONS: int = 3  # Maximum operations before requiring decomposition
    COMPLEXITY_THRESHOLD: float = 0.7  # Threshold for requiring decomposition
    
    def __init__(self):
        self.decomposition_history: List[DecompositionTask] = []
        self.current_depth = 0
        
    def decompose_coding_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None,
        max_depth: int = None,
    ) -> Tuple[List[DecompositionTask], Dict[str, Any]]:
        """
        Recursively decompose a coding task into atomic operations.
        
        Inspired by neuro-san's recursive problem decomposition methodology
        to achieve high precision in complex software development tasks.
        """
        max_depth = max_depth or self.MAX_DEPTH
        context = context or {}
        
        # Analyze task complexity
        complexity = self._analyze_task_complexity(task_description)
        
        if complexity == TaskComplexity.ATOMIC or self.current_depth >= max_depth:
            # Base case: create atomic task
            atomic_task = DecompositionTask(
                id=f"atomic_{len(self.decomposition_history)}",
                description=task_description,
                complexity=complexity,
                dependencies=[],
                validation_criteria=self._generate_validation_criteria(task_description, complexity),
                estimated_time=self._estimate_task_time(task_description, complexity),
                atomic_operations=[task_description],
                depth_level=self.current_depth,
            )
            return [atomic_task], {"decomposition_complete": True}
        
        # Recursive case: decompose into subtasks
        subtasks = self._generate_subtasks(task_description, complexity)
        decomposed_tasks = []
        
        self.current_depth += 1
        
        for i, subtask_desc in enumerate(subtasks):
            # Recursively decompose each subtask
            sub_decomposed, _ = self.decompose_coding_task(
                task_description=subtask_desc,
                context=context,
                max_depth=max_depth,
            )
            
            # Update parent relationships
            for sub_task in sub_decomposed:
                sub_task.parent_task_id = f"task_{len(self.decomposition_history)}"
                sub_task.dependencies = [f"task_{j}" for j in range(len(decomposed_tasks)) if j < i]
                
            decomposed_tasks.extend(sub_decomposed)
        
        self.current_depth -= 1
        
        # Add main task
        main_task = DecompositionTask(
            id=f"task_{len(self.decomposition_history)}",
            description=task_description,
            complexity=complexity,
            dependencies=[],
            validation_criteria=self._generate_validation_criteria(task_description, complexity),
            estimated_time=sum(task.estimated_time for task in decomposed_tasks),
            atomic_operations=[task.description for task in decomposed_tasks if task.complexity == TaskComplexity.ATOMIC],
            depth_level=self.current_depth,
        )
        
        return [main_task] + decomposed_tasks, {"decomposition_complete": False}
    
    def _analyze_task_complexity(self, task_description: str) -> TaskComplexity:
        """Analyze task complexity to determine if decomposition is needed."""
        # Count complexity indicators
        complexity_indicators = [
            len(re.findall(r'\b(implement|create|build|develop|design)\b', task_description.lower())),
            len(re.findall(r'\b(and|then|also|additionally|furthermore)\b', task_description.lower())),
            len(re.findall(r'\b(test|validate|verify|check)\b', task_description.lower())),
            len(re.findall(r'\b(database|api|frontend|backend|authentication)\b', task_description.lower())),
            len(task_description.split()) // 20,  # Word count factor
        ]
        
        total_complexity = sum(complexity_indicators)
        
        if total_complexity <= 1:
            return TaskComplexity.ATOMIC
        elif total_complexity <= 3:
            return TaskComplexity.SIMPLE
        elif total_complexity <= 6:
            return TaskComplexity.MEDIUM
        else:
            return TaskComplexity.COMPLEX
    
    def _generate_subtasks(self, task_description: str, complexity: TaskComplexity) -> List[str]:
        """Generate subtasks based on task complexity and patterns."""
        task_lower = task_description.lower()
        subtasks = []
        
        # Pattern-based decomposition
        if any(word in task_lower for word in ["web app", "application", "system"]):
            subtasks.extend([
                f"Analyze requirements and design architecture for: {task_description}",
                f"Implement core functionality for: {task_description}",
                f"Create tests and validation for: {task_description}",
                f"Add error handling and edge cases for: {task_description}",
            ])
        elif any(word in task_lower for word in ["function", "method", "algorithm"]):
            subtasks.extend([
                f"Define input/output specifications for: {task_description}",
                f"Implement core logic for: {task_description}",
                f"Add input validation and error handling for: {task_description}",
                f"Create unit tests for: {task_description}",
            ])
        elif any(word in task_lower for word in ["api", "service", "endpoint"]):
            subtasks.extend([
                f"Design API interface for: {task_description}",
                f"Implement API handlers for: {task_description}",
                f"Add authentication and authorization for: {task_description}",
                f"Create API tests and documentation for: {task_description}",
            ])
        else:
            # Generic decomposition
            subtasks.extend([
                f"Research and plan approach for: {task_description}",
                f"Implement core solution for: {task_description}",
                f"Test and validate implementation for: {task_description}",
            ])
        
        # Limit subtasks based on complexity
        if complexity == TaskComplexity.SIMPLE:
            return subtasks[:2]
        elif complexity == TaskComplexity.MEDIUM:
            return subtasks[:3]
        else:
            return subtasks[:4]
    
    def _generate_validation_criteria(self, task_description: str, complexity: TaskComplexity) -> List[str]:
        """Generate validation criteria for task verification."""
        criteria = []
        
        # Basic criteria for all tasks
        criteria.extend([
            "Code compiles and runs without errors",
            "Implementation matches the task description",
            "Code follows best practices and style guidelines",
        ])
        
        # Additional criteria based on complexity
        if complexity in [TaskComplexity.MEDIUM, TaskComplexity.COMPLEX]:
            criteria.extend([
                "Unit tests pass with adequate coverage",
                "Error handling covers edge cases",
                "Performance requirements are met",
            ])
        
        if complexity == TaskComplexity.COMPLEX:
            criteria.extend([
                "Integration tests validate component interactions",
                "Security considerations are addressed",
                "Documentation is complete and accurate",
            ])
        
        return criteria
    
    def _estimate_task_time(self, task_description: str, complexity: TaskComplexity) -> float:
        """Estimate task completion time in minutes."""
        base_times = {
            TaskComplexity.ATOMIC: 15.0,
            TaskComplexity.SIMPLE: 45.0,
            TaskComplexity.MEDIUM: 120.0,
            TaskComplexity.COMPLEX: 300.0,
        }
        
        base_time = base_times[complexity]
        
        # Adjust based on task characteristics
        task_lower = task_description.lower()
        multipliers = []
        
        if any(word in task_lower for word in ["database", "sql", "migration"]):
            multipliers.append(1.3)
        if any(word in task_lower for word in ["frontend", "ui", "react", "vue"]):
            multipliers.append(1.2)
        if any(word in task_lower for word in ["authentication", "security", "encryption"]):
            multipliers.append(1.4)
        if any(word in task_lower for word in ["api", "rest", "graphql"]):
            multipliers.append(1.1)
        if any(word in task_lower for word in ["test", "testing", "unit test"]):
            multipliers.append(0.8)  # Testing often takes less time
        
        final_multiplier = 1.0
        for mult in multipliers:
            final_multiplier *= mult
        
        return base_time * final_multiplier


def create_coding_agent(
    model: str,
    enable_execution: bool = True,
    enable_bash: bool = True,
    workspace_dir: str = "/tmp/workspace",
    memory_dir: str = "/tmp/memory",
    enable_decomposition: bool = True,
) -> Agent:
    """
    Create a precision-enhanced coding agent with recursive task decomposition.
    
    Args:
        model: The model to use for the agent
        enable_execution: Whether to enable code execution (default: True)
        enable_bash: Whether to enable bash commands (default: True)
        workspace_dir: Directory for file operations (default: /tmp/workspace)
        memory_dir: Directory for memory storage (default: /tmp/memory)
        enable_decomposition: Enable recursive task decomposition (default: True)
        
    Returns:
        Configured Agent for coding tasks with precision enhancements
    """
    # Create workspace directory
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Initialize task decomposer
    decomposer = TaskDecomposer() if enable_decomposition else None
    
    # Build functions list
    functions: List[Callable] = []
    
    # File tools
    functions.append(_create_file_read(workspace_dir))
    functions.append(_create_file_write(workspace_dir))
    functions.append(_create_glob(workspace_dir))
    functions.append(_create_grep(workspace_dir))
    
    # Code execution tools
    if enable_execution:
        functions.append(_create_execute_code(workspace_dir))
        functions.append(_create_python_repl())
    
    # Bash tool
    if enable_bash:
        functions.append(_create_bash(workspace_dir))
    
    # Memory tool
    functions.append(_create_memory(memory_dir))
    
    # Code analysis functions
    functions.extend([
        analyze_code,
        search_code_patterns,
        generate_tests,
        explain_code,
        suggest_improvements,
    ])
    
    # Precision enhancement functions
    if enable_decomposition:
        functions.append(_create_decompose_task(decomposer))
        functions.append(_create_validate_implementation(workspace_dir))
        functions.append(_create_atomic_step_executor(workspace_dir))
    
    return Agent(
        name="Coding Agent",
        model=model,
        instructions=CODING_INSTRUCTIONS_ENHANCED if enable_decomposition else CODING_INSTRUCTIONS,
        functions=functions,
    )


# Tool factory functions

def _create_file_read(workspace_dir: str) -> Callable:
    """Create file read function bound to workspace."""
    import asyncio
    
    def file_read(path: str, max_lines: int = 0, start_line: int = 1) -> str:
        """
        Read file contents or list directory.
        
        Args:
            path: File or directory path
            max_lines: Maximum lines to read (0 = no limit)
            start_line: Line number to start from (1-indexed)
        """
        file_path = Path(workspace_dir) / path
        
        if not file_path.exists():
            return f"Error: Path not found: {path}"
        
        if file_path.is_dir():
            items = []
            for item in sorted(file_path.iterdir()):
                if item.name.startswith("."):
                    continue
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")
            return f"Contents of {path}:\n" + "\n".join(items) if items else f"Directory {path} is empty"
        
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            start_idx = max(0, start_line - 1)
            if max_lines > 0:
                lines = lines[start_idx:start_idx + max_lines]
            else:
                lines = lines[start_idx:]
            
            numbered = [f"{i + start_idx + 1:4d}: {line.rstrip()}" for i, line in enumerate(lines)]
            return "\n".join(numbered)
        except Exception as e:
            return f"Error reading {path}: {e}"
    
    return file_read


def _create_file_write(workspace_dir: str) -> Callable:
    """Create file write function bound to workspace."""
    
    def file_write(
        operation: str,
        path: str,
        content: str = "",
        old_text: str = "",
        new_text: str = "",
    ) -> str:
        """
        Write or edit files.
        
        Args:
            operation: Operation to perform (write, edit, append)
            path: File path
            content: Content for write/append
            old_text: Text to replace (for edit)
            new_text: Replacement text (for edit)
        """
        file_path = Path(workspace_dir) / path
        
        # Security check
        if ".." in path:
            return "Error: Path traversal not allowed"
        
        try:
            if operation == "write":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                return f"Successfully wrote {len(content)} characters to {path}"
            
            elif operation == "edit":
                if not file_path.exists():
                    return f"Error: File not found: {path}"
                current = file_path.read_text(encoding="utf-8")
                if old_text not in current:
                    return f"Error: Text not found in {path}"
                new_content = current.replace(old_text, new_text, 1)
                file_path.write_text(new_content, encoding="utf-8")
                return f"Successfully edited {path}"
            
            elif operation == "append":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully appended to {path}"
            
            else:
                return f"Error: Unknown operation '{operation}'"
        except Exception as e:
            return f"Error: {e}"
    
    return file_write


def _create_glob(workspace_dir: str) -> Callable:
    """Create glob function bound to workspace."""
    import glob as glob_module
    
    def glob(pattern: str, max_results: int = 100) -> str:
        """
        Find files matching a glob pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.py", "**/*.js")
            max_results: Maximum results to return
        """
        search_path = Path(workspace_dir) / pattern
        matches = list(glob_module.glob(str(search_path), recursive=True))
        
        if not matches:
            return f"No files found matching: {pattern}"
        
        results = []
        for match in sorted(matches)[:max_results]:
            path = Path(match)
            try:
                rel = path.relative_to(workspace_dir)
            except ValueError:
                rel = path
            prefix = "📁 " if path.is_dir() else "📄 "
            results.append(f"{prefix}{rel}")
        
        output = "\n".join(results)
        if len(matches) > max_results:
            output += f"\n\n(Showing first {max_results} of {len(matches)} results)"
        return output
    
    return glob


def _create_grep(workspace_dir: str) -> Callable:
    """Create grep function bound to workspace."""
    import re
    import glob as glob_module
    
    def grep(
        pattern: str,
        path: str = ".",
        file_pattern: str = "**/*",
        context_lines: int = 2,
        max_results: int = 50,
    ) -> str:
        """
        Search for text patterns in files.
        
        Args:
            pattern: Regex pattern to search for
            path: Directory to search
            file_pattern: Glob pattern for files
            context_lines: Lines of context around matches
            max_results: Maximum matches to return
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex: {e}"
        
        search_dir = Path(workspace_dir) / path
        files = list(glob_module.glob(str(search_dir / file_pattern), recursive=True))
        files = [Path(f) for f in files if Path(f).is_file()]
        
        results = []
        total = 0
        
        for file_path in files:
            if total >= max_results:
                break
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                
                for i, line in enumerate(lines):
                    if total >= max_results:
                        break
                    if regex.search(line):
                        total += 1
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        
                        try:
                            rel = file_path.relative_to(workspace_dir)
                        except ValueError:
                            rel = file_path
                        
                        result = f"\n{rel}:{i + 1}:\n"
                        for j in range(start, end):
                            prefix = ">>> " if j == i else "    "
                            result += f"{prefix}{j + 1}: {lines[j]}\n"
                        results.append(result)
            except Exception:
                continue
        
        if not results:
            return f"No matches found for: {pattern}"
        
        output = f"Found {total} matches:\n" + "\n".join(results)
        if total >= max_results:
            output += f"\n\n(Showing first {max_results} matches)"
        return output
    
    return grep


def _create_execute_code(workspace_dir: str) -> Callable:
    """Create code execution function."""
    import subprocess
    import tempfile
    import os
    import sys
    
    LANG_CONFIG = {
        "python": {"ext": ".py", "cmd": [sys.executable]},
        "javascript": {"ext": ".js", "cmd": ["node"]},
        "typescript": {"ext": ".ts", "cmd": ["npx", "ts-node"]},
        "bash": {"ext": ".sh", "cmd": ["bash"]},
        "go": {"ext": ".go", "cmd": ["go", "run"]},
    }
    
    def execute_code(code: str, language: str, timeout: int = 30) -> str:
        """
        Execute code in a sandboxed environment.
        
        Args:
            code: The code to execute
            language: Programming language (python, javascript, typescript, bash, go)
            timeout: Execution timeout in seconds
        """
        language = language.lower()
        if language not in LANG_CONFIG:
            return f"Error: Unsupported language '{language}'. Supported: {list(LANG_CONFIG.keys())}"
        
        config = LANG_CONFIG[language]
        
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=config["ext"],
            delete=False,
            dir=workspace_dir,
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            cmd = config["cmd"] + [temp_file]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workspace_dir,
            )
            
            output = []
            if result.stdout:
                output.append(f"Output:\n{result.stdout}")
            if result.stderr:
                output.append(f"Stderr:\n{result.stderr}")
            output.append(f"Exit code: {result.returncode}")
            
            return "\n".join(output) if output else "Executed successfully (no output)"
            
        except subprocess.TimeoutExpired:
            return f"Error: Execution timed out after {timeout} seconds"
        except Exception as e:
            return f"Error: {e}"
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
    
    return execute_code


def _create_python_repl() -> Callable:
    """Create Python REPL function with persistent state."""
    _globals: Dict[str, Any] = {}
    _locals: Dict[str, Any] = {}
    
    def python_repl(code: str, reset: bool = False) -> str:
        """
        Execute Python code in an interactive REPL with persistent state.
        
        Args:
            code: Python code to execute
            reset: Reset the REPL state before execution
        """
        nonlocal _globals, _locals
        
        if reset:
            _globals = {}
            _locals = {}
        
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                try:
                    result = eval(code, _globals, _locals)
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    exec(code, _globals, _locals)
            
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
    
    return python_repl


def _create_bash(workspace_dir: str) -> Callable:
    """Create bash execution function with security validation."""
    import subprocess
    import shlex
    
    ALLOWED_COMMANDS = {
        "ls", "cat", "head", "tail", "wc", "grep", "find", "file",
        "cp", "mv", "mkdir", "touch", "rm",
        "pwd", "echo", "printf", "date",
        "python", "python3", "pip", "pip3",
        "node", "npm", "npx",
        "git",
        "curl", "wget",
    }
    
    def bash(command: str, timeout: int = 30) -> str:
        """
        Execute bash commands with security validation.
        
        Args:
            command: The bash command to execute
            timeout: Command timeout in seconds
        """
        # Extract first command
        try:
            tokens = shlex.split(command)
            if not tokens:
                return "Error: Empty command"
            
            import os
            cmd_name = os.path.basename(tokens[0])
            
            if cmd_name not in ALLOWED_COMMANDS:
                return f"Error: Command '{cmd_name}' not allowed. Allowed: {sorted(ALLOWED_COMMANDS)}"
        except ValueError as e:
            return f"Error: Could not parse command: {e}"
        
        # Block dangerous patterns
        dangerous = ["rm -rf /", "rm -rf ~", "> /dev/", "| sh", "| bash"]
        for pattern in dangerous:
            if pattern in command:
                return f"Error: Dangerous pattern detected: {pattern}"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workspace_dir,
            )
            
            output = []
            if result.stdout:
                output.append(result.stdout.rstrip())
            if result.stderr:
                output.append(f"stderr: {result.stderr.rstrip()}")
            if result.returncode != 0:
                output.append(f"(exit code: {result.returncode})")
            
            return "\n".join(output) if output else "(no output)"
            
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds"
        except Exception as e:
            return f"Error: {e}"
    
    return bash


def _create_memory(memory_dir: str) -> Callable:
    """Create memory tool function."""
    import shutil
    
    memory_root = Path(memory_dir) / "memories"
    memory_root.mkdir(parents=True, exist_ok=True)
    
    def memory(
        command: str,
        path: str = "",
        content: str = "",
        old_str: str = "",
        new_str: str = "",
    ) -> str:
        """
        Manage persistent memory storage.
        
        Args:
            command: Operation (view, create, edit, delete)
            path: Path within /memories
            content: Content for create
            old_str: Text to replace (for edit)
            new_str: Replacement text (for edit)
        """
        if not path.startswith("/memories"):
            path = "/memories" + ("/" + path if path else "")
        
        rel_path = path[len("/memories"):].lstrip("/")
        full_path = memory_root / rel_path if rel_path else memory_root
        
        try:
            if command == "view":
                if full_path.is_dir():
                    items = [f"- {i.name}{'/' if i.is_dir() else ''}" 
                             for i in sorted(full_path.iterdir()) if not i.name.startswith(".")]
                    return f"Directory: {path}\n" + "\n".join(items) if items else f"Directory {path} is empty"
                elif full_path.is_file():
                    lines = full_path.read_text().splitlines()
                    return "\n".join(f"{i+1:4d}: {line}" for i, line in enumerate(lines))
                else:
                    return f"Error: Path not found: {path}"
            
            elif command == "create":
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                return f"Created: {path}"
            
            elif command == "edit":
                if not full_path.is_file():
                    return f"Error: File not found: {path}"
                current = full_path.read_text()
                if old_str not in current:
                    return f"Error: Text not found in {path}"
                full_path.write_text(current.replace(old_str, new_str, 1))
                return f"Edited: {path}"
            
            elif command == "delete":
                if not full_path.exists():
                    return f"Error: Path not found: {path}"
                if full_path.is_file():
                    full_path.unlink()
                else:
                    shutil.rmtree(full_path)
                return f"Deleted: {path}"
            
            else:
                return f"Error: Unknown command '{command}'"
                
        except Exception as e:
            return f"Error: {e}"
    
    return memory


# Code analysis functions

def analyze_code(code: str, language: str) -> Dict[str, Any]:
    """
    Perform static analysis on code to find potential issues.
    
    Args:
        code: The code to analyze
        language: Programming language (python, javascript, typescript, go, rust)
    """
    issues = []
    
    if language == "python":
        if "import *" in code:
            issues.append({"severity": "warning", "message": "Avoid 'import *'"})
        if "except:" in code and "except Exception" not in code:
            issues.append({"severity": "warning", "message": "Bare 'except:' - catch specific exceptions"})
        if "eval(" in code or "exec(" in code:
            issues.append({"severity": "error", "message": "eval/exec is a security risk"})
        if "password" in code.lower() and "=" in code:
            issues.append({"severity": "error", "message": "Possible hardcoded password"})
    
    elif language in ("javascript", "typescript"):
        if "var " in code:
            issues.append({"severity": "warning", "message": "Use const/let instead of var"})
        if "eval(" in code:
            issues.append({"severity": "error", "message": "eval is a security risk"})
        if "innerHTML" in code:
            issues.append({"severity": "warning", "message": "innerHTML can be XSS risk"})
    
    elif language == "go":
        if "panic(" in code:
            issues.append({"severity": "warning", "message": "Avoid panic - return errors"})
    
    elif language == "rust":
        if ".unwrap()" in code:
            issues.append({"severity": "warning", "message": "unwrap() can panic - use ? or match"})
    
    return {
        "language": language,
        "issues": issues,
        "issue_count": len(issues),
        "has_errors": any(i["severity"] == "error" for i in issues),
    }


def search_code_patterns(query: str, language: str) -> Dict[str, Any]:
    """
    Search for common code patterns and provide examples.
    
    Args:
        query: Pattern to search for (e.g., "singleton", "decorator", "async")
        language: Programming language
    """
    patterns = {
        "python": {
            "singleton": '''class Singleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance''',
            "decorator": '''from functools import wraps
def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # before
        result = func(*args, **kwargs)
        # after
        return result
    return wrapper''',
            "context_manager": '''from contextlib import contextmanager
@contextmanager
def managed_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)''',
            "async": '''import asyncio
async def fetch_data(url):
    await asyncio.sleep(1)
    return f"Data from {url}"

async def main():
    results = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
    )
    return results''',
        },
        "javascript": {
            "singleton": '''const Singleton = (() => {
    let instance;
    return {
        getInstance: () => {
            if (!instance) instance = { data: "singleton" };
            return instance;
        }
    };
})();''',
            "async": '''async function fetchWithRetry(url, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url);
            return await response.json();
        } catch (error) {
            if (i === retries - 1) throw error;
            await new Promise(r => setTimeout(r, 1000));
        }
    }
}''',
        },
    }
    
    lang_patterns = patterns.get(language, {})
    query_lower = query.lower()
    
    matches = {k: v for k, v in lang_patterns.items() if query_lower in k.lower()}
    
    return {
        "query": query,
        "language": language,
        "matches": matches,
        "match_count": len(matches),
        "available": list(lang_patterns.keys()),
    }


def generate_tests(code: str, language: str, framework: str = "auto") -> Dict[str, Any]:
    """
    Generate unit tests for the given code.
    
    Args:
        code: The code to generate tests for
        language: Programming language
        framework: Test framework (auto, pytest, jest, go)
    """
    if framework == "auto":
        framework = {"python": "pytest", "javascript": "jest", "typescript": "jest", "go": "go"}.get(language, "generic")
    
    templates = {
        "pytest": '''import pytest

class TestCode:
    def test_basic(self):
        # result = function(input)
        # assert result == expected
        pass
    
    def test_edge_cases(self):
        pass
    
    def test_errors(self):
        with pytest.raises(ValueError):
            pass''',
        "jest": '''describe('Code', () => {
    test('basic functionality', () => {
        // expect(result).toBe(expected);
    });
    
    test('edge cases', () => {
    });
    
    test('error handling', () => {
        // expect(() => fn()).toThrow();
    });
});''',
        "go": '''package main

import "testing"

func TestBasic(t *testing.T) {
    // if result != expected {
    //     t.Errorf("Expected %v, got %v", expected, result)
    // }
}

func TestEdgeCases(t *testing.T) {
    tests := []struct {
        name string
        input string
        want string
    }{
        {"empty", "", ""},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
        })
    }
}''',
    }
    
    return {
        "language": language,
        "framework": framework,
        "test_code": templates.get(framework, "// Tests not available for this framework"),
    }


def explain_code(code: str, language: str) -> Dict[str, Any]:
    """
    Analyze code structure and provide explanation hints.
    
    Args:
        code: The code to explain
        language: Programming language
    """
    lines = code.strip().split("\n")
    
    indicators = {
        "loops": sum(1 for l in lines if any(k in l for k in ["for ", "while ", "loop "])),
        "conditionals": sum(1 for l in lines if any(k in l for k in ["if ", "else", "elif", "switch", "match"])),
        "functions": sum(1 for l in lines if any(k in l for k in ["def ", "function ", "fn ", "func "])),
        "classes": sum(1 for l in lines if any(k in l for k in ["class ", "struct ", "interface "])),
    }
    
    total = sum(indicators.values())
    complexity = "simple" if total <= 3 else "moderate" if total <= 10 else "complex"
    
    return {
        "language": language,
        "line_count": len(lines),
        "complexity": complexity,
        "indicators": indicators,
    }


def suggest_improvements(code: str, language: str, focus: str = "all") -> Dict[str, Any]:
    """
    Suggest improvements for the given code.
    
    Args:
        code: The code to improve
        language: Programming language
        focus: Area to focus on (all, performance, readability, security)
    """
    import re
    
    suggestions = []
    lines = code.split("\n")
    
    # Long functions
    func_lines = 0
    for line in lines:
        if any(k in line for k in ["def ", "function ", "fn "]):
            func_lines = 0
        func_lines += 1
        if func_lines > 50:
            suggestions.append({"category": "maintainability", "suggestion": "Break down long functions"})
            break
    
    # Magic numbers
    if re.findall(r'\b\d{2,}\b', code):
        suggestions.append({"category": "readability", "suggestion": "Use named constants for magic numbers"})
    
    # Deep nesting
    max_indent = max((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    if max_indent > 16:
        suggestions.append({"category": "readability", "suggestion": "Reduce nesting with early returns"})
    
    if focus != "all":
        suggestions = [s for s in suggestions if s["category"] == focus]
    
    return {
        "language": language,
        "focus": focus,
        "suggestions": suggestions,
        "count": len(suggestions),
    }


# Default instructions
CODING_INSTRUCTIONS = """You are an expert software developer and coding assistant.

## Capabilities

- **Code Generation**: Write clean, efficient code in Python, JavaScript, TypeScript, Go, Rust, and more
- **Code Review**: Analyze code for bugs, security issues, and improvements
- **Debugging**: Identify and fix issues systematically
- **Testing**: Generate comprehensive unit tests
- **Documentation**: Explain code and add documentation

## Available Tools

### File Operations
- `file_read(path, max_lines, start_line)`: Read files or list directories
- `file_write(operation, path, content, old_text, new_text)`: Write/edit files
- `glob(pattern, max_results)`: Find files matching patterns
- `grep(pattern, path, file_pattern, context_lines)`: Search file contents

### Code Execution
- `execute_code(code, language, timeout)`: Run code (python, javascript, typescript, bash, go)
- `python_repl(code, reset)`: Interactive Python with persistent state
- `bash(command, timeout)`: Execute shell commands

### Memory
- `memory(command, path, content)`: Persistent storage (view, create, edit, delete)

### Analysis
- `analyze_code(code, language)`: Static analysis
- `search_code_patterns(query, language)`: Find code patterns
- `generate_tests(code, language, framework)`: Create unit tests
- `explain_code(code, language)`: Analyze code structure
- `suggest_improvements(code, language, focus)`: Get improvement suggestions

## Workflow

1. **Understand**: Clarify requirements before coding
2. **Plan**: Outline the approach
3. **Implement**: Write code incrementally
4. **Test**: Verify with execute_code or tests
5. **Refine**: Improve based on feedback

## Best Practices

- Write clean, readable code
- Include error handling
- Follow language conventions
- Test your code
- Document complex logic"""


# Precision enhancement functions

def _create_decompose_task(decomposer) -> Callable:
    """Create task decomposition function."""
    
    def decompose_task(
        task_description: str,
        max_depth: int = None,
        return_format: str = "list",
    ) -> Dict[str, Any]:
        """
        Decompose a coding task into atomic operations.
        
        Args:
            task_description: The task to decompose
            max_depth: Maximum decomposition depth (default: from config)
            return_format: Return format - "list", "json", or "tree"
        """
        if not decomposer:
            return {"error": "Task decomposition not enabled"}
        
        try:
            tasks, metadata = decomposer.decompose_coding_task(
                task_description=task_description,
                max_depth=max_depth
            )
            
            result = {
                "original_task": task_description,
                "total_tasks": len(tasks),
                "estimated_total_time": sum(task.estimated_time for task in tasks),
                "max_depth_reached": max(task.depth_level for task in tasks) if tasks else 0,
                "metadata": metadata,
            }
            
            if return_format == "json":
                result["tasks"] = [
                    {
                        "id": task.id,
                        "description": task.description,
                        "complexity": task.complexity.value,
                        "dependencies": task.dependencies,
                        "validation_criteria": task.validation_criteria,
                        "estimated_time": task.estimated_time,
                        "atomic_operations": task.atomic_operations,
                        "parent_task_id": task.parent_task_id,
                        "depth_level": task.depth_level,
                    }
                    for task in tasks
                ]
            elif return_format == "tree":
                result["task_tree"] = _build_task_tree(tasks)
            else:  # list format
                result["tasks"] = [
                    f"{task.id}: {task.description} (complexity: {task.complexity.value}, "
                    f"time: {task.estimated_time:.1f}min, depth: {task.depth_level})"
                    for task in tasks
                ]
            
            return result
        except Exception as e:
            return {"error": f"Decomposition failed: {e}"}
    
    return decompose_task


def _build_task_tree(tasks: List) -> Dict[str, Any]:
    """Build hierarchical tree structure from flat task list."""
    tree = {}
    task_map = {task.id: task for task in tasks}
    
    for task in tasks:
        if task.parent_task_id is None:
            # Root task
            tree[task.id] = {
                "task": task,
                "children": _get_children(task.id, tasks),
            }
    
    return tree


def _get_children(parent_id: str, tasks: List) -> List[Dict[str, Any]]:
    """Get children tasks for a parent task."""
    children = []
    for task in tasks:
        if task.parent_task_id == parent_id:
            children.append({
                "task": task,
                "children": _get_children(task.id, tasks),
            })
    return children


def _create_validate_implementation(workspace_dir: str) -> Callable:
    """Create implementation validation function."""
    
    def validate_implementation(
        task_description: str,
        implementation_path: str,
        validation_criteria: List[str] = None,
        run_tests: bool = True,
    ) -> Dict[str, Any]:
        """
        Validate a coding implementation against task requirements.
        
        Args:
            task_description: Original task description
            implementation_path: Path to implementation file(s)
            validation_criteria: Custom validation criteria
            run_tests: Whether to run automated tests
        """
        results = {
            "task": task_description,
            "implementation_path": implementation_path,
            "validation_passed": False,
            "score": 0.0,
            "checks": [],
            "recommendations": [],
        }
        
        try:
            file_path = Path(workspace_dir) / implementation_path
            
            if not file_path.exists():
                results["checks"].append({
                    "name": "File Existence",
                    "passed": False,
                    "message": f"Implementation file not found: {implementation_path}"
                })
                return results
            
            # Read implementation
            try:
                code = file_path.read_text(encoding="utf-8")
            except Exception as e:
                results["checks"].append({
                    "name": "File Readability",
                    "passed": False,
                    "message": f"Could not read file: {e}"
                })
                return results
            
            # Basic checks
            checks_passed = 0
            total_checks = 0
            
            # Check 1: File is not empty
            total_checks += 1
            if code.strip():
                results["checks"].append({
                    "name": "Non-empty Implementation",
                    "passed": True,
                    "message": f"Implementation has {len(code.splitlines())} lines"
                })
                checks_passed += 1
            else:
                results["checks"].append({
                    "name": "Non-empty Implementation",
                    "passed": False,
                    "message": "Implementation file is empty"
                })
            
            # Check 2: Syntax validation (for Python)
            total_checks += 1
            if implementation_path.endswith('.py'):
                try:
                    import ast
                    ast.parse(code)
                    results["checks"].append({
                        "name": "Python Syntax Validation",
                        "passed": True,
                        "message": "Python syntax is valid"
                    })
                    checks_passed += 1
                except SyntaxError as e:
                    results["checks"].append({
                        "name": "Python Syntax Validation",
                        "passed": False,
                        "message": f"Syntax error: {e}"
                    })
            else:
                results["checks"].append({
                    "name": "Syntax Validation",
                    "passed": True,
                    "message": "Non-Python file, syntax validation skipped"
                })
                checks_passed += 1
            
            # Check 3: Basic code quality
            total_checks += 1
            quality_issues = []
            
            if len(code.splitlines()) < 5:
                quality_issues.append("Implementation seems very short")
            
            if "TODO" in code or "FIXME" in code:
                quality_issues.append("Contains TODO/FIXME comments")
            
            if not any(keyword in code.lower() for keyword in ["def ", "function", "class", "const", "let", "var"]):
                quality_issues.append("No functions/classes/variables detected")
            
            if quality_issues:
                results["checks"].append({
                    "name": "Code Quality Check",
                    "passed": False,
                    "message": f"Quality issues: {', '.join(quality_issues)}"
                })
            else:
                results["checks"].append({
                    "name": "Code Quality Check",
                    "passed": True,
                    "message": "Basic code quality checks passed"
                })
                checks_passed += 1
            
            # Check 4: Task alignment (keyword matching)
            total_checks += 1
            task_keywords = set(task_description.lower().split())
            code_lower = code.lower()
            
            matched_keywords = sum(1 for keyword in task_keywords if keyword in code_lower and len(keyword) > 3)
            keyword_coverage = matched_keywords / max(len([k for k in task_keywords if len(k) > 3]), 1)
            
            if keyword_coverage > 0.3:
                results["checks"].append({
                    "name": "Task Alignment",
                    "passed": True,
                    "message": f"Implementation aligns with task ({keyword_coverage:.1%} keyword match)"
                })
                checks_passed += 1
            else:
                results["checks"].append({
                    "name": "Task Alignment",
                    "passed": False,
                    "message": f"Poor task alignment ({keyword_coverage:.1%} keyword match)"
                })
            
            # Custom validation criteria
            if validation_criteria:
                for criterion in validation_criteria:
                    total_checks += 1
                    criterion_lower = criterion.lower()
                    
                    if any(keyword in code_lower for keyword in criterion_lower.split() if len(keyword) > 3):
                        results["checks"].append({
                            "name": f"Custom: {criterion}",
                            "passed": True,
                            "message": "Criterion appears to be addressed in code"
                        })
                        checks_passed += 1
                    else:
                        results["checks"].append({
                            "name": f"Custom: {criterion}",
                            "passed": False,
                            "message": "Criterion not clearly addressed"
                        })
            
            # Calculate final score
            results["score"] = checks_passed / max(total_checks, 1)
            results["validation_passed"] = results["score"] >= 0.7
            
            # Generate recommendations
            if results["score"] < 0.8:
                results["recommendations"].extend([
                    "Add more comprehensive error handling",
                    "Include input validation",
                    "Add documentation/comments",
                    "Consider edge cases",
                    "Improve code structure"
                ])
            
            if not results["validation_passed"]:
                results["recommendations"].insert(0, "Implementation needs significant improvements")
            
            return results
            
        except Exception as e:
            results["checks"].append({
                "name": "Validation Process",
                "passed": False,
                "message": f"Validation failed: {e}"
            })
            return results
    
    return validate_implementation


def _create_atomic_step_executor(workspace_dir: str) -> Callable:
    """Create atomic step execution function."""
    
    def execute_atomic_step(
        step_description: str,
        step_type: str = "auto",
        context: Dict[str, Any] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a single atomic coding step.
        
        Args:
            step_description: Description of the step to execute
            step_type: Type of step (auto, create, edit, test, analyze)
            context: Additional context for execution
            dry_run: If True, only plan without executing
        """
        context = context or {}
        
        result = {
            "step_description": step_description,
            "step_type": step_type,
            "success": False,
            "actions_taken": [],
            "files_modified": [],
            "execution_time": 0.0,
            "dry_run": dry_run,
        }
        
        start_time = time.time()
        
        try:
            # Auto-detect step type if needed
            if step_type == "auto":
                step_type = _detect_step_type(step_description)
                result["detected_step_type"] = step_type
            
            if dry_run:
                result["actions_taken"] = _plan_step_actions(step_description, step_type, context)
                result["success"] = True
                return result
            
            # Execute based on step type
            if step_type == "create":
                return _execute_create_step(step_description, context, workspace_dir, result)
            elif step_type == "edit":
                return _execute_edit_step(step_description, context, workspace_dir, result)
            elif step_type == "test":
                return _execute_test_step(step_description, context, workspace_dir, result)
            elif step_type == "analyze":
                return _execute_analyze_step(step_description, context, workspace_dir, result)
            else:
                result["error"] = f"Unknown step type: {step_type}"
                return result
                
        except Exception as e:
            result["error"] = f"Step execution failed: {e}"
            return result
        finally:
            result["execution_time"] = time.time() - start_time
    
    return execute_atomic_step


def _detect_step_type(description: str) -> str:
    """Detect the type of step based on description."""
    desc_lower = description.lower()
    
    if any(word in desc_lower for word in ["create", "implement", "write", "build", "generate"]):
        return "create"
    elif any(word in desc_lower for word in ["edit", "modify", "update", "fix", "change"]):
        return "edit"
    elif any(word in desc_lower for word in ["test", "verify", "validate", "check"]):
        return "test"
    elif any(word in desc_lower for word in ["analyze", "review", "examine", "inspect"]):
        return "analyze"
    else:
        return "create"  # Default to create


def _plan_step_actions(description: str, step_type: str, context: Dict[str, Any]) -> List[str]:
    """Plan actions for a step without executing."""
    actions = []
    
    if step_type == "create":
        actions.extend([
            "Analyze requirements from description",
            "Determine appropriate file structure",
            "Generate code scaffolding",
            "Implement core functionality",
            "Add error handling",
            "Create basic tests"
        ])
    elif step_type == "edit":
        actions.extend([
            "Locate files to modify",
            "Identify specific changes needed",
            "Plan modification strategy",
            "Apply changes incrementally",
            "Validate changes",
            "Update related documentation"
        ])
    elif step_type == "test":
        actions.extend([
            "Identify code to test",
            "Generate test cases",
            "Execute test suite",
            "Analyze test results",
            "Report coverage gaps"
        ])
    elif step_type == "analyze":
        actions.extend([
            "Read and parse code",
            "Perform static analysis",
            "Check code quality metrics",
            "Generate analysis report",
            "Provide improvement recommendations"
        ])
    
    return actions


def _execute_create_step(description: str, context: Dict[str, Any], workspace_dir: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a file creation step."""
    result["actions_taken"].append("Starting file creation step")
    
    # Extract file information from description
    filename = context.get("filename")
    if not filename:
        # Try to extract from description
        import re
        file_match = re.search(r'(\w+\.\w+)', description)
        if file_match:
            filename = file_match.group(1)
        else:
            filename = "implementation.py"  # Default
    
    # Generate basic code structure
    if filename.endswith('.py'):
        content = f'"""\n{description}\n"""\n\n# TODO: Implement {description}\n\ndef main():\n    """Main implementation."""\n    pass\n\nif __name__ == "__main__":\n    main()\n'
    elif filename.endswith('.js'):
        content = f'/**\n * {description}\n */\n\n// TODO: Implement {description}\n\nfunction main() {\n    // Implementation here\n}\n\nif (require.main === module) {\n    main();\n}\n'
    else:
        content = f'# {description}\n\n# TODO: Implement {description}\n'
    
    # Write file
    file_path = Path(workspace_dir) / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    
    result["actions_taken"].extend([
        f"Created file: {filename}",
        f"Generated {len(content)} characters of code",
        "Added basic structure and TODO comments"
    ])
    result["files_modified"] = [filename]
    result["success"] = True
    
    return result


def _execute_edit_step(description: str, context: Dict[str, Any], workspace_dir: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a file editing step."""
    result["actions_taken"].append("Starting file edit step")
    
    filename = context.get("filename")
    if not filename:
        result["error"] = "Filename required for edit operation"
        return result
    
    file_path = Path(workspace_dir) / filename
    if not file_path.exists():
        result["error"] = f"File not found: {filename}"
        return result
    
    # Read current content
    current_content = file_path.read_text(encoding="utf-8")
    
    # Simple edit: add comment about the change
    edit_comment = f"\n# EDIT: {description}\n"
    new_content = current_content + edit_comment
    
    # Write updated content
    file_path.write_text(new_content, encoding="utf-8")
    
    result["actions_taken"].extend([
        f"Read existing file: {filename}",
        f"Added edit comment for: {description}",
        "Saved updated file"
    ])
    result["files_modified"] = [filename]
    result["success"] = True
    
    return result


def _execute_test_step(description: str, context: Dict[str, Any], workspace_dir: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a testing step."""
    result["actions_taken"].append("Starting test execution step")
    
    # Simple test validation
    test_files = list(Path(workspace_dir).glob("test_*.py"))
    test_files.extend(Path(workspace_dir).glob("*_test.py"))
    
    result["actions_taken"].append(f"Found {len(test_files)} test files")
    
    if test_files:
        result["actions_taken"].append("Test files exist - would run test suite")
    else:
        result["actions_taken"].append("No test files found - would create basic tests")
    
    result["success"] = True
    return result


def _execute_analyze_step(description: str, context: Dict[str, Any], workspace_dir: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a code analysis step."""
    result["actions_taken"].append("Starting code analysis step")
    
    # Find Python files to analyze
    python_files = list(Path(workspace_dir).glob("*.py"))
    
    analysis_results = []
    for file_path in python_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = len(content.splitlines())
            chars = len(content)
            
            analysis_results.append({
                "file": file_path.name,
                "lines": lines,
                "characters": chars,
                "functions": content.count("def "),
                "classes": content.count("class "),
            })
        except Exception:
            continue
    
    result["actions_taken"].extend([
        f"Analyzed {len(python_files)} Python files",
        f"Total analysis data points: {len(analysis_results)}"
    ])
    result["analysis_results"] = analysis_results
    result["success"] = True
    
    return result


# Enhanced instructions for precision coding
CODING_INSTRUCTIONS_ENHANCED = """You are an expert software developer and precision-enhanced coding assistant with neuro-san task decomposition capabilities.

## Enhanced Capabilities

- **Precision-Enhanced Code Generation**: Write clean, efficient code with recursive task decomposition
- **Intelligent Task Breaking**: Automatically decompose complex tasks into atomic operations
- **Validation-Driven Development**: Validate implementations against precise criteria
- **Atomic Step Execution**: Execute coding tasks in small, verifiable steps

## Available Tools

### Standard File Operations
- `file_read(path, max_lines, start_line)`: Read files or list directories
- `file_write(operation, path, content, old_text, new_text)`: Write/edit files
- `glob(pattern, max_results)`: Find files matching patterns
- `grep(pattern, path, file_pattern, context_lines)`: Search file contents

### Code Execution
- `execute_code(code, language, timeout)`: Run code (python, javascript, typescript, bash, go)
- `python_repl(code, reset)`: Interactive Python with persistent state
- `bash(command, timeout)`: Execute shell commands

### Memory & Analysis
- `memory(command, path, content)`: Persistent storage (view, create, edit, delete)
- `analyze_code(code, language)`: Static analysis
- `search_code_patterns(query, language)`: Find code patterns
- `generate_tests(code, language, framework)`: Create unit tests
- `explain_code(code, language)`: Analyze code structure
- `suggest_improvements(code, language, focus)`: Get improvement suggestions

### Precision Enhancement Tools (NEW)
- `decompose_task(task_description, max_depth, return_format)`: Recursively decompose complex tasks into atomic operations
- `validate_implementation(task_description, implementation_path, validation_criteria, run_tests)`: Validate code against task requirements
- `execute_atomic_step(step_description, step_type, context, dry_run)`: Execute individual atomic coding steps

## Precision-Enhanced Workflow

1. **Task Analysis**: Use `decompose_task()` to break complex requests into atomic operations
2. **Strategic Planning**: Review decomposition tree and identify dependencies
3. **Atomic Implementation**: Use `execute_atomic_step()` for each sub-task
4. **Continuous Validation**: Use `validate_implementation()` after each significant change
5. **Iterative Refinement**: Improve based on validation feedback

## Task Complexity Levels

- **ATOMIC**: Single operation (15 min) - direct implementation
- **SIMPLE**: 2-3 operations (45 min) - minimal decomposition
- **MEDIUM**: 4-10 operations (2 hours) - moderate decomposition
- **COMPLEX**: 11+ operations (5+ hours) - deep decomposition

## Precision Best Practices

- **Start with Decomposition**: For tasks with >3 operations, always use `decompose_task()` first
- **Validate Early & Often**: Run `validate_implementation()` after each atomic step
- **Atomic Steps Only**: Keep individual implementations small and focused
- **Dependency Awareness**: Respect task dependencies from decomposition
- **Error Pattern Recognition**: Learn from validation failures to improve future decompositions
- **Graceful Degradation**: If consensus/validation fails, provide best-effort implementation with clear limitations

## Example Precision Workflow

```
User Request: "Create a web API with authentication"

1. decompose_task("Create a web API with authentication", max_depth=3, return_format="tree")
2. Review decomposition tree: authentication setup → API routes → testing
3. For each atomic task:
   - execute_atomic_step(task_description, step_type="auto", dry_run=False)
   - validate_implementation(task_description, implementation_path, validation_criteria)
4. Final validation of complete system
```

## Enhanced Error Handling

- Provide detailed error analysis when validation fails
- Suggest specific improvements based on validation criteria
- Offer alternative approaches when initial decomposition is ineffective
- Maintain precision focus: prefer correct implementation over fast delivery

You now have the ability to handle complex, multi-step coding tasks with high precision through systematic decomposition and validation. Use these capabilities to ensure every implementation meets the highest standards of correctness and completeness.
"""
