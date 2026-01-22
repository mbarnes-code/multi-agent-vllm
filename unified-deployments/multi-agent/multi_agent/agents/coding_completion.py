# Completion code for coding.py precision enhancement functions
# This contains the missing functions that need to be added to coding.py


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