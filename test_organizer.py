"""Tests for the file organizer module."""

import os
import tempfile
import shutil
from pathlib import Path
import pytest

from src.config import Config
from src.organizer import FileOrganizer


@pytest.fixture
def temp_dir():
    """Create a temporary directory with test files."""
    temp_path = tempfile.mkdtemp()
    
    # Create test files
    test_files = [
        "document.pdf",
        "photo.jpg",
        "video.mp4",
        "script.py",
        "archive.zip",
        "music.mp3",
    ]
    
    for filename in test_files:
        (Path(temp_path) / filename).touch()
    
    yield temp_path
    
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config()


@pytest.fixture
def organizer(config):
    """Create a FileOrganizer instance."""
    return FileOrganizer(config)


class TestFileOrganizer:
    """Tests for FileOrganizer class."""
    
    def test_scan_directory(self, organizer, temp_dir):
        """Test scanning a directory."""
        categorized = organizer.scan_directory(Path(temp_dir))
        
        assert "Documents" in categorized
        assert "Images" in categorized
        assert "Videos" in categorized
        assert "Code" in categorized
        assert "Archives" in categorized
        assert "Audio" in categorized
    
    def test_organize_by_type(self, organizer, temp_dir):
        """Test organizing files by type."""
        result = organizer.organize(
            source_dir=Path(temp_dir),
            sort_by="type"
        )
        
        assert result.success
        assert result.total_processed == 6
        
        # Check that category folders were created
        assert (Path(temp_dir) / "Documents").exists()
        assert (Path(temp_dir) / "Images").exists()
        assert (Path(temp_dir) / "Videos").exists()
    
    def test_dry_run(self, organizer, temp_dir):
        """Test dry run mode doesn't move files."""
        original_files = list(Path(temp_dir).glob("*"))
        
        result = organizer.organize(
            source_dir=Path(temp_dir),
            sort_by="type",
            dry_run=True
        )
        
        # Files should still be in original location
        current_files = [f for f in Path(temp_dir).glob("*") if f.is_file()]
        assert len(current_files) == len([f for f in original_files if f.is_file()])
    
    def test_undo(self, organizer, temp_dir):
        """Test undo functionality."""
        # First organize
        organizer.organize(source_dir=Path(temp_dir), sort_by="type")
        
        # Then undo
        undone = organizer.undo_last(count=6)
        
        assert len(undone) == 6
        
        # Check files are back
        current_files = [f for f in Path(temp_dir).glob("*") if f.is_file()]
        assert len(current_files) == 6
    
    def test_preview(self, organizer, temp_dir):
        """Test preview functionality."""
        preview = organizer.preview_organization(
            source_dir=Path(temp_dir),
            sort_by="type"
        )
        
        assert len(preview) > 0
        total_files = sum(len(files) for files in preview.values())
        assert total_files == 6
