"""
Memory tool for persistent storage and retrieval.

Adapted from claude-cookbooks/tool_use/memory_tool.py for use with
the local VLLM-based multi-agent system.

Provides secure file-based memory operations with path validation
and comprehensive error handling.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import Tool


class MemoryTool(Tool):
    """
    Tool for managing persistent memory storage.
    
    Provides file-based memory operations including:
    - View: Read files or list directories
    - Create: Create new files
    - Edit: Modify existing files (str_replace, insert)
    - Delete: Remove files or directories
    - Rename: Move or rename files
    
    All operations are confined to a designated memory directory
    with path validation to prevent directory traversal attacks.
    """
    
    def __init__(
        self,
        base_path: str = "./memory_storage",
        memory_prefix: str = "/memories",
    ):
        """
        Initialize the memory tool.
        
        Args:
            base_path: Root directory for memory storage
            memory_prefix: Virtual path prefix for memory operations
        """
        self.base_path = Path(base_path).resolve()
        self.memory_prefix = memory_prefix
        self.memory_root = self.base_path / "memories"
        self.memory_root.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            name="memory",
            description=f"""Manage persistent memory storage.

Operations:
- view: Read file contents or list directory
- create: Create a new file
- str_replace: Replace text in a file
- insert: Insert text at a specific line
- delete: Delete a file or directory
- rename: Rename or move a file/directory

