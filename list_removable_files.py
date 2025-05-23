#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Files and directories that must be kept
ESSENTIAL_FILES = [
    # Core application files
    "scripts/high_current.py", 
    "scripts/tracking_manager.py",
    "scripts/historical_analyzer.py",
    "scripts/report_generator.py",
    "auto_tracker.py",
    "enhanced_report.py",
    
    # Configuration
    "requirements.txt",
    ".github/workflows/unified_daily_report.yml",
    
    # Documentation
    "README.md",
    "TRACKING_GUIDE.md",
    "AUTO_TRACKER_README.md",
    "UNIFIED_WORKFLOW_GUIDE.md",
    "DB_MIGRATION_PLAN.md",
    "PROJECT_COMPLETION.md"
]

ESSENTIAL_DIRS = [
    "scripts",
    "Data",
    "results/live_signals",
    "tracking",
    ".github/workflows"
]

def is_essential_file(rel_path):
    """Check if a file is essential based on its path"""
    # Check if the file is explicitly in the essential files list
    if rel_path in ESSENTIAL_FILES:
        return True
    
    # Check if the file is in an essential directory
    for essential_dir in ESSENTIAL_DIRS:
        if rel_path.startswith(essential_dir + os.sep):
            return True
            
    return False

def list_removable_files(directory):
    """List all files that can be safely deleted"""
    removable_files = []
    
    # Get the root directory path
    root_dir = Path(directory)
    
    # Walk through all files
    for path in root_dir.rglob('*'):
        if path.is_file():
            # Convert to relative path
            rel_path = str(path.relative_to(root_dir))
            
            # Replace backslashes with forward slashes for consistency
            rel_path = rel_path.replace('\\', '/')
            
            # Check if it's not an essential file
            if not is_essential_file(rel_path):
                # Skip .git files
                if '.git/' not in rel_path:
                    removable_files.append(rel_path)
    
    return removable_files

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get list of removable files
    removable = list_removable_files(script_dir)
    
    # Count by extension
    extension_counts = {}
    for file in removable:
        ext = os.path.splitext(file)[1]
        extension_counts[ext] = extension_counts.get(ext, 0) + 1
    
    # Print summary
    print(f"Found {len(removable)} files that can be safely deleted:")
    print("\nBreakdown by file type:")
    for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
        ext_name = ext if ext else "(no extension)"
        print(f"  {ext_name}: {count} files")
    
    # Print all files
    print("\nList of files that can be deleted:")
    for file in sorted(removable):
        print(f"  {file}")
    
    print("\nTo delete these files, run the cleanup_project.py script.")
