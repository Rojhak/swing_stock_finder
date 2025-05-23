#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

# Files and directories that are essential for production
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

# Directories that are essential for production
ESSENTIAL_DIRS = [
    "scripts",
    "Data",
    "results/live_signals",
    "tracking",
    ".github/workflows"
]

# Files that should be kept for development but could be removed for production
DEVELOPMENT_FILES = [
    "tests/scripts/test_tracking_manager.py",  # Keep main test files for future testing
    "tests/scripts/test_high_current.py",
    "tests/scripts/__init__.py",
    "tests/__init__.py",
    "validate_workflow.py",  # Keep some utility scripts
    "test_signal_tracking.py"
]

# Files to be explicitly deleted (temporary/debug files)
TEMP_DEBUG_FILES = [
    "*.bak",
    "debug_*.py",
    "debug_*.sh",
    "test_email*.py",
    "direct_report.txt",
    "report*.txt", 
    "fix_report.py",
    "*_fixed_report.txt",
    ".github/workflows/*.yml.disabled",
    ".github/workflows_backup/*",
]

def should_delete_file(rel_path):
    """Determine if a file should be deleted"""
    # Keep essential files
    if rel_path in ESSENTIAL_FILES:
        return False
    
    # Keep files in essential directories
    for essential_dir in ESSENTIAL_DIRS:
        if rel_path.startswith(essential_dir) and not any(
            rel_path.startswith(f"{essential_dir}/") and 
            rel_path.endswith(ext.replace("*", "")) 
            for ext in [".bak", "*.pyc"]
        ):
            return False
    
    # Keep development files
    if rel_path in DEVELOPMENT_FILES:
        return False
    
    # Delete temporary/debug files
    for pattern in TEMP_DEBUG_FILES:
        if pattern.startswith("*") and rel_path.endswith(pattern[1:]):
            return True
        elif pattern.endswith("*") and rel_path.startswith(pattern[:-1]):
            return True
        elif "*" in pattern:
            # Simple wildcard matching - not as robust as glob but works for our case
            prefix, suffix = pattern.split("*", 1)
            if rel_path.startswith(prefix) and rel_path.endswith(suffix):
                return True
    
    # Default: delete if not explicitly kept
    return True

def cleanup_files():
    """Clean up unnecessary files based on our rules"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = Path(script_dir)
    
    files_to_delete = []
    
    # First identify all files to delete
    for path in root_dir.rglob('*'):
        if path.is_file():
            rel_path = str(path.relative_to(root_dir)).replace('\\', '/')
            
            # Skip .git files
            if '.git/' in rel_path:
                continue
                
            # Check if file should be deleted
            if should_delete_file(rel_path):
                files_to_delete.append((path, rel_path))
    
    # Show files to be deleted
    print(f"The following {len(files_to_delete)} files will be deleted:")
    for _, rel_path in sorted(files_to_delete):
        print(f"  - {rel_path}")
    
    # Confirm before deletion
    confirm = input("\nProceed with deletion? (yes/no): ")
    if confirm.lower() not in ('yes', 'y'):
        print("Deletion cancelled.")
        return
    
    # Delete the files
    for path, rel_path in files_to_delete:
        try:
            os.remove(path)
            print(f"Deleted: {rel_path}")
        except Exception as e:
            print(f"Error deleting {rel_path}: {e}")
    
    # Remove empty directories (except .git)
    print("\nRemoving empty directories...")
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # Skip .git directories
        if '.git' in dirpath.parts:
            continue
            
        if not filenames and not dirnames:
            try:
                rel_dir = os.path.relpath(dirpath, root_dir)
                # Don't remove root directory
                if rel_dir != '.':
                    os.rmdir(dirpath)
                    print(f"Removed empty directory: {rel_dir}")
            except Exception as e:
                print(f"Error removing directory {dirpath}: {e}")
    
    print("\nCleanup completed successfully.")
    print("The project is now ready for GitHub deployment.")

if __name__ == "__main__":
    print("Project Cleanup Tool - Prepare for GitHub Deployment")
    print("----------------------------------------------------")
    print("This tool will remove unnecessary files to prepare for GitHub deployment.")
    print("It will keep essential files and directories needed for the application to run.")
    
    cleanup_files()
