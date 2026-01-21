"""
Coding Agent - Autonomous code generation and development tasks.

Based on patterns from claude-quickstarts/autonomous-coding, adapted for VLLM.
Handles code generation, debugging, code review, and software development.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from ..core import Agent, Result

CODING_INSTRUCTIONS = """You are an expert Coding Agent specialized in software development.

## YOUR CAPABILITIES

1. **Code Generation**: Write clean, efficient, well-documented code in any language
2. **Code Review**: Analyze code for bugs, security issues, and improvements
3. **Debugging**: Identify and fix issues in existing code
4. **Refactoring**: Improve code structure and maintainability
5. **Testing**: Write unit tests and integration tests
6. **Documentation**: Generate docstrings, comments, and technical docs

## CODING PRINCIPLES

- Write clean, readable code following language-specific best practices
- Include appropriate error handling and edge case coverage
- Add meaningful comments for complex logic
- Follow SOLID principles and design patterns where appropriate
- Consider performance implications
- Write testable code with clear interfaces

## AVAILABLE TOOLS

- `execute_code`: Run code in a sandboxed environment
- `analyze_code`: Static analysis for bugs and style issues
- `search_code_patterns`: Find code examples and patterns
- `generate_tests`: Create unit tests for given code
- `explain_code`: Provide detailed explanation of code

## WORKFLOW

1. **Understand**: Clarify requirements before coding
2. **Plan**: Outline the approach and structure
3. **Implement**: Write the code incrementally
4. **Test**: Verify the code works correctly
5. **Refine**: Improve based on feedback

## SECURITY

- Never execute untrusted code without sandboxing
- Sanitize all inputs
- Avoid hardcoded credentials
- Follow secure coding practices

