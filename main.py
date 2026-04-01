"""
Main entry point for Smart File Organizer.
"""

import argparse
import sys
from pathlib import Path

from .config import Config
from .organizer import FileOrganizer
from .watcher import DirectoryWatcher
from .duplicate_detector import DuplicateDetector
from .gui import run_gui


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Smart File Organizer - Intelligently organize your files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Launch GUI
  %(prog)s --path ~/Downloads           # Organize Downloads folder
  %(prog)s --path ~/Downloads --mode watch   # Watch mode
  %(prog)s --path ~/Downloads --sort-by date # Organize by date
        """
    )
    
    parser.add_argument(
        "--path", "-p",
        type=str,
        help="Path to the folder to organize"
    )
    
    parser.add_argument(
        "--dest", "-d",
        type=str,
        help="Destination folder (defaults to source)"
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["organize", "watch", "duplicates"],
        default="organize",
        help="Operation mode (default: organize)"
    )
    
    parser.add_argument(
        "--sort-by", "-s",
        choices=["type", "date", "both"],
        default="type",
        help="Sort method (default: type)"
    )
    
    parser.add_argument(
        "--rename", "-r",
        action="store_true",
        help="Enable smart file renaming"
    )
    
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include subdirectories"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without moving files"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to custom config file"
    )
    
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Force launch GUI mode"
    )
    
    return parser.parse_args()


def run_cli(args) -> int:
    """Run in command-line mode."""
    # Load configuration
    config = Config.load(args.config)
    
    source_path = Path(args.path).resolve()
    dest_path = Path(args.dest).resolve() if args.dest else None
    
    if not source_path.exists():
        print(f"Error: Path does not exist: {source_path}")
        return 1
    
    if args.mode == "organize":
        organizer = FileOrganizer(config)
        
        print(f"Organizing: {source_path}")
        if args.dry_run:
            print("(Dry run - no files will be moved)")
        
        result = organizer.organize(
            source_dir=source_path,
            dest_dir=dest_path,
            sort_by=args.sort_by,
            rename_files=args.rename,
            recursive=args.recursive,
            dry_run=args.dry_run,
            progress_callback=lambda c, t, f: print(f"  [{c}/{t}] {Path(f).name}")
        )
        
        print(f"\nComplete!")
        print(f"  Files processed: {result.total_processed}")
        print(f"  Errors: {result.total_errors}")
        print(f"  Skipped: {len(result.skipped)}")
        
        return 0 if result.success else 1
    
    elif args.mode == "watch":
        print(f"Watching: {source_path}")
        print("Press Ctrl+C to stop...")
        
        def on_organize(result):
            for action in result.actions:
                print(f"  Organized: {action.source.name} → {action.destination.parent.name}/")
        
        watcher = DirectoryWatcher(
            config=config,
            watch_dir=source_path,
            dest_dir=dest_path,
            sort_by=args.sort_by,
            rename_files=args.rename,
            on_organize=on_organize
        )
        
        watcher.start()
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping watcher...")
            watcher.stop()
        
        return 0
    
    elif args.mode == "duplicates":
        print(f"Scanning for duplicates: {source_path}")
        
        detector = DuplicateDetector(config)
        groups = detector.find_duplicates(
            directory=source_path,
            recursive=args.recursive,
            progress_callback=lambda c, t, f: print(f"  [{c}/{t}] Scanning...", end="\r")
        )
        
        print("\n")
        
        if not groups:
            print("No duplicates found!")
            return 0
        
        stats = detector.get_duplicate_stats(groups)
        
        print(f"Found {stats['total_groups']} groups of duplicates")
        print(f"Total duplicate files: {stats['total_duplicate_files']}")
        print(f"Wasted space: {stats['total_wasted_mb']} MB")
        print()
        
        for i, group in enumerate(groups[:20], 1):
            print(f"Group {i} ({len(group.files)} files, {group.size:,} bytes each):")
            for f in group.files:
                print(f"  - {f}")
            print()
        
        if len(groups) > 20:
            print(f"... and {len(groups) - 20} more groups")
        
        return 0
    
    return 1


def main():
    """Main entry point."""
    args = parse_args()
    
    # If no path specified or --gui flag, launch GUI
    if args.gui or args.path is None:
        run_gui()
        return 0
    
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
