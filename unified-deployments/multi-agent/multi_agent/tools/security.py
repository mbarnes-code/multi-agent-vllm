"""
Security validation for code execution and bash commands.

Adapted from claude-quickstarts/autonomous-coding/security.py for use with
the local VLLM-based multi-agent system.

Provides an allowlist-based approach to command validation with additional
checks for sensitive operations.
"""

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# Default allowed commands for development tasks
ALLOWED_COMMANDS: Set[str] = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find", "file", "stat",
    # File operations
    "cp", "mv", "mkdir", "touch", "chmod", "rm",
    # Directory navigation
    "pwd", "cd",
    # Text processing
    "sed", "awk", "sort", "uniq", "cut", "tr", "diff",
    # Development tools
    "python", "python3", "pip", "pip3",
    "node", "npm", "npx", "yarn", "pnpm",
    "go", "cargo", "rustc",
    "java", "javac", "mvn", "gradle",
    "gcc", "g++", "make", "cmake",
    # Version control
    "git",
    # Process management
    "ps", "lsof", "sleep", "pkill", "kill",
    # Network (limited)
    "curl", "wget",
    # Archive
    "tar", "zip", "unzip", "gzip", "gunzip",
    # Misc
    "echo", "printf", "date", "env", "which", "whoami",
    "true", "false", "test", "[",
}

# Commands that need additional validation
COMMANDS_NEEDING_VALIDATION: Set[str] = {
    "pkill", "kill", "chmod", "rm", "curl", "wget",
}

# Dangerous patterns to block
DANGEROUS_PATTERNS: List[str] = [
    r"rm\s+-rf\s+/",  # rm -rf /
    r"rm\s+-rf\s+~",  # rm -rf ~
    r">\s*/dev/sd",   # Writing to disk devices
    r"mkfs\.",        # Formatting filesystems
    r"dd\s+if=",      # dd command
    r":\(\)\{",       # Fork bomb
    r"chmod\s+777",   # Overly permissive chmod
    r"curl.*\|\s*sh", # Piping curl to shell
    r"wget.*\|\s*sh", # Piping wget to shell
]


@dataclass
class ValidationResult:
    """Result of command validation."""
    allowed: bool
    reason: str = ""
    warnings: List[str] = field(default_factory=list)


