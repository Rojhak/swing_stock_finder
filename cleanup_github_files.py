#!/usr/bin/env python3
import os
import shutil

# Remove backup and disabled workflow files
def cleanup_github_files():
    """Clean up unnecessary GitHub workflow files"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    github_dir = os.path.join(script_dir, '.github')
    
    # Check if .github directory exists
    if not os.path.exists(github_dir):
        print(".github directory not found")
        return
    
    # Remove the entire workflows_backup directory
    backup_dir = os.path.join(github_dir, 'workflows_backup')
    if os.path.exists(backup_dir):
        try:
            shutil.rmtree(backup_dir)
            print(f"Removed directory: {os.path.relpath(backup_dir, script_dir)}")
        except Exception as e:
            print(f"Error removing directory {backup_dir}: {e}")
    
    # Remove disabled workflow files
    workflows_dir = os.path.join(github_dir, 'workflows')
    if os.path.exists(workflows_dir):
        for file in os.listdir(workflows_dir):
            # Keep only unified_daily_report.yml and remove everything else
            if file != 'unified_daily_report.yml':
                file_path = os.path.join(workflows_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Removed file: {os.path.relpath(file_path, script_dir)}")
                    except Exception as e:
                        print(f"Error removing file {file_path}: {e}")
    
    print("\nGitHub workflow files cleaned up successfully.")

if __name__ == "__main__":
    print("Cleaning up GitHub workflow files...")
    cleanup_github_files()
    
    # Also remove this file
    script_path = os.path.abspath(__file__)
    print(f"Removing self ({os.path.basename(script_path)})...")
    try:
        os.remove(script_path)
        print("Self-deletion successful.")
    except Exception as e:
        print(f"Error removing self: {e}")
