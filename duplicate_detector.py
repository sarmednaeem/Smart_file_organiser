"""
Duplicate file detection functionality.
"""

import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Callable
from dataclasses import dataclass

from .config import Config


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate files."""
    hash_value: str
    files: List[Path]
    size: int
    
    @property
    def count(self) -> int:
        return len(self.files)
    
    @property
    def wasted_space(self) -> int:
        """Calculate wasted space (all but one copy)."""
        return self.size * (self.count - 1)


class DuplicateDetector:
    """Detects and manages duplicate files."""
    
    CHUNK_SIZE = 8192  # Read files in chunks for memory efficiency
    
    def __init__(self, config: Config):
        self.config = config
        self.settings = config.duplicate_settings
        self._cancel_flag = False
    
    def cancel(self) -> None:
        """Cancel an ongoing scan."""
        self._cancel_flag = True
    
    def find_duplicates(
        self,
        directory: Path,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[DuplicateGroup]:
        """
        Find all duplicate files in a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            progress_callback: Optional callback(current, total, current_file)
        
        Returns:
            List of DuplicateGroup objects containing duplicate files
        """
        self._cancel_flag = False
        
        # Step 1: Group files by size
        size_groups = self._group_by_size(directory, recursive, progress_callback)
        
        if self._cancel_flag:
            return []
        
        # Step 2: For groups with multiple files, calculate hashes
        duplicates = []
        potential_duplicates = [(size, files) for size, files in size_groups.items() 
                               if len(files) > 1]
        
        total_to_hash = sum(len(files) for _, files in potential_duplicates)
        hashed = 0
        
        for size, files in potential_duplicates:
            if self._cancel_flag:
                return []
            
            hash_groups: Dict[str, List[Path]] = defaultdict(list)
            
            for file_path in files:
                if self._cancel_flag:
                    return []
                
                file_hash = self._calculate_hash(file_path)
                if file_hash:
                    hash_groups[file_hash].append(file_path)
                
                hashed += 1
                if progress_callback:
                    progress_callback(hashed, total_to_hash, str(file_path))
            
            # Create duplicate groups for hashes with multiple files
            for hash_value, hash_files in hash_groups.items():
                if len(hash_files) > 1:
                    duplicates.append(DuplicateGroup(
                        hash_value=hash_value,
                        files=sorted(hash_files),
                        size=size
                    ))
        
        return sorted(duplicates, key=lambda x: x.wasted_space, reverse=True)
    
    def _group_by_size(
        self,
        directory: Path,
        recursive: bool,
        progress_callback: Optional[Callable[[int, int, str], None]]
    ) -> Dict[int, List[Path]]:
        """Group files by their size."""
        size_groups: Dict[int, List[Path]] = defaultdict(list)
        
        # Collect all files first
        pattern = "**/*" if recursive else "*"
        all_files = [f for f in directory.glob(pattern) if f.is_file()]
        
        for i, file_path in enumerate(all_files):
            if self._cancel_flag:
                return {}
            
            try:
                size = file_path.stat().st_size
                
                # Skip files smaller than minimum size
                if size >= self.settings.min_size_bytes:
                    size_groups[size].append(file_path)
                
                if progress_callback:
                    progress_callback(i + 1, len(all_files), str(file_path))
                    
            except (OSError, IOError):
                continue
        
        return size_groups
    
    def _calculate_hash(self, file_path: Path) -> Optional[str]:
        """Calculate the hash of a file."""
        try:
            if self.settings.hash_algorithm == "sha256":
                hasher = hashlib.sha256()
            else:
                hasher = hashlib.md5()
            
            with open(file_path, "rb") as f:
                while True:
                    if self._cancel_flag:
                        return None
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except (OSError, IOError):
            return None
    
    def quick_compare(self, file1: Path, file2: Path) -> bool:
        """Quickly compare two files to check if they're duplicates."""
        try:
            # First compare sizes
            if file1.stat().st_size != file2.stat().st_size:
                return False
            
            # Then compare hashes
            hash1 = self._calculate_hash(file1)
            hash2 = self._calculate_hash(file2)
            
            return hash1 is not None and hash1 == hash2
            
        except (OSError, IOError):
            return False
    
    def get_duplicate_stats(self, groups: List[DuplicateGroup]) -> Dict:
        """Get statistics about found duplicates."""
        total_files = sum(g.count for g in groups)
        total_wasted = sum(g.wasted_space for g in groups)
        
        return {
            "total_groups": len(groups),
            "total_duplicate_files": total_files,
            "total_wasted_bytes": total_wasted,
            "total_wasted_mb": round(total_wasted / (1024 * 1024), 2),
            "largest_group_size": max((g.count for g in groups), default=0),
            "largest_wasted_single": max((g.wasted_space for g in groups), default=0),
        }
