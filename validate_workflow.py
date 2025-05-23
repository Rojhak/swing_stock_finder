#!/usr/bin/env python3
import yaml
import sys

def validate_yaml(file_path):
    try:
        with open(file_path, 'r') as file:
            yaml_content = yaml.safe_load(file)
            print(f"✓ YAML file is valid: {file_path}")
            print(f"\nWorkflow name: {yaml_content.get('name', 'Unnamed')}")
            
            # Print triggers
            if 'on' in yaml_content:
                print("\nTriggers:")
                triggers = yaml_content['on']
                if isinstance(triggers, dict):
                    for trigger, config in triggers.items():
                        print(f"  - {trigger}: {config}")
                else:
                    print(f"  - {triggers}")
            
            # Print jobs
            if 'jobs' in yaml_content:
                print("\nJobs:")
                for job_name, job in yaml_content['jobs'].items():
                    print(f"  - {job_name}")
                    if 'steps' in job:
                        print(f"    Steps: {len(job['steps'])}")
            
            return True
    except yaml.YAMLError as e:
        print(f"❌ Error: YAML is invalid: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_workflow.py <path_to_yaml_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if validate_yaml(file_path):
        sys.exit(0)
    else:
        sys.exit(1)