class SecurityValidator:
    """
    Validates bash commands against security policies.
    
    Uses an allowlist approach where only explicitly permitted commands
    can be executed, with additional validation for sensitive operations.
    """
    
    def __init__(
        self,
        allowed_commands: Optional[Set[str]] = None,
        workspace_dir: Optional[str] = None,
        allow_network: bool = True,
        allow_file_deletion: bool = True,
    ):
        """
        Initialize the security validator.
        
        Args:
            allowed_commands: Set of allowed command names (uses default if None)
            workspace_dir: Restrict file operations to this directory
            allow_network: Allow network commands (curl, wget)
            allow_file_deletion: Allow rm command
        """
        self.allowed_commands = allowed_commands or ALLOWED_COMMANDS.copy()
        self.workspace_dir = workspace_dir
        self.allow_network = allow_network
        self.allow_file_deletion = allow_file_deletion
        
        # Adjust allowed commands based on settings
        if not allow_network:
            self.allowed_commands.discard("curl")
            self.allowed_commands.discard("wget")
        
        if not allow_file_deletion:
            self.allowed_commands.discard("rm")
        
        # Compile dangerous patterns
        self._dangerous_patterns = [
            re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS
        ]
    
    def validate_command(self, command: str) -> ValidationResult:
        """
        Validate a bash command.
        
        Args:
            command: The command string to validate
            
        Returns:
            ValidationResult with allowed status and reason
        """
        if not command or not command.strip():
            return ValidationResult(allowed=False, reason="Empty command")
        
        # Check for dangerous patterns first
        for pattern in self._dangerous_patterns:
            if pattern.search(command):
                return ValidationResult(
                    allowed=False,
                    reason=f"Command matches dangerous pattern: {pattern.pattern}"
                )
        
        # Extract all commands from the command string
        commands = self._extract_commands(command)
        
        if not commands:
            return ValidationResult(
                allowed=False,
                reason="Could not parse command for security validation"
            )
        
        warnings = []
        
        # Check each command against allowlist
        for cmd in commands:
            if cmd not in self.allowed_commands:
                return ValidationResult(
                    allowed=False,
                    reason=f"Command '{cmd}' is not in the allowed commands list"
                )
            
            # Additional validation for sensitive commands
            if cmd in COMMANDS_NEEDING_VALIDATION:
                result = self._validate_sensitive_command(cmd, command)
                if not result.allowed:
                    return result
                warnings.extend(result.warnings)
        
        return ValidationResult(allowed=True, warnings=warnings)
    
    def _extract_commands(self, command_string: str) -> List[str]:
        """
        Extract command names from a shell command string.
        
        Handles pipes, command chaining (&&, ||, ;), and subshells.
        """
        commands = []
        
        # Split on semicolons that aren't inside quotes
        segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            try:
                tokens = shlex.split(segment)
            except ValueError:
                # Malformed command - fail safe
                return []
            
            if not tokens:
                continue
            
            expect_command = True
            
            for token in tokens:
                # Shell operators indicate a new command follows
                if token in ("|", "||", "&&", "&"):
                    expect_command = True
                    continue
                
                # Skip shell keywords
                if token in (
                    "if", "then", "else", "elif", "fi",
                    "for", "while", "until", "do", "done",
                    "case", "esac", "in", "!", "{", "}",
                ):
                    continue
                
                # Skip flags/options
                if token.startswith("-"):
                    continue
                
                # Skip variable assignments
                if "=" in token and not token.startswith("="):
                    continue
                
                if expect_command:
                    # Extract base command name
                    cmd = os.path.basename(token)
                    commands.append(cmd)
                    expect_command = False
        
        return commands
    
    def _validate_sensitive_command(
        self,
        cmd: str,
        full_command: str,
    ) -> ValidationResult:
        """Perform additional validation for sensitive commands."""
        
        if cmd == "pkill" or cmd == "kill":
            return self._validate_kill_command(full_command)
        elif cmd == "chmod":
            return self._validate_chmod_command(full_command)
        elif cmd == "rm":
            return self._validate_rm_command(full_command)
        elif cmd in ("curl", "wget"):
            return self._validate_network_command(full_command)
        
        return ValidationResult(allowed=True)
    
    def _validate_kill_command(self, command: str) -> ValidationResult:
        """Validate kill/pkill commands."""
        allowed_processes = {
            "node", "npm", "npx", "python", "python3",
            "vite", "next", "webpack", "jest", "pytest",
        }
        
        try:
            tokens = shlex.split(command)
        except ValueError:
            return ValidationResult(allowed=False, reason="Could not parse kill command")
        
        # Find the target process
        args = [t for t in tokens[1:] if not t.startswith("-")]
        
        if not args:
            return ValidationResult(allowed=False, reason="kill/pkill requires a target")
        
        target = args[-1]
        
        # For -f flag, extract first word
        if " " in target:
            target = target.split()[0]
        
        if target in allowed_processes or target.isdigit():
            return ValidationResult(allowed=True)
        
        return ValidationResult(
            allowed=False,
            reason=f"kill/pkill only allowed for dev processes: {allowed_processes}"
        )
    
    def _validate_chmod_command(self, command: str) -> ValidationResult:
        """Validate chmod commands - only allow +x variants."""
        try:
            tokens = shlex.split(command)
        except ValueError:
            return ValidationResult(allowed=False, reason="Could not parse chmod command")
        
        if not tokens or tokens[0] != "chmod":
            return ValidationResult(allowed=False, reason="Not a chmod command")
        
        # Find the mode argument
        mode = None
        for token in tokens[1:]:
            if token.startswith("-"):
                return ValidationResult(
                    allowed=False,
                    reason="chmod flags are not allowed"
                )
            elif mode is None:
                mode = token
        
        if mode is None:
            return ValidationResult(allowed=False, reason="chmod requires a mode")
        
        # Only allow +x variants
        if not re.match(r"^[ugoa]*\+x$", mode):
            return ValidationResult(
                allowed=False,
                reason=f"chmod only allowed with +x mode, got: {mode}"
            )
        
        return ValidationResult(allowed=True)
    
    def _validate_rm_command(self, command: str) -> ValidationResult:
        """Validate rm commands - prevent dangerous deletions."""
        try:
            tokens = shlex.split(command)
        except ValueError:
            return ValidationResult(allowed=False, reason="Could not parse rm command")
        
        warnings = []
        
        # Check for dangerous flags
        for token in tokens:
            if token == "-rf" or token == "-fr":
                warnings.append("Using rm -rf - be careful!")
            if token.startswith("/") and token.count("/") <= 2:
                return ValidationResult(
                    allowed=False,
                    reason=f"Cannot delete system directories: {token}"
                )
        
        # If workspace is set, ensure paths are within it
        if self.workspace_dir:
            for token in tokens[1:]:
                if not token.startswith("-"):
                    # This is a path argument
                    if token.startswith("/"):
                        try:
                            from pathlib import Path
                            path = Path(token).resolve()
                            workspace = Path(self.workspace_dir).resolve()
                            path.relative_to(workspace)
                        except ValueError:
                            return ValidationResult(
                                allowed=False,
                                reason=f"rm path '{token}' is outside workspace"
                            )
        
        return ValidationResult(allowed=True, warnings=warnings)
    
    def _validate_network_command(self, command: str) -> ValidationResult:
        """Validate network commands."""
        # Block piping to shell
        if re.search(r"\|\s*(ba)?sh", command):
            return ValidationResult(
                allowed=False,
                reason="Piping network output to shell is not allowed"
            )
        
        return ValidationResult(
            allowed=True,
            warnings=["Network command - ensure URL is trusted"]
        )
    
    def add_allowed_command(self, command: str) -> None:
        """Add a command to the allowlist."""
        self.allowed_commands.add(command)
    
    def remove_allowed_command(self, command: str) -> None:
        """Remove a command from the allowlist."""
        self.allowed_commands.discard(command)


# Convenience function for quick validation
def validate_bash_command(
    command: str,
    workspace_dir: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Quick validation of a bash command.
    
    Args:
        command: The command to validate
        workspace_dir: Optional workspace directory restriction
        
    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    validator = SecurityValidator(workspace_dir=workspace_dir)
    result = validator.validate_command(command)
    return result.allowed, result.reason
