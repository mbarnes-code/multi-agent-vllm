"""
Coding Agent for the multi-agent system.

Specialized agent for code generation, debugging, testing, and code review.
Based on patterns from:
- claude-quickstarts/autonomous-coding
- claude-quickstarts/agents
- claude-plugins-official/plugins/code-review
- claude-plugins-official/plugins/feature-dev
- claude-cookbooks/tool_use
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..core import Agent


def create_coding_agent(
    model: str,
    enable_execution: bool = True,
    enable_bash: bool = True,
    workspace_dir: str = "/tmp/workspace",
    memory_dir: str = "/tmp/memory",
) -> Agent:
    """
    Create a coding agent with comprehensive code tools.
    
    Args:
        model: The model to use for the agent
        enable_execution: Whether to enable code execution (default: True)
        enable_bash: Whether to enable bash commands (default: True)
        workspace_dir: Directory for file operations (default: /tmp/workspace)
        memory_dir: Directory for memory storage (default: /tmp/memory)
        
    Returns:
        Configured Agent for coding tasks
    """
    # Create workspace directory
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    
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
    
    return Agent(
        name="Coding Agent",
        model=model,
        instructions=CODING_INSTRUCTIONS,
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
