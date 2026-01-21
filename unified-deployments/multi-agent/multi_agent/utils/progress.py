"""
Progress tracking utilities for the multi-agent system.

Adapted from claude-quickstarts/autonomous-coding/progress.py for use with
the local VLLM-based multi-agent system.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    """Represents a task or feature to be completed."""
    id: str
    description: str
    category: str = "general"
    status: str = "pending"  # pending, in_progress, completed, failed
    steps: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "steps": self.steps,
            "notes": self.notes,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            status=data.get("status", "pending"),
            steps=data.get("steps", []),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
        )


class ProgressTracker:
    """
    Tracks progress on tasks and features.
    
    Provides methods for:
    - Adding and updating tasks
    - Tracking completion status
    - Generating progress reports
    - Persisting progress to disk
    """
    
    def __init__(
        self,
        project_dir: Optional[str] = None,
        tasks_file: str = "tasks.json",
        progress_file: str = "progress.txt",
    ):
        """
        Initialize the progress tracker.
        
        Args:
            project_dir: Directory for storing progress files
            tasks_file: Name of the tasks JSON file
            progress_file: Name of the progress notes file
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.tasks_file = self.project_dir / tasks_file
        self.progress_file = self.project_dir / progress_file
        self.tasks: Dict[str, Task] = {}
        
        # Load existing tasks if available
        self._load_tasks()
    
    def _load_tasks(self) -> None:
        """Load tasks from disk."""
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            task = Task.from_dict(item)
                            self.tasks[task.id] = task
                    elif isinstance(data, dict):
                        for task_id, item in data.items():
                            task = Task.from_dict(item)
                            self.tasks[task_id] = task
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_tasks(self) -> None:
        """Save tasks to disk."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.tasks_file, "w") as f:
            json.dump(
                [task.to_dict() for task in self.tasks.values()],
                f,
                indent=2,
            )
    
    def add_task(
        self,
        task_id: str,
        description: str,
        category: str = "general",
        steps: Optional[List[str]] = None,
    ) -> Task:
        """
        Add a new task.
        
        Args:
            task_id: Unique identifier for the task
            description: Description of what needs to be done
            category: Category (e.g., "functional", "style", "bug")
            steps: List of steps to complete the task
            
        Returns:
            The created Task
        """
        task = Task(
            id=task_id,
            description=description,
            category=category,
            steps=steps or [],
        )
        self.tasks[task_id] = task
        self._save_tasks()
        return task
    
    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Update a task's status or notes.
        
        Args:
            task_id: ID of the task to update
            status: New status (pending, in_progress, completed, failed)
            notes: Additional notes
            
        Returns:
            The updated Task or None if not found
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None
        
        if status:
            task.status = status
            if status == "completed":
                task.completed_at = datetime.now().isoformat()
        
        if notes:
            task.notes = notes
        
        self._save_tasks()
        return task
    
    def complete_task(self, task_id: str, notes: str = "") -> Optional[Task]:
        """Mark a task as completed."""
        return self.update_task(task_id, status="completed", notes=notes)
    
    def fail_task(self, task_id: str, notes: str = "") -> Optional[Task]:
        """Mark a task as failed."""
        return self.update_task(task_id, status="failed", notes=notes)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: str) -> List[Task]:
        """Get all tasks with a specific status."""
        return [t for t in self.tasks.values() if t.status == status]
    
    def get_tasks_by_category(self, category: str) -> List[Task]:
        """Get all tasks in a specific category."""
        return [t for t in self.tasks.values() if t.category == category]
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next pending task to work on."""
        pending = self.get_tasks_by_status("pending")
        return pending[0] if pending else None
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get a summary of progress.
        
        Returns:
            Dictionary with progress statistics
        """
        total = len(self.tasks)
        completed = len(self.get_tasks_by_status("completed"))
        in_progress = len(self.get_tasks_by_status("in_progress"))
        pending = len(self.get_tasks_by_status("pending"))
        failed = len(self.get_tasks_by_status("failed"))
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "failed": failed,
            "completion_percentage": (completed / total * 100) if total > 0 else 0,
        }
    
    def print_progress(self) -> None:
        """Print a formatted progress summary."""
        summary = self.get_progress_summary()
        
        print("\n" + "=" * 50)
        print("  PROGRESS SUMMARY")
        print("=" * 50)
        print(f"  Total tasks:     {summary['total']}")
        print(f"  Completed:       {summary['completed']}")
        print(f"  In Progress:     {summary['in_progress']}")
        print(f"  Pending:         {summary['pending']}")
        print(f"  Failed:          {summary['failed']}")
        print(f"  Completion:      {summary['completion_percentage']:.1f}%")
        print("=" * 50 + "\n")
    
    def save_progress_notes(self, notes: str) -> None:
        """
        Save progress notes to the progress file.
        
        Args:
            notes: Notes to append to the progress file
        """
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n--- {timestamp} ---\n{notes}\n"
        
        with open(self.progress_file, "a") as f:
            f.write(entry)
    
    def get_progress_notes(self) -> str:
        """Read all progress notes."""
        if self.progress_file.exists():
            return self.progress_file.read_text()
        return ""
    
    def import_feature_list(self, feature_list_path: str) -> int:
        """
        Import tasks from a feature_list.json file.
        
        Args:
            feature_list_path: Path to the feature list JSON file
            
        Returns:
            Number of tasks imported
        """
        path = Path(feature_list_path)
        if not path.exists():
            return 0
        
        try:
            with open(path) as f:
                features = json.load(f)
            
            count = 0
            for i, feature in enumerate(features):
                task_id = f"feature_{i + 1}"
                if task_id not in self.tasks:
                    self.add_task(
                        task_id=task_id,
                        description=feature.get("description", ""),
                        category=feature.get("category", "functional"),
                        steps=feature.get("steps", []),
                    )
                    
                    # Set status based on "passes" field
                    if feature.get("passes", False):
                        self.complete_task(task_id)
                    
                    count += 1
            
            return count
            
        except (json.JSONDecodeError, IOError):
            return 0
    
    def export_feature_list(self, output_path: str) -> None:
        """
        Export tasks to a feature_list.json format.
        
        Args:
            output_path: Path for the output file
        """
        features = []
        for task in self.tasks.values():
            features.append({
                "category": task.category,
                "description": task.description,
                "steps": task.steps,
                "passes": task.status == "completed",
            })
        
        with open(output_path, "w") as f:
            json.dump(features, f, indent=2)
