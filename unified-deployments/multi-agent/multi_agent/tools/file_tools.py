"""
File operation tools for reading, writing, and searching files.

Adapted from claude-quickstarts/agents/tools/file_tools.py for use with
VLLM's OpenAI-compatible API.
"""

import asyncio
import glob
import os
import re
from pathlib import Path
from typing import List, Optional

from .base import Tool


class FileReadTool(Tool):
    """Tool for reading files and listing directories."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize the file read tool.
        
        Args:
            workspace_dir: Optional workspace directory to restrict operations to
        """
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else None
        
        super().__init__(
            name="file_read",
            description="""Read the contents of a file or list directory contents.
            
Use this tool to:
- Read source code files
- View configuration files
- List files in a directory
- Check file contents before editing""",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read or directory path to list",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum lines to read (0 = no limit, default: 0)",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Line number to start reading from (1-indexed, default: 1)",
                    },
                },
                "required": ["path"],
            },
        )
    
    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path, ensuring it's within workspace if set."""
        resolved = Path(path).resolve()
        
        if self.workspace_dir:
            try:
                resolved.relative_to(self.workspace_dir)
            except ValueError:
                raise ValueError(f"Path '{path}' is outside workspace directory")
        
        return resolved
    
    async def execute(
        self,
        path: str,
        max_lines: int = 0,
        start_line: int = 1,
    ) -> str:
        """
        Read a file or list directory contents.
        
        Args:
            path: File or directory path
            max_lines: Maximum lines to read (0 = no limit)
            start_line: Line number to start from (1-indexed)
        """
        try:
            file_path = self._validate_path(path)
        except ValueError as e:
            return f"Error: {e}"
        
        if not file_path.exists():
            return f"Error: Path not found: {path}"
        
        if file_path.is_dir():
            return await self._list_directory(file_path)
        else:
            return await self._read_file(file_path, max_lines, start_line)
    
    async def _read_file(
        self,
        file_path: Path,
        max_lines: int,
        start_line: int,
    ) -> str:
        """Read file contents with optional line range."""
        def read_sync():
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                
                # Apply line range
                start_idx = max(0, start_line - 1)
                if max_lines > 0:
                    end_idx = start_idx + max_lines
                    lines = lines[start_idx:end_idx]
                else:
                    lines = lines[start_idx:]
                
                # Format with line numbers
                numbered = []
                for i, line in enumerate(lines, start=start_idx + 1):
                    numbered.append(f"{i:4d}: {line.rstrip()}")
                
                return "\n".join(numbered)
                
            except UnicodeDecodeError:
                return f"Error: {file_path} appears to be a binary file"
            except Exception as e:
                return f"Error reading {file_path}: {e}"
        
        return await asyncio.to_thread(read_sync)
    
    async def _list_directory(self, dir_path: Path) -> str:
        """List directory contents."""
        def list_sync():
            try:
                items = []
                for item in sorted(dir_path.iterdir()):
                    if item.name.startswith("."):
                        continue
                    prefix = "📁 " if item.is_dir() else "📄 "
                    items.append(f"{prefix}{item.name}")
                
                if not items:
                    return f"Directory {dir_path} is empty"
                
                return f"Contents of {dir_path}:\n" + "\n".join(items)
                
            except Exception as e:
                return f"Error listing {dir_path}: {e}"
        
        return await asyncio.to_thread(list_sync)


