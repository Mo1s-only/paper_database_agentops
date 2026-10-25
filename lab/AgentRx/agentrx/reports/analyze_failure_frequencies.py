"""
Failure Case Frequency Analysis

This script analyzes the output results JSON file to compute and visualize
the frequency distribution of predicted and ground truth failure cases.
"""

import argparse
import json
import matplotlib.pyplot as plt
import numpy as np
import os
from collections import Counter

# Define the failure case mapping
FAILURE_CASES = {
    1: "Instruction/Plan\nAdherence",
    2: "Invention of\nNew Info",
    3: "Invalid\nInvocation",
    4: "Misinterpretation\nof Tool Output",
    5: "Intent-Plan\nMisalignment",
    6: "Underspecified\nUser Intent",
    7: "Intent Not\nSupported",
    8: "Guardrails\nTriggered",
    9: "System\nFailure",
    10: "Inconclusive"
}

FAILURE_CASES_FULL = {
    1: "Instruction/Plan Adherence Failure",
    2: "Invention of New Information",
    3: "Invalid Invocation",
    4: "Misinterpretation of Tool Output",
    5: "Intent-Plan Misalignment",
    6: "Underspecified User Intent",
    7: "Intent Not Supported",
    8: "Guardrails Triggered",
    9: "System Failure",
    10: "Inconclusive"
}

def extract_failure_case_number(failure_case_str):
    """
    Extract the numeric failure case from string representation.
    
    Args:
        failure_case_str (str or int): String like "FailureCase.INVENTION_OF_NEW_INFORMATION",
                                       numeric string like "4", or integer like 4
        
    Returns:
        int: Numeric failure case (1-10)
    """
    # Handle integer input directly
    if isinstance(failure_case_str, int):
        return failure_case_str if 1 <= failure_case_str <= 10 else 10
    
    # Handle numeric strings (e.g., "4", "1")
    failure_case_str = str(failure_case_str).strip()
    if failure_case_str.isdigit():
        num = int(failure_case_str)
        return num if 1 <= num <= 10 else 10
    
    # Map enum names to numbers
    enum_to_number = {
        "INSTRUCTION_OR_PLAN_ADHERENCE_FAILURE": 1,
        "INVENTION_OF_NEW_INFORMATION": 2,
        "INVALID_INVOCATION": 3,
        "MISINTERPRETATION_OF_TOOL_OUTPUT": 4,
        "INTENT_PLAN_MISALIGNMENT": 5,
        "UNDERSPECIFIED_USER_INTENT": 6,
        "INTENT_NOT_SUPPORTED": 7,
        "GUARDRAILS_TRIGGERED": 8,
        "SYSTEM_FAILURE": 9,
        "INCONCLUSIVE": 10
    }
    
    # Extract the enum name from the string (e.g., "FailureCase.INVALID_INVOCATION")
    if "." in failure_case_str:
        enum_name = failure_case_str.split(".")[-1]
        return enum_to_number.get(enum_name, 10)  # Default to inconclusive if not found
    
    # Try direct enum name match (e.g., "INVALID_INVOCATION")
    upper_str = failure_case_str.upper().replace(" ", "_").replace("-", "_")
    if upper_str in enum_to_number:
        return enum_to_number[upper_str]
    
    return 10  # Default to inconclusive

def load_and_analyze_json(json_file_path):
    """
    Load JSON file and extract failure case frequencies.
    
    Args:
        json_file_path (str): Path to the JSON file
        
    Returns:
        tuple: (predicted_frequencies, ground_truth_frequencies)
    """
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    detailed_results = data['detailed_results']
    
    # Initialize frequency counters for all 10 cases
    predicted_freq = {i: 0 for i in range(1, 11)}
    gt_freq = {i: 0 for i in range(1, 11)}
    
    has_gt = False
    # Count frequencies
    for result in detailed_results:
        # Extract predicted failure case: prefer most_common_failure, fall back to
        # the first entry in the failures list when no ground truth was provided.
        if 'most_common_failure' in result:
            predicted_case_str = result['most_common_failure']
        elif result.get('failures'):
            predicted_case_str = str(result['failures'][0].get('failure_case', 0))
        else:
            continue
        predicted_case_num = extract_failure_case_number(predicted_case_str)
        predicted_freq[predicted_case_num] += 1
        
        # Extract ground truth failure case (only when GT is available)
        if 'gt_failure_case' in result:
            has_gt = True
            gt_case_str = result['gt_failure_case']
            gt_case_num = extract_failure_case_number(gt_case_str)
            gt_freq[gt_case_num] += 1
    
    return predicted_freq, gt_freq if has_gt else None

