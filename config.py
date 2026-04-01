"""
Configuration management for Smart File Organizer.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Default file categories and their extensions
DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
        ".xls", ".xlsx", ".ppt", ".pptx", ".pages", ".numbers", ".key"
    ],
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
        ".webp", ".ico", ".tiff", ".tif", ".raw", ".heic"
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",
        ".m4a", ".aiff", ".alac"
    ],
    "Videos": [
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
        ".webm", ".m4v", ".mpeg", ".mpg"
    ],
    "Archives": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
        ".xz", ".iso", ".dmg"
    ],
    "Code": [
        ".py", ".js", ".ts", ".html", ".css", ".java",
        ".cpp", ".c", ".h", ".hpp", ".cs", ".go", ".rs",
        ".rb", ".php", ".swift", ".kt", ".scala", ".r"
    ],
    "Data": [
        ".json", ".xml", ".yaml", ".yml", ".csv", ".sql",
        ".db", ".sqlite", ".sqlite3"
    ],
    "Executables": [
        ".exe", ".msi", ".dmg", ".app", ".deb", ".rpm",
        ".sh", ".bat", ".cmd"
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2", ".eot"
    ],
    "Ebooks": [
        ".epub", ".mobi", ".azw", ".azw3", ".fb2"
    ],
}

# Prefixes commonly found in auto-generated filenames
DEFAULT_RENAME_PREFIXES = [
    "IMG_", "DSC_", "Screenshot_", "Screen Shot ",
    "Photo_", "VID_", "MOV_", "DCIM_", "PXL_",
    "Untitled_", "Copy of ", "Copy_of_"
]


@dataclass
class RenameSettings:
    """Settings for file renaming."""
    remove_prefixes: List[str] = field(default_factory=lambda: DEFAULT_RENAME_PREFIXES.copy())
    date_format: str = "%Y-%m-%d"
    separator: str = "_"
    lowercase: bool = False
    remove_special_chars: bool = True
    max_length: int = 100


@dataclass
class WatchSettings:
    """Settings for watch mode."""
    debounce_seconds: float = 2.0
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.tmp", "*.temp", "*.partial", "~*", ".DS_Store", "Thumbs.db"
    ])
    recursive: bool = False


@dataclass
class DuplicateSettings:
    """Settings for duplicate handling."""
    action: str = "move"  # "move", "delete", "ignore"
    duplicate_folder: str = "Duplicates"
    compare_method: str = "hash"  # "hash", "name", "size"
    hash_algorithm: str = "md5"  # "md5", "sha256"
    min_size_bytes: int = 1024  # Ignore files smaller than this


@dataclass
class Config:
    """Main configuration class."""
    categories: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_CATEGORIES.copy())
    rename_settings: RenameSettings = field(default_factory=RenameSettings)
    watch_settings: WatchSettings = field(default_factory=WatchSettings)
    duplicate_settings: DuplicateSettings = field(default_factory=DuplicateSettings)
    
    # General settings
    create_date_folders: bool = True
    date_folder_format: str = "%Y/%m"  # Year/Month structure
    unknown_category: str = "Other"
    preserve_structure: bool = False
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from a JSON file."""
        if config_path is None:
            config_path = "config.json"
        
        config = cls()
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Update categories
                if "categories" in data:
                    config.categories.update(data["categories"])
                
                # Update rename settings
                if "rename_patterns" in data:
                    for key, value in data["rename_patterns"].items():
                        if hasattr(config.rename_settings, key):
                            setattr(config.rename_settings, key, value)
                
                # Update watch settings
                if "watch_settings" in data:
                    for key, value in data["watch_settings"].items():
                        if hasattr(config.watch_settings, key):
                            setattr(config.watch_settings, key, value)
                
                # Update duplicate settings
                if "duplicate_handling" in data:
                    for key, value in data["duplicate_handling"].items():
                        if hasattr(config.duplicate_settings, key):
                            setattr(config.duplicate_settings, key, value)
                
                # Update general settings
                for key in ["create_date_folders", "date_folder_format", 
                           "unknown_category", "preserve_structure"]:
                    if key in data:
                        setattr(config, key, data[key])
                        
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")
        
        return config
    
    def save(self, config_path: str = "config.json") -> None:
        """Save configuration to a JSON file."""
        data = {
            "categories": self.categories,
            "rename_patterns": {
                "remove_prefixes": self.rename_settings.remove_prefixes,
                "date_format": self.rename_settings.date_format,
                "separator": self.rename_settings.separator,
                "lowercase": self.rename_settings.lowercase,
                "remove_special_chars": self.rename_settings.remove_special_chars,
                "max_length": self.rename_settings.max_length,
            },
            "watch_settings": {
                "debounce_seconds": self.watch_settings.debounce_seconds,
                "ignore_patterns": self.watch_settings.ignore_patterns,
                "recursive": self.watch_settings.recursive,
            },
            "duplicate_handling": {
                "action": self.duplicate_settings.action,
                "duplicate_folder": self.duplicate_settings.duplicate_folder,
                "compare_method": self.duplicate_settings.compare_method,
                "hash_algorithm": self.duplicate_settings.hash_algorithm,
                "min_size_bytes": self.duplicate_settings.min_size_bytes,
            },
            "create_date_folders": self.create_date_folders,
            "date_folder_format": self.date_folder_format,
            "unknown_category": self.unknown_category,
            "preserve_structure": self.preserve_structure,
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def get_category(self, extension: str) -> str:
        """Get the category for a given file extension."""
        ext_lower = extension.lower()
        for category, extensions in self.categories.items():
            if ext_lower in [e.lower() for e in extensions]:
                return category
        return self.unknown_category
    
    def get_all_extensions(self) -> List[str]:
        """Get all registered file extensions."""
        extensions = []
        for exts in self.categories.values():
            extensions.extend(exts)
        return extensions