All paths must start with '{memory_prefix}' and are confined to the memory directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "create", "str_replace", "insert", "delete", "rename"],
                        "description": "Memory operation to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": f"Path starting with {memory_prefix}",
                    },
                    "file_text": {
                        "type": "string",
                        "description": "Content for create operation",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Text to replace (for str_replace)",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement text (for str_replace)",
                    },
                    "insert_line": {
                        "type": "integer",
                        "description": "Line number for insert (0-indexed)",
                    },
                    "insert_text": {
                        "type": "string",
                        "description": "Text to insert",
                    },
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Line range [start, end] for view (1-indexed, -1 for end)",
                    },
                    "old_path": {
                        "type": "string",
                        "description": "Source path for rename",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "Destination path for rename",
                    },
                },
                "required": ["command"],
            },
        )
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve memory paths.
        
        Args:
            path: Path to validate (must start with memory_prefix)
            
        Returns:
            Resolved absolute Path within memory_root
            
        Raises:
            ValueError: If path is invalid or escapes memory directory
        """
        if not path.startswith(self.memory_prefix):
            raise ValueError(
                f"Path must start with {self.memory_prefix}, got: {path}"
            )
        
        # Remove prefix and resolve
        relative_path = path[len(self.memory_prefix):].lstrip("/")
        
        if relative_path:
            full_path = (self.memory_root / relative_path).resolve()
        else:
            full_path = self.memory_root.resolve()
        
        # Verify path is within memory_root
        try:
            full_path.relative_to(self.memory_root.resolve())
        except ValueError:
            raise ValueError(
                f"Path '{path}' would escape memory directory. "
                "Directory traversal is not allowed."
            )
        
        return full_path
    
    async def execute(self, **params: Any) -> str:
        """Execute a memory operation."""
        command = params.get("command")
        
        try:
            if command == "view":
                return self._view(params)
            elif command == "create":
                return self._create(params)
            elif command == "str_replace":
                return self._str_replace(params)
            elif command == "insert":
                return self._insert(params)
            elif command == "delete":
                return self._delete(params)
            elif command == "rename":
                return self._rename(params)
            else:
                return f"Error: Unknown command '{command}'. Valid: view, create, str_replace, insert, delete, rename"
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error executing {command}: {e}"
    
    def _view(self, params: Dict[str, Any]) -> str:
        """View file contents or list directory."""
        path = params.get("path")
        view_range = params.get("view_range")
        
        if not path:
            return "Error: Missing required parameter: path"
        
        full_path = self._validate_path(path)
        
        # Directory listing
        if full_path.is_dir():
            try:
                items = []
                for item in sorted(full_path.iterdir()):
                    if item.name.startswith("."):
                        continue
                    suffix = "/" if item.is_dir() else ""
                    items.append(f"- {item.name}{suffix}")
                
                if not items:
                    return f"Directory: {path}\n(empty)"
                
                return f"Directory: {path}\n" + "\n".join(items)
            except Exception as e:
                return f"Error reading directory {path}: {e}"
        
        # File reading
        elif full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                
                # Apply view range
                if view_range:
                    start = max(1, view_range[0]) - 1
                    end = len(lines) if view_range[1] == -1 else view_range[1]
                    lines = lines[start:end]
                    start_num = start + 1
                else:
                    start_num = 1
                
                # Format with line numbers
                numbered = [f"{i + start_num:4d}: {line}" for i, line in enumerate(lines)]
                return "\n".join(numbered)
                
            except UnicodeDecodeError:
                return f"Error: {path} is not valid UTF-8 text"
            except Exception as e:
                return f"Error reading {path}: {e}"
        
        else:
            return f"Error: Path not found: {path}"
    
    def _create(self, params: Dict[str, Any]) -> str:
        """Create a new file."""
        path = params.get("path")
        file_text = params.get("file_text", "")
        
        if not path:
            return "Error: Missing required parameter: path"
        
        full_path = self._validate_path(path)
        
        # Validate file extension
        valid_extensions = {".txt", ".md", ".json", ".py", ".yaml", ".yml", ".toml", ".xml", ".csv"}
        if full_path.suffix.lower() not in valid_extensions:
            return f"Error: Only text files are supported. Valid extensions: {valid_extensions}"
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(file_text, encoding="utf-8")
            return f"File created successfully at {path}"
        except Exception as e:
            return f"Error creating {path}: {e}"
    
    def _str_replace(self, params: Dict[str, Any]) -> str:
        """Replace text in a file."""
        path = params.get("path")
        old_str = params.get("old_str")
        new_str = params.get("new_str", "")
        
        if not path or old_str is None:
            return "Error: Missing required parameters: path, old_str"
        
        full_path = self._validate_path(path)
        
        if not full_path.is_file():
            return f"Error: File not found: {path}"
        
        try:
            content = full_path.read_text(encoding="utf-8")
            
            count = content.count(old_str)
            if count == 0:
                return f"Error: String not found in {path}"
            elif count > 1:
                return f"Error: String appears {count} times. Use more specific context."
            
            new_content = content.replace(old_str, new_str, 1)
            full_path.write_text(new_content, encoding="utf-8")
            
            return f"File {path} edited successfully"
        except Exception as e:
            return f"Error editing {path}: {e}"
    
    def _insert(self, params: Dict[str, Any]) -> str:
        """Insert text at a specific line."""
        path = params.get("path")
        insert_line = params.get("insert_line")
        insert_text = params.get("insert_text", "")
        
        if not path or insert_line is None:
            return "Error: Missing required parameters: path, insert_line"
        
        full_path = self._validate_path(path)
        
        if not full_path.is_file():
            return f"Error: File not found: {path}"
        
        try:
            lines = full_path.read_text(encoding="utf-8").splitlines()
            
            if insert_line < 0 or insert_line > len(lines):
                return f"Error: Invalid line {insert_line}. Must be 0-{len(lines)}"
            
            lines.insert(insert_line, insert_text.rstrip("\n"))
            full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            
            return f"Text inserted at line {insert_line} in {path}"
        except Exception as e:
            return f"Error inserting into {path}: {e}"
    
    def _delete(self, params: Dict[str, Any]) -> str:
        """Delete a file or directory."""
        path = params.get("path")
        
        if not path:
            return "Error: Missing required parameter: path"
        
        if path == self.memory_prefix:
            return f"Error: Cannot delete the {self.memory_prefix} directory itself"
        
        full_path = self._validate_path(path)
        
        if not full_path.exists():
            return f"Error: Path not found: {path}"
        
        try:
            if full_path.is_file():
                full_path.unlink()
                return f"File deleted: {path}"
            elif full_path.is_dir():
                shutil.rmtree(full_path)
                return f"Directory deleted: {path}"
        except Exception as e:
            return f"Error deleting {path}: {e}"
    
    def _rename(self, params: Dict[str, Any]) -> str:
        """Rename or move a file/directory."""
        old_path = params.get("old_path")
        new_path = params.get("new_path")
        
        if not old_path or not new_path:
            return "Error: Missing required parameters: old_path, new_path"
        
        old_full = self._validate_path(old_path)
        new_full = self._validate_path(new_path)
        
        if not old_full.exists():
            return f"Error: Source not found: {old_path}"
        
        if new_full.exists():
            return f"Error: Destination exists: {new_path}"
        
        try:
            new_full.parent.mkdir(parents=True, exist_ok=True)
            old_full.rename(new_full)
            return f"Renamed {old_path} to {new_path}"
        except Exception as e:
            return f"Error renaming: {e}"
    
    def clear_all(self) -> str:
        """Clear all memory (for testing/reset)."""
        try:
            if self.memory_root.exists():
                shutil.rmtree(self.memory_root)
            self.memory_root.mkdir(parents=True, exist_ok=True)
            return "All memory cleared"
        except Exception as e:
            return f"Error clearing memory: {e}"
    
    def list_all(self) -> List[str]:
        """List all files in memory."""
        files = []
        for path in self.memory_root.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(self.memory_root)
                files.append(f"{self.memory_prefix}/{rel_path}")
        return sorted(files)