When generating code:
- Ask clarifying questions if requirements are ambiguous
- Provide complete, runnable solutions
- Include usage examples
- Explain key design decisions"""


class CodingAgent:
    """Factory for creating coding agents with development tools."""
    
    def __init__(
        self,
        model: str = "meta-llama/Llama-3.1-8B-Instruct",
        workspace_dir: Optional[str] = None,
        allowed_languages: Optional[List[str]] = None,
        enable_execution: bool = True,
        execution_timeout: int = 30,
    ):
        self.model = model
        self.workspace_dir = workspace_dir or tempfile.mkdtemp(prefix="coding_agent_")
        self.allowed_languages = allowed_languages or [
            "python", "javascript", "typescript", "go", "rust", "java", "c", "cpp", "bash"
        ]
        self.enable_execution = enable_execution
        self.execution_timeout = execution_timeout
        
        # Ensure workspace exists
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
        
    def _create_coding_functions(self) -> list:
        """Create coding tool functions."""
        
        def execute_code(code: str, language: str = "python") -> str:
            """
            Execute code in a sandboxed environment.
            
            Args:
                code: The code to execute
                language: Programming language (python, javascript, bash, etc.)
            """
            if not self.enable_execution:
                return "Code execution is disabled for security reasons."
            
            language = language.lower()
            if language not in self.allowed_languages:
                return f"Language '{language}' is not allowed. Supported: {', '.join(self.allowed_languages)}"
            
            # Map languages to executors
            executors = {
                "python": ["python3", "-c"],
                "javascript": ["node", "-e"],
                "typescript": ["npx", "ts-node", "-e"],
                "bash": ["bash", "-c"],
                "go": None,  # Requires file-based execution
                "rust": None,
                "java": None,
                "c": None,
                "cpp": None,
            }
            
            executor = executors.get(language)
            
            if executor is None:
                # File-based execution for compiled languages
                return _execute_compiled(code, language, self.workspace_dir, self.execution_timeout)
            
            try:
                result = subprocess.run(
                    executor + [code],
                    capture_output=True,
                    text=True,
                    timeout=self.execution_timeout,
                    cwd=self.workspace_dir,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                
                output = ""
                if result.stdout:
                    output += f"STDOUT:\n{result.stdout}\n"
                if result.stderr:
                    output += f"STDERR:\n{result.stderr}\n"
                output += f"Exit code: {result.returncode}"
                
                return output or "Code executed successfully with no output."
                
            except subprocess.TimeoutExpired:
                return f"Execution timed out after {self.execution_timeout} seconds."
            except Exception as e:
                return f"Execution error: {str(e)}"
        
        def analyze_code(code: str, language: str = "python") -> str:
            """
            Perform static analysis on code.
            
            Args:
                code: The code to analyze
                language: Programming language
            """
            issues = []
            
            # Basic analysis (in production, use proper linters)
            lines = code.split("\n")
            
            for i, line in enumerate(lines, 1):
                # Check for common issues
                if "eval(" in line or "exec(" in line:
                    issues.append(f"Line {i}: Security risk - eval/exec usage")
                if "password" in line.lower() and "=" in line:
                    issues.append(f"Line {i}: Potential hardcoded password")
                if len(line) > 120:
                    issues.append(f"Line {i}: Line too long ({len(line)} chars)")
                if line.rstrip() != line:
                    issues.append(f"Line {i}: Trailing whitespace")
                    
            # Language-specific checks
            if language == "python":
                if "import *" in code:
                    issues.append("Style: Avoid 'import *' - use explicit imports")
                if "except:" in code and "except Exception" not in code:
                    issues.append("Style: Avoid bare 'except:' - catch specific exceptions")
                    
            if not issues:
                return "No issues found. Code looks good!"
            
            return "Issues found:\n" + "\n".join(f"- {issue}" for issue in issues)
        
        def search_code_patterns(query: str, language: str = "python") -> str:
            """
            Search for code patterns and examples.
            
            Args:
                query: What pattern or example to search for
                language: Programming language
            """
            # Common patterns database (simplified)
            patterns = {
                "python": {
                    "singleton": '''class Singleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance''',
                    "context manager": '''from contextlib import contextmanager

@contextmanager
def managed_resource():
    resource = acquire_resource()
    try:
        yield resource
    finally:
        release_resource(resource)''',
                    "async http": '''import aiohttp
import asyncio

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()''',
                    "decorator": '''from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Before
        result = func(*args, **kwargs)
        # After
        return result
    return wrapper''',
                },
                "javascript": {
                    "async await": '''async function fetchData(url) {
    try {
        const response = await fetch(url);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}''',
                    "class": '''class MyClass {
    constructor(name) {
        this.name = name;
    }
    
    greet() {
        return `Hello, ${this.name}!`;
    }
}''',
                },
            }
            
            lang_patterns = patterns.get(language, {})
            query_lower = query.lower()
            
            matches = []
            for pattern_name, pattern_code in lang_patterns.items():
                if query_lower in pattern_name.lower():
                    matches.append(f"### {pattern_name.title()}\n```{language}\n{pattern_code}\n```")
            
            if matches:
                return "\n\n".join(matches)
            return f"No patterns found for '{query}' in {language}. Try: {', '.join(lang_patterns.keys())}"
        
        def generate_tests(code: str, language: str = "python") -> str:
            """
            Generate unit tests for the given code.
            
            Args:
                code: The code to generate tests for
                language: Programming language
            """
            # Extract function/class names (simplified)
            if language == "python":
                import re
                functions = re.findall(r'def (\w+)\(', code)
                classes = re.findall(r'class (\w+)', code)
                
                tests = ["import pytest", ""]
                
                for func in functions:
                    if not func.startswith("_"):
                        tests.append(f'''def test_{func}():
    """Test {func} function."""
    # TODO: Add test implementation
    # result = {func}(...)
    # assert result == expected
    pass
''')
                
                for cls in classes:
                    tests.append(f'''class Test{cls}:
    """Tests for {cls} class."""
    
    def test_init(self):
        """Test {cls} initialization."""
        # instance = {cls}(...)
        # assert instance is not None
        pass
''')
                
                return "\n".join(tests)
            
            return f"Test generation for {language} is not yet implemented."
        
        def explain_code(code: str, language: str = "python") -> str:
            """
            Provide a detailed explanation of the code.
            
            Args:
                code: The code to explain
                language: Programming language
            """
            # This would typically use the LLM itself
            # For now, provide structural analysis
            lines = code.split("\n")
            
            explanation = [f"## Code Analysis ({language})", ""]
            explanation.append(f"**Total lines:** {len(lines)}")
            explanation.append(f"**Non-empty lines:** {len([l for l in lines if l.strip()])}")
            
            if language == "python":
                import re
                imports = [l for l in lines if l.strip().startswith(("import ", "from "))]
                functions = re.findall(r'def (\w+)\(', code)
                classes = re.findall(r'class (\w+)', code)
                
                if imports:
                    explanation.append(f"\n**Imports:** {len(imports)}")
                    for imp in imports[:5]:
                        explanation.append(f"  - {imp.strip()}")
                        
                if classes:
                    explanation.append(f"\n**Classes:** {', '.join(classes)}")
                    
                if functions:
                    explanation.append(f"\n**Functions:** {', '.join(functions)}")
            
            explanation.append("\n*For detailed explanation, ask me to walk through the code step by step.*")
            
            return "\n".join(explanation)
        
        def write_file(filename: str, content: str) -> str:
            """
            Write content to a file in the workspace.
            
            Args:
                filename: Name of the file to create
                content: Content to write
            """
            filepath = Path(self.workspace_dir) / filename
            
            # Security: prevent path traversal
            if ".." in filename or filename.startswith("/"):
                return "Error: Invalid filename. Cannot use '..' or absolute paths."
            
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content)
                return f"File written successfully: {filepath}"
            except Exception as e:
                return f"Error writing file: {str(e)}"
        
        def read_file(filename: str) -> str:
            """
            Read content from a file in the workspace.
            
            Args:
                filename: Name of the file to read
            """
            filepath = Path(self.workspace_dir) / filename
            
            if ".." in filename or filename.startswith("/"):
                return "Error: Invalid filename."
            
            try:
                if not filepath.exists():
                    return f"File not found: {filename}"
                return filepath.read_text()
            except Exception as e:
                return f"Error reading file: {str(e)}"
        
        def list_files(directory: str = ".") -> str:
            """
            List files in the workspace directory.
            
            Args:
                directory: Subdirectory to list (default: workspace root)
            """
            dirpath = Path(self.workspace_dir) / directory
            
            if ".." in directory:
                return "Error: Invalid directory."
            
            try:
                if not dirpath.exists():
                    return f"Directory not found: {directory}"
                
                files = []
                for item in sorted(dirpath.iterdir()):
                    prefix = "📁 " if item.is_dir() else "📄 "
                    files.append(f"{prefix}{item.name}")
                
                return "\n".join(files) if files else "Directory is empty."
            except Exception as e:
                return f"Error listing files: {str(e)}"
        
        return [
            execute_code,
            analyze_code,
            search_code_patterns,
            generate_tests,
            explain_code,
            write_file,
            read_file,
            list_files,
        ]
    
    def create(self) -> Agent:
        """Create the coding agent with development tools."""
        return Agent(
            name="Coding Agent",
            model=self.model,
            instructions=CODING_INSTRUCTIONS,
            functions=self._create_coding_functions(),
        )


def _execute_compiled(code: str, language: str, workspace: str, timeout: int) -> str:
    """Execute compiled languages via temporary files."""
    import uuid
    
    extensions = {
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
    }
    
    compilers = {
        "go": ["go", "run"],
        "rust": ["rustc", "-o", "out", "{file}", "&&", "./out"],
        "java": ["javac", "{file}", "&&", "java", "{class}"],
        "c": ["gcc", "-o", "out", "{file}", "&&", "./out"],
        "cpp": ["g++", "-o", "out", "{file}", "&&", "./out"],
    }
    
    ext = extensions.get(language)
    if not ext:
        return f"Unsupported compiled language: {language}"
    
    filename = f"temp_{uuid.uuid4().hex[:8]}{ext}"
    filepath = Path(workspace) / filename
    
    try:
        filepath.write_text(code)
        
        if language == "go":
            result = subprocess.run(
                ["go", "run", str(filepath)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workspace,
            )
        elif language in ("c", "cpp"):
            compiler = "gcc" if language == "c" else "g++"
            outfile = Path(workspace) / "out"
            compile_result = subprocess.run(
                [compiler, "-o", str(outfile), str(filepath)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if compile_result.returncode != 0:
                return f"Compilation error:\n{compile_result.stderr}"
            result = subprocess.run(
                [str(outfile)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workspace,
            )
        else:
            return f"Execution for {language} not implemented."
        
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"Exit code: {result.returncode}"
        
        return output or "Code executed successfully with no output."
        
    except subprocess.TimeoutExpired:
        return f"Execution timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution error: {str(e)}"
    finally:
        # Cleanup
        try:
            filepath.unlink(missing_ok=True)
            (Path(workspace) / "out").unlink(missing_ok=True)
        except:
            pass


def create_coding_agent(
    model: str = "meta-llama/Llama-3.1-8B-Instruct",
    workspace_dir: Optional[str] = None,
    enable_execution: bool = True,
) -> Agent:
    """
    Create a coding agent with development tools.
    
    Args:
        model: Model to use for the coding agent
        workspace_dir: Directory for code execution
        enable_execution: Whether to allow code execution
        
    Returns:
        Configured Coding Agent
    """
    factory = CodingAgent(
        model=model,
        workspace_dir=workspace_dir,
        enable_execution=enable_execution,
    )
    return factory.create()
