"""
Real-time file system watching functionality.
"""

import time
import fnmatch
from pathlib import Path
from typing import Optional, Callable, Set
from threading import Thread, Event
from queue import Queue, Empty

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileMovedEvent,
    FileModifiedEvent,
)

from .config import Config
from .organizer import FileOrganizer, OrganizeResult


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events for the watcher."""
    
    def __init__(
        self,
        event_queue: Queue,
        ignore_patterns: list,
        debounce_seconds: float
    ):
        super().__init__()
        self.event_queue = event_queue
        self.ignore_patterns = ignore_patterns
        self.debounce_seconds = debounce_seconds
        self._pending_events: dict = {}
        self._last_event_time: dict = {}
    
    def _should_ignore(self, path: str) -> bool:
        """Check if the file should be ignored based on patterns."""
        filename = Path(path).name
        return any(
            fnmatch.fnmatch(filename, pattern) 
            for pattern in self.ignore_patterns
        )
    
    def _handle_event(self, event_path: str) -> None:
        """Handle a file event with debouncing."""
        if self._should_ignore(event_path):
            return
        
        current_time = time.time()
        
        # Check if we should debounce
        if event_path in self._last_event_time:
            if current_time - self._last_event_time[event_path] < self.debounce_seconds:
                return
        
        self._last_event_time[event_path] = current_time
        self.event_queue.put(event_path)
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            # Add a small delay for file creation to complete
            time.sleep(0.5)
            self._handle_event(event.src_path)
    
    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move events."""
        if not event.is_directory:
            self._handle_event(event.dest_path)


class DirectoryWatcher:
    """Watches a directory for changes and auto-organizes new files."""
    
    def __init__(
        self,
        config: Config,
        watch_dir: Path,
        dest_dir: Optional[Path] = None,
        sort_by: str = "type",
        rename_files: bool = False,
        on_organize: Optional[Callable[[OrganizeResult], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        self.config = config
        self.watch_dir = Path(watch_dir).resolve()
        self.dest_dir = Path(dest_dir).resolve() if dest_dir else self.watch_dir
        self.sort_by = sort_by
        self.rename_files = rename_files
        self.on_organize = on_organize
        self.on_error = on_error
        
        self.organizer = FileOrganizer(config)
        self._event_queue: Queue = Queue()
        self._stop_event = Event()
        self._observer: Optional[Observer] = None
        self._processor_thread: Optional[Thread] = None
        self._is_running = False
    
    def start(self) -> None:
        """Start watching the directory."""
        if self._is_running:
            return
        
        self._stop_event.clear()
        
        # Set up the event handler
        event_handler = FileEventHandler(
            event_queue=self._event_queue,
            ignore_patterns=self.config.watch_settings.ignore_patterns,
            debounce_seconds=self.config.watch_settings.debounce_seconds
        )
        
        # Start the observer
        self._observer = Observer()
        self._observer.schedule(
            event_handler,
            str(self.watch_dir),
            recursive=self.config.watch_settings.recursive
        )
        self._observer.start()
        
        # Start the processor thread
        self._processor_thread = Thread(target=self._process_events, daemon=True)
        self._processor_thread.start()
        
        self._is_running = True
    
    def stop(self) -> None:
        """Stop watching the directory."""
        if not self._is_running:
            return
        
        self._stop_event.set()
        
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
            self._processor_thread = None
        
        self._is_running = False
    
    def _process_events(self) -> None:
        """Process file events from the queue."""
        processed_files: Set[str] = set()
        
        while not self._stop_event.is_set():
            try:
                event_path = self._event_queue.get(timeout=1)
                
                # Skip if already processed recently
                if event_path in processed_files:
                    continue
                
                file_path = Path(event_path)
                
                # Skip if file no longer exists
                if not file_path.exists():
                    continue
                
                # Skip if it's in a category folder (already organized)
                if self._is_in_category_folder(file_path):
                    continue
                
                # Organize the single file
                try:
                    result = self.organizer.organize(
                        source_dir=file_path.parent,
                        dest_dir=self.dest_dir,
                        sort_by=self.sort_by,
                        rename_files=self.rename_files,
                        recursive=False,
                        dry_run=False
                    )
                    
                    # Filter result to only this file
                    result.actions = [
                        a for a in result.actions 
                        if a.source == file_path
                    ]
                    
                    if result.actions and self.on_organize:
                        self.on_organize(result)
                    
                    processed_files.add(event_path)
                    
                    # Limit the size of processed_files set
                    if len(processed_files) > 1000:
                        processed_files.clear()
                        
                except Exception as e:
                    if self.on_error:
                        self.on_error(e)
                        
            except Empty:
                continue
    
    def _is_in_category_folder(self, file_path: Path) -> bool:
        """Check if a file is already in a category folder."""
        categories = set(self.config.categories.keys())
        categories.add(self.config.unknown_category)
        
        # Check if any parent folder is a category
        for parent in file_path.parents:
            if parent.name in categories:
                return True
            if parent == self.dest_dir:
                break
        
        return False
    
    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._is_running
