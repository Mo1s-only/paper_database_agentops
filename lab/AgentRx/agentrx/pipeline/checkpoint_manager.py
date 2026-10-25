#!/usr/bin/env python3
"""
Checkpoint Manager Utility

This script helps manage the checkpoint file for the symbolic invariants pipeline.
It allows you to view, reset, or modify the list of processed task IDs for specific result directories.
"""

import os
import json
import argparse
from datetime import datetime
import glob


def get_results_directory(results_dir):
    """
    Get the full path to a results directory.
    
    Args:
        results_dir (str): Name of the results directory (e.g., 'violation_results_20250117_143022')
        
    Returns:
        str: Full path to the results directory
        
    Raises:
        FileNotFoundError: If the directory doesn't exist
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, results_dir)
    
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Results directory not found: {full_path}")
    
    return full_path


def list_results_directories():
    """List all available violation_results_* directories."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dirs = glob.glob(os.path.join(script_dir, "violation_results_*"))
    
    if not results_dirs:
        print("No violation_results_* directories found.")
        return []
    
    print("\n" + "=" * 80)
    print("AVAILABLE RESULTS DIRECTORIES")
    print("=" * 80)
    
    dirs_info = []
    for full_path in sorted(results_dirs, reverse=True):
        dir_name = os.path.basename(full_path)
        checkpoint_path = os.path.join(full_path, 'metrics_output', 'checkpoint.json')
        
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r') as f:
                    data = json.load(f)
                    num_tasks = len(data.get('processed_task_ids', []))
                    last_updated = data.get('last_updated', 'Unknown')
                    status = f"{num_tasks} tasks processed"
            except:
                status = "Checkpoint exists (error reading)"
        else:
            status = "No checkpoint"
        
        print(f"  {dir_name:<40} | {status}")
        dirs_info.append(dir_name)
    
    print("=" * 80 + "\n")
    return dirs_info


def get_checkpoint_path(results_dir):
    """Get the checkpoint file path for a specific results directory."""
    full_path = get_results_directory(results_dir)
    return os.path.join(full_path, 'metrics_output', 'checkpoint.json')


def load_checkpoint(results_dir):
    """Load and return the checkpoint data for a specific results directory."""
    checkpoint_path = get_checkpoint_path(results_dir)
    
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return None
    else:
        print(f"No checkpoint file found at: {checkpoint_path}")
        return None


def save_checkpoint(results_dir, processed_task_ids, backup=True):
    """Save checkpoint for a specific results directory with optional backup."""
    checkpoint_path = get_checkpoint_path(results_dir)
    
    if backup and os.path.exists(checkpoint_path):
        backup_path = f"{checkpoint_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(checkpoint_path, backup_path)
        print(f"Backed up existing checkpoint to: {backup_path}")
    
    checkpoint_data = {
        'processed_task_ids': sorted(list(processed_task_ids)),
        'last_updated': datetime.now().isoformat()
    }
    
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)
    print(f"Checkpoint saved: {len(processed_task_ids)} task IDs")


def view_checkpoint(results_dir):
    """Display the current checkpoint status for a specific results directory."""
    data = load_checkpoint(results_dir)
    if data:
        processed_ids = data.get('processed_task_ids', [])
        last_updated = data.get('last_updated', 'Unknown')
        print("\n" + "=" * 60)
        print(f"CHECKPOINT STATUS: {results_dir}")
        print("=" * 60)
        print(f"Last Updated: {last_updated}")
        print(f"Total Processed Tasks: {len(processed_ids)}")
        print(f"\nProcessed Task IDs: {sorted(processed_ids)}")
        print("=" * 60 + "\n")


def reset_checkpoint(results_dir):
    """Reset the checkpoint file for a specific results directory."""
    checkpoint_path = get_checkpoint_path(results_dir)
    
    if os.path.exists(checkpoint_path):
        backup_path = f"{checkpoint_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(checkpoint_path, backup_path)
        print(f"Checkpoint reset. Backup saved to: {backup_path}")
    else:
        print("No checkpoint file to reset.")


def add_task_ids(results_dir, task_ids):
    """Add task IDs to the checkpoint for a specific results directory."""
    data = load_checkpoint(results_dir)
    if data:
        processed_ids = set(data.get('processed_task_ids', []))
    else:
        processed_ids = set()
    
    processed_ids.update(task_ids)
    save_checkpoint(results_dir, processed_ids)
    print(f"Added task IDs: {sorted(task_ids)}")


