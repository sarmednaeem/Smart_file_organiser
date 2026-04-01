"""
Smart file renaming functionality.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import Config, RenameSettings


class FileRenamer:
    """Handles intelligent file renaming."""
    
    def __init__(self, config: Config):
        self.config = config
        self.settings = config.rename_settings
    
    def generate_new_name(self, file_path: Path) -> str:
        """Generate a clean, standardized filename."""
        original_name = file_path.stem
        extension = file_path.suffix
        
        # Start with the original name
        new_name = original_name
        
        # Remove common prefixes
        new_name = self._remove_prefixes(new_name)
        
        # Remove special characters if enabled
        if self.settings.remove_special_chars:
            new_name = self._clean_special_chars(new_name)
        
        # Handle multiple consecutive separators
        new_name = self._normalize_separators(new_name)
        
        # Apply case transformation
        if self.settings.lowercase:
            new_name = new_name.lower()
        
        # Truncate if too long
        if len(new_name) > self.settings.max_length:
            new_name = new_name[:self.settings.max_length]
        
        # Ensure we have a valid name
        new_name = new_name.strip("_- ")
        if not new_name:
            new_name = self._generate_timestamp_name()
        
        return new_name + extension
    
    def _remove_prefixes(self, name: str) -> str:
        """Remove common auto-generated prefixes."""
        for prefix in self.settings.remove_prefixes:
            if name.lower().startswith(prefix.lower()):
                name = name[len(prefix):]
        return name
    
    def _clean_special_chars(self, name: str) -> str:
        """Remove or replace special characters."""
        # Replace common separators with the configured separator
        name = re.sub(r'[\s\-_]+', self.settings.separator, name)
        
        # Remove other special characters (keep alphanumeric and separator)
        separator_escaped = re.escape(self.settings.separator)
        name = re.sub(rf'[^a-zA-Z0-9{separator_escaped}]', '', name)
        
        return name
    
    def _normalize_separators(self, name: str) -> str:
        """Normalize multiple consecutive separators."""
        separator = self.settings.separator
        pattern = f'{re.escape(separator)}+'
        return re.sub(pattern, separator, name)
    
    def _generate_timestamp_name(self) -> str:
        """Generate a timestamp-based name for files with no usable name."""
        timestamp = datetime.now().strftime(self.settings.date_format + "_%H%M%S")
        return f"file{self.settings.separator}{timestamp}"
    
    def get_date_based_name(self, file_path: Path) -> str:
        """Generate a date-based filename using file modification time."""
        try:
            mtime = os.path.getmtime(file_path)
            date_str = datetime.fromtimestamp(mtime).strftime(self.settings.date_format)
        except OSError:
            date_str = datetime.now().strftime(self.settings.date_format)
        
        original_name = file_path.stem
        extension = file_path.suffix
        
        # Clean the original name
        clean_name = self._remove_prefixes(original_name)
        if self.settings.remove_special_chars:
            clean_name = self._clean_special_chars(clean_name)
        clean_name = self._normalize_separators(clean_name)
        
        if clean_name:
            new_name = f"{date_str}{self.settings.separator}{clean_name}"
        else:
            new_name = f"{date_str}{self.settings.separator}file"
        
        return new_name + extension
    
    def get_unique_path(self, target_path: Path) -> Path:
        """Get a unique file path by adding a counter if needed."""
        if not target_path.exists():
            return target_path
        
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        counter = 1
        while True:
            new_name = f"{stem}{self.settings.separator}{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            
            # Safety limit
            if counter > 9999:
                raise ValueError(f"Could not find unique name for {target_path}")
    
    def preview_rename(self, file_path: Path) -> Tuple[str, str]:
        """Preview what a file would be renamed to."""
        original = file_path.name
        new_name = self.generate_new_name(file_path)
        return (original, new_name)
    
    def should_rename(self, file_path: Path) -> bool:
        """Check if a file should be renamed based on current settings."""
        original = file_path.name
        new_name = self.generate_new_name(file_path)
        return original != new_name
//