class FileWriteTool(Tool):
    """Tool for writing and editing files."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize the file write tool.
        
        Args:
            workspace_dir: Optional workspace directory to restrict operations to
        """
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else None
        
        super().__init__(
            name="file_write",
            description="""Write content to a file or edit existing files.
            
Operations:
- write: Create or completely replace a file
- edit: Make targeted changes using search/replace
- append: Add content to the end of a file
- insert: Insert content at a specific line""",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["write", "edit", "append", "insert"],
                        "description": "File operation to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path to write to or edit",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write/append operations)",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to find and replace (for edit operation)",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text (for edit operation)",
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "Line number for insert operation (1-indexed)",
                    },
                },
                "required": ["operation", "path"],
            },
        )
    
    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path."""
        resolved = Path(path).resolve()
        
        if self.workspace_dir:
            try:
                resolved.relative_to(self.workspace_dir)
            except ValueError:
                raise ValueError(f"Path '{path}' is outside workspace directory")
        
        return resolved
    
    async def execute(
        self,
        operation: str,
        path: str,
        content: str = "",
        old_text: str = "",
        new_text: str = "",
        line_number: int = 0,
    ) -> str:
        """Execute a file write operation."""
        try:
            file_path = self._validate_path(path)
        except ValueError as e:
            return f"Error: {e}"
        
        if operation == "write":
            return await self._write_file(file_path, content)
        elif operation == "edit":
            return await self._edit_file(file_path, old_text, new_text)
        elif operation == "append":
            return await self._append_file(file_path, content)
        elif operation == "insert":
            return await self._insert_line(file_path, line_number, content)
        else:
            return f"Error: Unknown operation '{operation}'"
    
    async def _write_file(self, file_path: Path, content: str) -> str:
        """Write content to a file, creating directories as needed."""
        def write_sync():
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                return f"Successfully wrote {len(content)} characters to {file_path}"
            except Exception as e:
                return f"Error writing to {file_path}: {e}"
        
        return await asyncio.to_thread(write_sync)
    
    async def _edit_file(self, file_path: Path, old_text: str, new_text: str) -> str:
        """Edit a file by replacing text."""
        if not old_text:
            return "Error: old_text is required for edit operation"
        
        def edit_sync():
            try:
                if not file_path.exists():
                    return f"Error: File not found: {file_path}"
                
                content = file_path.read_text(encoding="utf-8")
                
                count = content.count(old_text)
                if count == 0:
                    return f"Error: Text not found in {file_path}"
                elif count > 1:
                    return f"Warning: Found {count} occurrences. All replaced in {file_path}"
                
                new_content = content.replace(old_text, new_text)
                file_path.write_text(new_content, encoding="utf-8")
                return f"Successfully edited {file_path}"
                
            except Exception as e:
                return f"Error editing {file_path}: {e}"
        
        return await asyncio.to_thread(edit_sync)
    
    async def _append_file(self, file_path: Path, content: str) -> str:
        """Append content to a file."""
        def append_sync():
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully appended {len(content)} characters to {file_path}"
            except Exception as e:
                return f"Error appending to {file_path}: {e}"
        
        return await asyncio.to_thread(append_sync)
    
    async def _insert_line(self, file_path: Path, line_number: int, content: str) -> str:
        """Insert content at a specific line."""
        def insert_sync():
            try:
                if not file_path.exists():
                    return f"Error: File not found: {file_path}"
                
                lines = file_path.read_text(encoding="utf-8").splitlines()
                
                # Validate line number
                if line_number < 1 or line_number > len(lines) + 1:
                    return f"Error: Invalid line number {line_number}. File has {len(lines)} lines."
                
                # Insert at the specified line (1-indexed)
                lines.insert(line_number - 1, content.rstrip("\n"))
                
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return f"Successfully inserted content at line {line_number} in {file_path}"
                
            except Exception as e:
                return f"Error inserting into {file_path}: {e}"
        
        return await asyncio.to_thread(insert_sync)


class GlobTool(Tool):
    """Tool for finding files using glob patterns."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd()
        
        super().__init__(
            name="glob",
            description="""Find files matching a glob pattern.
            
Examples:
- "*.py" - All Python files in current directory
- "**/*.py" - All Python files recursively
- "src/**/*.ts" - All TypeScript files in src/""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)",
                    },
                },
                "required": ["pattern"],
            },
        )
    
    async def execute(self, pattern: str, max_results: int = 100) -> str:
        """Find files matching the glob pattern."""
        def glob_sync():
            try:
                search_path = self.workspace_dir / pattern
                matches = list(glob.glob(str(search_path), recursive=True))
                
                if not matches:
                    return f"No files found matching pattern: {pattern}"
                
                # Limit results
                if len(matches) > max_results:
                    matches = matches[:max_results]
                    truncated = True
                else:
                    truncated = False
                
                # Format results
                results = []
                for match in sorted(matches):
                    path = Path(match)
                    try:
                        rel_path = path.relative_to(self.workspace_dir)
                    except ValueError:
                        rel_path = path
                    
                    prefix = "📁 " if path.is_dir() else "📄 "
                    results.append(f"{prefix}{rel_path}")
                
                output = "\n".join(results)
                if truncated:
                    output += f"\n\n(Showing first {max_results} results)"
                
                return output
                
            except Exception as e:
                return f"Error searching for {pattern}: {e}"
        
        return await asyncio.to_thread(glob_sync)


class GrepTool(Tool):
    """Tool for searching file contents using regex patterns."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd()
        
        super().__init__(
            name="grep",
            description="""Search for text patterns in files.
            
Searches file contents using regular expressions and returns matching lines
with context.""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search (default: current directory)",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern for files to search (default: **/*)",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines before/after match (default: 2)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matches (default: 50)",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search (default: false)",
                    },
                },
                "required": ["pattern"],
            },
        )
    
    async def execute(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "**/*",
        context_lines: int = 2,
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> str:
        """Search for pattern in files."""
        def grep_sync():
            try:
                # Compile regex
                flags = 0 if case_sensitive else re.IGNORECASE
                try:
                    regex = re.compile(pattern, flags)
                except re.error as e:
                    return f"Error: Invalid regex pattern: {e}"
                
                # Find files to search
                search_dir = self.workspace_dir / path
                if search_dir.is_file():
                    files = [search_dir]
                else:
                    files = list(glob.glob(str(search_dir / file_pattern), recursive=True))
                    files = [Path(f) for f in files if Path(f).is_file()]
                
                results = []
                total_matches = 0
                
                for file_path in files:
                    if total_matches >= max_results:
                        break
                    
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        lines = content.splitlines()
                        
                        for i, line in enumerate(lines):
                            if total_matches >= max_results:
                                break
                            
                            if regex.search(line):
                                total_matches += 1
                                
                                # Get context
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                
                                try:
                                    rel_path = file_path.relative_to(self.workspace_dir)
                                except ValueError:
                                    rel_path = file_path
                                
                                result = f"\n{rel_path}:{i + 1}:\n"
                                for j in range(start, end):
                                    prefix = ">>> " if j == i else "    "
                                    result += f"{prefix}{j + 1}: {lines[j]}\n"
                                
                                results.append(result)
                                
                    except Exception:
                        continue
                
                if not results:
                    return f"No matches found for pattern: {pattern}"
                
                output = f"Found {total_matches} matches:\n" + "\n".join(results)
                if total_matches >= max_results:
                    output += f"\n\n(Showing first {max_results} matches)"
                
                return output
                
            except Exception as e:
                return f"Error searching: {e}"
        
        return await asyncio.to_thread(grep_sync)