def remove_task_ids(results_dir, task_ids):
    """Remove task IDs from the checkpoint and clear corresponding files for a specific results directory."""
    data = load_checkpoint(results_dir)
    if not data:
        print("No checkpoint file found.")
        return
    
    processed_ids = set(data.get('processed_task_ids', []))
    processed_ids.difference_update(task_ids)
    save_checkpoint(results_dir, processed_ids)
    print(f"Removed task IDs from checkpoint: {sorted(task_ids)}")
    
    # Clear corresponding files in the specific results directory
    results_path = get_results_directory(results_dir)
    
    for task_id in task_ids:
        # Path to dynamic invariants module file
        module_file = os.path.join(results_path, 'invariants_module', 'dynamic_invariants_module', f"task_{task_id}.py")
        if os.path.exists(module_file):
            try:
                with open(module_file, 'w') as f:
                    pass  # Clear the file
                print(f"  Cleared: {module_file}")
            except Exception as e:
                print(f"  Warning: Could not clear {module_file}: {e}")
        
        # Path to dynamic invariants output file
        output_file = os.path.join(results_path, 'invariant_outputs', 'dynamic_invariants_output', f"task_{task_id}.txt")
        if os.path.exists(output_file):
            try:
                with open(output_file, 'w') as f:
                    pass  # Clear the file
                print(f"  Cleared: {output_file}")
            except Exception as e:
                print(f"  Warning: Could not clear {output_file}: {e}")
        
        # Path to judge context file
        judge_context_file = os.path.join(results_path, 'judge_context', f"task_{task_id}.txt")
        if os.path.exists(judge_context_file):
            try:
                with open(judge_context_file, 'w') as f:
                    pass  # Clear the file
                print(f"  Cleared: {judge_context_file}")
            except Exception as e:
                print(f"  Warning: Could not clear {judge_context_file}: {e}")
        
        # Path to metrics output file
        metrics_file = os.path.join(results_path, 'metrics_output', f"task_{task_id}.json")
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'w') as f:
                    pass  # Clear the file
                print(f"  Cleared: {metrics_file}")
            except Exception as e:
                print(f"  Warning: Could not clear {metrics_file}: {e}")
        
        # Path to deduplicated violations file
        dedup_file = os.path.join(results_path, 'deduplicated_violations', f"task_{task_id}.json")
        if os.path.exists(dedup_file):
            try:
                with open(dedup_file, 'w') as f:
                    pass  # Clear the file
                print(f"  Cleared: {dedup_file}")
            except Exception as e:
                print(f"  Warning: Could not clear {dedup_file}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Manage checkpoint for symbolic invariants pipeline with specific results directories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available results directories
  python checkpoint_manager.py list
  
  # View checkpoint status for a specific results directory
  python checkpoint_manager.py view violation_results_20250117_143022
  
  # Reset checkpoint for a specific results directory (with backup)
  python checkpoint_manager.py reset violation_results_20250117_143022
  
  # Add task IDs to checkpoint for a specific results directory
  python checkpoint_manager.py add violation_results_20250117_143022 2 3 4
  
  # Remove task IDs from checkpoint for a specific results directory
  python checkpoint_manager.py remove violation_results_20250117_143022 2 3
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all available results directories')
    
    # View command
    view_parser = subparsers.add_parser('view', help='View checkpoint status for a results directory')
    view_parser.add_argument('results_dir', help='Results directory name (e.g., violation_results_20250117_143022)')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset checkpoint (creates backup)')
    reset_parser.add_argument('results_dir', help='Results directory name (e.g., violation_results_20250117_143022)')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add task IDs to checkpoint')
    add_parser.add_argument('results_dir', help='Results directory name (e.g., violation_results_20250117_143022)')
    add_parser.add_argument('task_ids', type=int, nargs='+', help='Task IDs to add')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove task IDs from checkpoint')
    remove_parser.add_argument('results_dir', help='Results directory name (e.g., violation_results_20250117_143022)')
    remove_parser.add_argument('task_ids', type=int, nargs='+', help='Task IDs to remove')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            list_results_directories()
        elif args.command == 'view':
            view_checkpoint(args.results_dir)
        elif args.command == 'reset':
            confirm = input(f"Are you sure you want to reset the checkpoint for {args.results_dir}? (yes/no): ")
            if confirm.lower() == 'yes':
                reset_checkpoint(args.results_dir)
            else:
                print("Reset cancelled.")
        elif args.command == 'add':
            add_task_ids(args.results_dir, args.task_ids)
        elif args.command == 'remove':
            remove_task_ids(args.results_dir, args.task_ids)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nRun 'python checkpoint_manager.py list' to see available directories.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
