#!/usr/bin/env python3
import os
import sys
import shutil

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

# Tests and development files that can be deleted in production
# But might want to keep for future development
DEVELOPMENT_FILES = [
    "tests",
    "*.sh",
    "*.py",
    "__pycache__",
    ".github/workflows_backup"
]

def is_essential_file(path, base_dir):
    """Check if a file is in the essential files list"""
    rel_path = os.path.relpath(path, base_dir)
    
    # Check if the file is explicitly in the essential files list
    if rel_path in ESSENTIAL_FILES:
        return True
    
    # Check if the file is in an essential directory
    for essential_dir in ESSENTIAL_DIRS:
        essential_dir_path = os.path.normpath(os.path.join(base_dir, essential_dir))
        if path.startswith(essential_dir_path):
            return True
            
    return False

def cleanup_directory(directory):
    """Remove non-essential files from the directory"""
    print(f"Starting cleanup of {directory}...")
    
    files_deleted = 0
    dirs_deleted = 0
    
    # First get a list of all files
    all_files = []
    for root, dirs, files in os.walk(directory):
        # Skip .git directory
        if '.git' in dirs:
            dirs.remove('.git')
            
        for file in files:
            all_files.append(os.path.join(root, file))
    
    # Then delete non-essential files
    for file_path in all_files:
        if not is_essential_file(file_path, directory):
            try:
                os.remove(file_path)
                files_deleted += 1
                print(f"Deleted file: {os.path.relpath(file_path, directory)}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    
    # Now walk the directory tree bottom-up to remove empty directories
    for root, dirs, files in os.walk(directory, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            # Check if directory is empty and not essential
            if not os.listdir(dir_path) and not is_essential_file(dir_path, directory):
                try:
                    os.rmdir(dir_path)
                    dirs_deleted += 1
                    print(f"Deleted empty directory: {os.path.relpath(dir_path, directory)}")
                except Exception as e:
                    print(f"Error deleting directory {dir_path}: {e}")
    
    print(f"Cleanup completed. {files_deleted} files and {dirs_deleted} directories deleted.")

if __name__ == "__main__":
    # Confirm before proceeding
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(script_dir)
    
    print(f"This will delete all non-essential files from {project_dir}")
    print("Essential files and directories that will be KEPT:")
    for f in ESSENTIAL_FILES:
        print(f"  - {f}")
    print("\nEssential directories that will be PRESERVED (and their contents):")
    for d in ESSENTIAL_DIRS:
        print(f"  - {d}")
    
    confirm = input("\nAre you sure you want to proceed? (yes/no): ")
    
    if confirm.lower() in ('yes', 'y'):
        cleanup_directory(project_dir)
        print("\nCleanup completed successfully.")
        print("The project is now ready for deployment to GitHub.")
    else:
        print("Cleanup cancelled.")
