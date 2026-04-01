"""
Core file organization functionality.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
from send2trash import send2trash

from .config import Config
from .file_renamer import FileRenamer
from .duplicate_detector import DuplicateDetector


@dataclass
class OrganizeAction:
    """Represents a single file organization action."""
    source: Path
    destination: Path
    action_type: str  # "move", "rename", "copy"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "action_type": self.action_type,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OrganizeResult:
    """Result of an organization operation."""
    success: bool
    actions: List[OrganizeAction] = field(default_factory=list)
    errors: List[Tuple[Path, str]] = field(default_factory=list)
    skipped: List[Path] = field(default_factory=list)
    
    @property
    def total_processed(self) -> int:
        return len(self.actions)
    
    @property
    def total_errors(self) -> int:
        return len(self.errors)


class FileOrganizer:
    """Main file organization engine."""
    
    def __init__(self, config: Config):
        self.config = config
        self.renamer = FileRenamer(config)
        self.duplicate_detector = DuplicateDetector(config)
        self._history: List[OrganizeAction] = []
        self._cancel_flag = False
    
    def cancel(self) -> None:
        """Cancel an ongoing operation."""
        self._cancel_flag = True
    
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = False
    ) -> Dict[str, List[Path]]:
        """
        Scan a directory and categorize files.
        
        Returns a dictionary mapping categories to lists of file paths.
        """
        categorized: Dict[str, List[Path]] = {}
        
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                category = self.config.get_category(file_path.suffix)
                
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(file_path)
        
        return categorized
    
    def organize(
        self,
        source_dir: Path,
        dest_dir: Optional[Path] = None,
        sort_by: str = "type",  # "type", "date", "both"
        rename_files: bool = False,
        recursive: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> OrganizeResult:
        """
        Organize files in the source directory.
        
        Args:
            source_dir: Directory to organize
            dest_dir: Destination directory (defaults to source_dir)
            sort_by: Organization method ("type", "date", "both")
            rename_files: Whether to apply smart renaming
            recursive: Whether to process subdirectories
            dry_run: If True, don't actually move files
            progress_callback: Optional callback(current, total, current_file)
        
        Returns:
            OrganizeResult with details of the operation
        """
        self._cancel_flag = False
        result = OrganizeResult(success=True)
        
        if dest_dir is None:
            dest_dir = source_dir
        
        # Ensure directories exist
        source_dir = Path(source_dir).resolve()
        dest_dir = Path(dest_dir).resolve()
        
        if not source_dir.exists():
            result.success = False
            result.errors.append((source_dir, "Source directory does not exist"))
            return result
        
        # Collect files
        pattern = "**/*" if recursive else "*"
        files = [f for f in source_dir.glob(pattern) if f.is_file()]
        
        total = len(files)
        
        for i, file_path in enumerate(files):
            if self._cancel_flag:
                result.success = False
                break
            
            if progress_callback:
                progress_callback(i + 1, total, str(file_path))
            
            try:
                action = self._process_file(
                    file_path, dest_dir, sort_by, rename_files, dry_run
                )
                
                if action:
                    result.actions.append(action)
                    if not dry_run:
                        self._history.append(action)
                else:
                    result.skipped.append(file_path)
                    
            except Exception as e:
                result.errors.append((file_path, str(e)))
        
        return result
    
    def _process_file(
        self,
        file_path: Path,
        dest_dir: Path,
        sort_by: str,
        rename_files: bool,
        dry_run: bool
    ) -> Optional[OrganizeAction]:
        """Process a single file."""
        # Determine target directory
        target_dir = dest_dir
        
        if sort_by in ("type", "both"):
            category = self.config.get_category(file_path.suffix)
            target_dir = target_dir / category
        
        if sort_by in ("date", "both") and self.config.create_date_folders:
            try:
                mtime = os.path.getmtime(file_path)
                date_folder = datetime.fromtimestamp(mtime).strftime(
                    self.config.date_folder_format
                )
                target_dir = target_dir / date_folder
            except OSError:
                pass
        
        # Determine target filename
        if rename_files:
            target_name = self.renamer.generate_new_name(file_path)
        else:
            target_name = file_path.name
        
        target_path = target_dir / target_name
        
        # Skip if source and destination are the same
        if file_path.resolve() == target_path.resolve():
            return None
        
        # Get unique path if file already exists
        target_path = self.renamer.get_unique_path(target_path)
        
        # Perform the move
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(target_path))
        
        return OrganizeAction(
            source=file_path,
            destination=target_path,
            action_type="move"
        )
    
    def undo_last(self, count: int = 1) -> List[OrganizeAction]:
        """Undo the last N actions."""
        undone = []
        
        for _ in range(min(count, len(self._history))):
            action = self._history.pop()
            
            try:
                if action.destination.exists():
                    # Ensure source directory exists
                    action.source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(action.destination), str(action.source))
                    undone.append(action)
                    
                    # Clean up empty directories
                    self._cleanup_empty_dirs(action.destination.parent)
                    
            except Exception as e:
                print(f"Error undoing action: {e}")
        
        return undone
    
    def _cleanup_empty_dirs(self, directory: Path) -> None:
        """Remove empty directories."""
        try:
            while directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
                directory = directory.parent
        except (OSError, PermissionError):
            pass
    
    def preview_organization(
        self,
        source_dir: Path,
        dest_dir: Optional[Path] = None,
        sort_by: str = "type",
        rename_files: bool = False,
        recursive: bool = False
    ) -> Dict[str, List[Tuple[Path, Path]]]:
        """
        Preview how files would be organized.
        
        Returns a dictionary mapping categories to lists of (source, dest) tuples.
        """
        result = self.organize(
            source_dir, dest_dir, sort_by, rename_files, recursive, dry_run=True
        )
        
        preview: Dict[str, List[Tuple[Path, Path]]] = {}
        
        for action in result.actions:
            category = action.destination.parent.name
            if category not in preview:
                preview[category] = []
            preview[category].append((action.source, action.destination))
        
        return preview
    
    def get_history(self) -> List[OrganizeAction]:
        """Get the history of organization actions."""
        return self._history.copy()
    
    def clear_history(self) -> None:
        """Clear the action history."""
        self._history.clear()
