"""
Modern GUI for Smart File Organizer using CustomTkinter.
"""

import os
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .config import Config
from .organizer import FileOrganizer, OrganizeResult
from .watcher import DirectoryWatcher
from .duplicate_detector import DuplicateDetector, DuplicateGroup


# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SmartFileOrganizerGUI(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize configuration
        self.config = Config.load()
        self.organizer = FileOrganizer(self.config)
        self.watcher: Optional[DirectoryWatcher] = None
        
        # Window setup
        self.title("Smart File Organizer")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)
        
        # Create widgets
        self._create_header()
        self._create_settings_panel()
        self._create_log_panel()
        self._create_footer()
        
        # State variables
        self._is_organizing = False
        self._is_watching = False
    
    def _create_header(self) -> None:
        """Create the header section with folder selection."""
        header_frame = ctk.CTkFrame(self.main_container)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Source folder
        ctk.CTkLabel(header_frame, text="Source Folder:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        
        self.source_entry = ctk.CTkEntry(header_frame, placeholder_text="Select folder to organize...")
        self.source_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        self.source_browse_btn = ctk.CTkButton(
            header_frame, text="Browse", width=100,
            command=self._browse_source
        )
        self.source_browse_btn.grid(row=0, column=2, padx=10, pady=10)
        
        # Destination folder
        ctk.CTkLabel(header_frame, text="Destination:").grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )
        
        self.dest_entry = ctk.CTkEntry(header_frame, placeholder_text="Same as source (optional)")
        self.dest_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        self.dest_browse_btn = ctk.CTkButton(
            header_frame, text="Browse", width=100,
            command=self._browse_dest
        )
        self.dest_browse_btn.grid(row=1, column=2, padx=10, pady=10)
    
    def _create_settings_panel(self) -> None:
        """Create the settings panel."""
        settings_frame = ctk.CTkFrame(self.main_container)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        # Sort by option
        ctk.CTkLabel(settings_frame, text="Sort by:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        
        self.sort_var = ctk.StringVar(value="type")
        sort_options = ctk.CTkSegmentedButton(
            settings_frame,
            values=["Type", "Date", "Both"],
            variable=self.sort_var,
            command=lambda v: self.sort_var.set(v.lower())
        )
        sort_options.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        sort_options.set("Type")
        
        # Checkboxes
        self.rename_var = ctk.BooleanVar(value=False)
        rename_check = ctk.CTkCheckBox(
            settings_frame, text="Smart Rename",
            variable=self.rename_var
        )
        rename_check.grid(row=0, column=2, padx=20, pady=10)
        
        self.recursive_var = ctk.BooleanVar(value=False)
        recursive_check = ctk.CTkCheckBox(
            settings_frame, text="Include Subfolders",
            variable=self.recursive_var
        )
        recursive_check.grid(row=0, column=3, padx=20, pady=10)
        
        # Action buttons
        buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        buttons_frame.grid(row=1, column=0, columnspan=4, pady=10)
        
        self.organize_btn = ctk.CTkButton(
            buttons_frame, text="🗂️ Organize Now",
            command=self._start_organize, width=150
        )
        self.organize_btn.grid(row=0, column=0, padx=10)
        
        self.preview_btn = ctk.CTkButton(
            buttons_frame, text="👁️ Preview",
            command=self._preview_organize, width=120
        )
        self.preview_btn.grid(row=0, column=1, padx=10)
        
        self.watch_btn = ctk.CTkButton(
            buttons_frame, text="👀 Start Watch Mode",
            command=self._toggle_watch, width=150
        )
        self.watch_btn.grid(row=0, column=2, padx=10)
        
        self.duplicates_btn = ctk.CTkButton(
            buttons_frame, text="🔍 Find Duplicates",
            command=self._find_duplicates, width=150
        )
        self.duplicates_btn.grid(row=0, column=3, padx=10)
        
        self.undo_btn = ctk.CTkButton(
            buttons_frame, text="↩️ Undo",
            command=self._undo_last, width=100
        )
        self.undo_btn.grid(row=0, column=4, padx=10)
    
    def _create_log_panel(self) -> None:
        """Create the log/output panel."""
        log_frame = ctk.CTkFrame(self.main_container)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(log_frame, text="Activity Log").grid(
            row=0, column=0, padx=10, pady=5, sticky="w"
        )
        
        self.log_text = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(log_frame)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.progress_bar.set(0)
    
    def _create_footer(self) -> None:
        """Create the footer with status."""
        footer_frame = ctk.CTkFrame(self.main_container, height=30)
        footer_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        footer_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(footer_frame, text="Ready")
        self.status_label.grid(row=0, column=0, padx=10, sticky="w")
    
    def _browse_source(self) -> None:
        """Open folder browser for source directory."""
        folder = filedialog.askdirectory(title="Select Source Folder")
        if folder:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, folder)
    
    def _browse_dest(self) -> None:
        """Open folder browser for destination directory."""
        folder = filedialog.askdirectory(title="Select Destination Folder")
        if folder:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, folder)
    
    def _get_source_path(self) -> Optional[Path]:
        """Get and validate source path."""
        source = self.source_entry.get().strip()
        if not source:
            messagebox.showerror("Error", "Please select a source folder.")
            return None
        
        source_path = Path(source)
        if not source_path.exists():
            messagebox.showerror("Error", "Source folder does not exist.")
            return None
        
        return source_path
    
    def _get_dest_path(self) -> Optional[Path]:
        """Get destination path (or None for same as source)."""
        dest = self.dest_entry.get().strip()
        return Path(dest) if dest else None
    
    def _log(self, message: str) -> None:
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
    
    def _update_progress(self, current: int, total: int, filename: str) -> None:
        """Update the progress bar."""
        if total > 0:
            self.progress_bar.set(current / total)
            self.status_label.configure(text=f"Processing: {Path(filename).name}")
    
    def _start_organize(self) -> None:
        """Start the organization process."""
        source_path = self._get_source_path()
        if not source_path:
            return
        
        if self._is_organizing:
            return
        
        self._is_organizing = True
        self.organize_btn.configure(state="disabled")
        
        def organize_thread():
            try:
                self._log(f"Starting organization of {source_path}")
                
                result = self.organizer.organize(
                    source_dir=source_path,
                    dest_dir=self._get_dest_path(),
                    sort_by=self.sort_var.get(),
                    rename_files=self.rename_var.get(),
                    recursive=self.recursive_var.get(),
                    progress_callback=lambda c, t, f: self.after(
                        0, self._update_progress, c, t, f
                    )
                )
                
                self.after(0, self._on_organize_complete, result)
                
            except Exception as e:
                self.after(0, self._log, f"Error: {str(e)}")
            finally:
                self._is_organizing = False
                self.after(0, lambda: self.organize_btn.configure(state="normal"))
        
        thread = threading.Thread(target=organize_thread, daemon=True)
        thread.start()
    
    def _on_organize_complete(self, result: OrganizeResult) -> None:
        """Handle organization completion."""
        self.progress_bar.set(1)
        
        self._log(f"Organization complete!")
        self._log(f"  - Files moved: {result.total_processed}")
        self._log(f"  - Errors: {result.total_errors}")
        self._log(f"  - Skipped: {len(result.skipped)}")
        
        if result.errors:
            for path, error in result.errors[:5]:
                self._log(f"  Error: {path.name} - {error}")
        
        self.status_label.configure(text="Organization complete")
        
        messagebox.showinfo(
            "Complete",
            f"Organized {result.total_processed} files.\n"
            f"Errors: {result.total_errors}\n"
            f"Skipped: {len(result.skipped)}"
        )
    
    def _preview_organize(self) -> None:
        """Preview the organization without moving files."""
        source_path = self._get_source_path()
        if not source_path:
            return
        
        preview = self.organizer.preview_organization(
            source_dir=source_path,
            dest_dir=self._get_dest_path(),
            sort_by=self.sort_var.get(),
            rename_files=self.rename_var.get(),
            recursive=self.recursive_var.get()
        )
        
        self._log("Preview of organization:")
        total = 0
        for category, files in preview.items():
            self._log(f"  {category}: {len(files)} files")
            total += len(files)
        self._log(f"Total: {total} files would be organized")
    
    def _toggle_watch(self) -> None:
        """Toggle watch mode on/off."""
        if self._is_watching:
            self._stop_watch()
        else:
            self._start_watch()
    
    def _start_watch(self) -> None:
        """Start watching the directory."""
        source_path = self._get_source_path()
        if not source_path:
            return
        
        self.watcher = DirectoryWatcher(
            config=self.config,
            watch_dir=source_path,
            dest_dir=self._get_dest_path(),
            sort_by=self.sort_var.get(),
            rename_files=self.rename_var.get(),
            on_organize=lambda r: self.after(0, self._on_watch_organize, r),
            on_error=lambda e: self.after(0, self._log, f"Watch error: {e}")
        )
        
        self.watcher.start()
        self._is_watching = True
        
        self.watch_btn.configure(text="⏹️ Stop Watching")
        self._log(f"Started watching: {source_path}")
        self.status_label.configure(text="Watch mode active")
    
    def _stop_watch(self) -> None:
        """Stop watching the directory."""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        
        self._is_watching = False
        self.watch_btn.configure(text="👀 Start Watch Mode")
        self._log("Stopped watching")
        self.status_label.configure(text="Ready")
    
    def _on_watch_organize(self, result: OrganizeResult) -> None:
        """Handle file organization from watch mode."""
        for action in result.actions:
            self._log(f"Auto-organized: {action.source.name} → {action.destination.parent.name}/")
    
    def _find_duplicates(self) -> None:
        """Find duplicate files in the directory."""
        source_path = self._get_source_path()
        if not source_path:
            return
        
        self.duplicates_btn.configure(state="disabled")
        
        def duplicate_thread():
            try:
                self.after(0, self._log, "Scanning for duplicates...")
                
                detector = DuplicateDetector(self.config)
                groups = detector.find_duplicates(
                    directory=source_path,
                    recursive=self.recursive_var.get(),
                    progress_callback=lambda c, t, f: self.after(
                        0, self._update_progress, c, t, f
                    )
                )
                
                self.after(0, self._on_duplicates_found, groups)
                
            except Exception as e:
                self.after(0, self._log, f"Error: {str(e)}")
            finally:
                self.after(0, lambda: self.duplicates_btn.configure(state="normal"))
        
        thread = threading.Thread(target=duplicate_thread, daemon=True)
        thread.start()
    
    def _on_duplicates_found(self, groups: list) -> None:
        """Handle duplicate detection completion."""
        self.progress_bar.set(1)
        
        if not groups:
            self._log("No duplicates found!")
            messagebox.showinfo("Duplicates", "No duplicate files found.")
            return
        
        detector = DuplicateDetector(self.config)
        stats = detector.get_duplicate_stats(groups)
        
        self._log(f"Found {stats['total_groups']} groups of duplicates")
        self._log(f"Total duplicate files: {stats['total_duplicate_files']}")
        self._log(f"Wasted space: {stats['total_wasted_mb']} MB")
        
        for group in groups[:10]:
            self._log(f"  Duplicate ({len(group.files)} copies, {group.size} bytes):")
            for f in group.files[:3]:
                self._log(f"    - {f}")
            if len(group.files) > 3:
                self._log(f"    ... and {len(group.files) - 3} more")
        
        self.status_label.configure(text=f"Found {stats['total_groups']} duplicate groups")
    
    def _undo_last(self) -> None:
        """Undo the last organization action."""
        undone = self.organizer.undo_last(count=1)
        
        if undone:
            for action in undone:
                self._log(f"Undone: {action.destination.name} → {action.source.parent.name}/")
            self.status_label.configure(text="Undo complete")
        else:
            self._log("Nothing to undo")
            messagebox.showinfo("Undo", "No actions to undo.")


def run_gui() -> None:
    """Run the GUI application."""
    app = SmartFileOrganizerGUI()
    app.mainloop()
