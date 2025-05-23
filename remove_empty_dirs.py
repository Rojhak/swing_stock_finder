#!/usr/bin/env python3
import os
from pathlib import Path

def remove_empty_dirs(directory):
    """Remove empty directories recursively"""
    count = 0
    base_path = Path(directory)
    
    # Walk bottom-up so we process child directories first
    for dirpath, dirnames, filenames in os.walk(str(base_path), topdown=False):
        # Skip .git directories
        if '.git' in Path(dirpath).parts:
            continue
            
        if not filenames and not dirnames:
            rel_path = os.path.relpath(dirpath, directory)
            # Don't delete the root directory
            if rel_path != '.':
                try:
                    os.rmdir(dirpath)
                    print(f"Removed empty directory: {rel_path}")
                    count += 1
                except Exception as e:
                    print(f"Error removing directory {rel_path}: {e}")
    
    print(f"\nRemoved {count} empty directories.")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Removing empty directories in: {script_dir}")
    remove_empty_dirs(script_dir)
    print("Project is now cleaned up and ready for GitHub deployment.")