def plot_predicted_frequency(predicted_freq, output_file='predicted_failure_frequency.png'):
    """
    Create bar graph for predicted failure case frequencies.
    
    Args:
        predicted_freq (dict): Dictionary of failure case frequencies
        output_file (str): Output file name for the plot
    """
    plt.figure(figsize=(16, 7))
    
    cases = list(range(1, 11))
    frequencies = [predicted_freq[i] for i in cases]
    labels = [FAILURE_CASES[i] for i in cases]
    
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    bars = plt.bar(labels, frequencies, color=colors, edgecolor='black', alpha=0.8)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontweight='bold')
    
    plt.xlabel('Failure Categories', fontsize=12, fontweight='bold')
    plt.ylabel('Frequency', fontsize=12, fontweight='bold')
    plt.title('Predicted Failure Case Frequency Distribution', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Predicted frequency plot saved to {output_file}")
    plt.close()

def plot_ground_truth_frequency(gt_freq, output_file='ground_truth_failure_frequency.png'):
    """
    Create bar graph for ground truth failure case frequencies.
    
    Args:
        gt_freq (dict): Dictionary of failure case frequencies
        output_file (str): Output file name for the plot
    """
    plt.figure(figsize=(16, 7))
    
    cases = list(range(1, 11))
    frequencies = [gt_freq[i] for i in cases]
    labels = [FAILURE_CASES[i] for i in cases]
    
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    bars = plt.bar(labels, frequencies, color=colors, edgecolor='black', alpha=0.8)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontweight='bold')
    
    plt.xlabel('Failure Categories', fontsize=12, fontweight='bold')
    plt.ylabel('Frequency', fontsize=12, fontweight='bold')
    plt.title('Ground Truth Failure Case Frequency Distribution', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Ground truth frequency plot saved to {output_file}")
    plt.close()

def plot_comparison(predicted_freq, gt_freq, output_file='failure_frequency_comparison.png'):
    """
    Create side-by-side comparison bar graph for predicted vs ground truth.
    
    Args:
        predicted_freq (dict): Dictionary of predicted failure case frequencies
        gt_freq (dict): Dictionary of ground truth failure case frequencies
        output_file (str): Output file name for the plot
    """
    plt.figure(figsize=(18, 8))
    
    cases = list(range(1, 11))
    predicted_frequencies = [predicted_freq[i] for i in cases]
    gt_frequencies = [gt_freq[i] for i in cases]
    labels = [FAILURE_CASES[i] for i in cases]
    
    x = np.arange(len(cases))
    width = 0.35
    
    bars1 = plt.bar(x - width/2, predicted_frequencies, width, 
                    label='Predicted', color='steelblue', edgecolor='black', alpha=0.8)
    bars2 = plt.bar(x + width/2, gt_frequencies, width, 
                    label='Ground Truth', color='coral', edgecolor='black', alpha=0.8)
    
    # Add value labels on top of bars
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.xlabel('Failure Categories', fontsize=12, fontweight='bold')
    plt.ylabel('Frequency', fontsize=12, fontweight='bold')
    plt.title('Predicted vs Ground Truth Failure Case Frequency Comparison', 
              fontsize=14, fontweight='bold')
    plt.xticks(x, labels, rotation=45, ha='right', fontsize=9)
    plt.legend(fontsize=11)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Comparison plot saved to {output_file}")
    plt.close()

def print_frequency_summary(predicted_freq, gt_freq):
    """
    Print a summary of the frequency distributions.
    
    Args:
        predicted_freq (dict): Dictionary of predicted failure case frequencies
        gt_freq (dict): Dictionary of ground truth failure case frequencies
    """
    print("\n" + "="*80)
    print("FAILURE CASE FREQUENCY ANALYSIS SUMMARY")
    print("="*80)
    
    total_predicted = sum(predicted_freq.values())
    total_gt = sum(gt_freq.values())
    
    print(f"\nTotal entries analyzed: {total_predicted}")
    
    print("\n{:<5} {:<45} {:>10} {:>10}".format(
        "Case", "Failure Category", "Predicted", "GT"))
    print("-" * 80)
    
    for i in range(1, 11):
        case_name = FAILURE_CASES_FULL[i]
        pred_count = predicted_freq[i]
        gt_count = gt_freq[i]
        print(f"{i:<5} {case_name:<45} {pred_count:>10} {gt_count:>10}")
    
    print("-" * 80)
    print(f"{'TOTAL':<51} {total_predicted:>10} {total_gt:>10}")
    print("="*80)
    
    # Calculate accuracy
    correct_predictions = sum(1 for i in range(1, 11) 
                              if predicted_freq[i] == gt_freq[i])
    
    print(f"\nNote: This is frequency comparison, not per-task accuracy.")
    print(f"Cases with matching frequency: {correct_predictions}/10")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Analyze failure category frequencies from judge output.")
    parser.add_argument('json_file', help='Path to the output results JSON file')
    args = parser.parse_args()
    json_file_path = args.json_file
    
    print(f"Loading data from {json_file_path}...")
    
    # Extract filename without extension to create subdirectory
    json_filename = os.path.basename(json_file_path)
    json_filename_without_ext = os.path.splitext(json_filename)[0]
    
    # Create output directory: output_results/plots_<json_filename>
    output_dir = os.path.join('output_results', f'plots_{json_filename_without_ext}')
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Load and analyze the JSON file
    predicted_freq, gt_freq = load_and_analyze_json(json_file_path)
    
    # Print summary
    print_frequency_summary(predicted_freq, gt_freq)
    
    # Generate plots in the subdirectory
    print("\nGenerating visualizations...")
    plot_predicted_frequency(predicted_freq, 
                             output_file=os.path.join(output_dir, 'predicted_failure_frequency.png'))
    plot_ground_truth_frequency(gt_freq, 
                                output_file=os.path.join(output_dir, 'ground_truth_failure_frequency.png'))
    plot_comparison(predicted_freq, gt_freq, 
                   output_file=os.path.join(output_dir, 'failure_frequency_comparison.png'))
    
    print(f"\nAnalysis complete! All plots have been saved to {output_dir}/")


if __name__ == "__main__":
    main()
