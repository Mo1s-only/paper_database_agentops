import inspect
import agentrx.pipeline.globals as g
import os
import re
from typing import Dict, Optional
import textwrap
import html
import ast
import json

def format_previous_dynamic_assertions(assertions):
    """Format previous assertions list for display in prompt"""
    if not assertions:
        return "None yet."
    
    formatted = []
    for i, assertion in enumerate(assertions, 1):
        formatted.append(f"{i}. Step {assertion['step_number']}: {assertion['assertion_name']}")
        formatted.append(f"   Logic: {assertion['check_logic']}")
        formatted.append(f"   Violation: {assertion['violation_condition']}")
        formatted.append("")  # Empty line for separation
    
    return "\n".join(formatted)

def format_previous_static_assertions(static_invariants):
    """Format static assertions list for display in prompt"""
    if not static_invariants:
        return "None yet."
    
    formatted = []
    for i, assertion in enumerate(static_invariants, 1):
        formatted.append(f"{i}. {assertion['assertion_name']}")
        formatted.append(f"   Tool Trigger: {assertion['tool_trigger']}")
        formatted.append(f"   Logic: {assertion['check_logic']}")
        formatted.append(f"   Violation: {assertion['violation_condition']}")
        formatted.append("")  # Empty line for separation
    
    return "\n".join(formatted)

def format_trajectory_steps(trajectory_steps):
    """Format trajectory steps list for display in prompt"""
    if not trajectory_steps:
        return "None yet."
    
    formatted = []
    for i, step in enumerate(trajectory_steps, 1):  # Start from 1
        # Try to format as JSON for better readability
        try:
            if isinstance(step, (dict, list)):
                step_str = json.dumps(step, indent=2)
            else:
                step_str = str(step)
        except (TypeError, ValueError):
            # Fallback to string representation if JSON serialization fails
            step_str = str(step)
        
        # Indent continuation lines for better visual structure
        lines = step_str.split('\n')
        if len(lines) > 1:
            indented = lines[0] + '\n' + '\n'.join('   ' + line for line in lines[1:])
            formatted.append(f"Step {i}:\n   {indented}")
        else:
            formatted.append(f"Step {i}: {step_str}")
    
    return "\n".join(formatted)

def parse_dynamic_invariant_generated(text: str, task_id: int, module_path: str = None) -> Dict:
    """
    Parse a single invariant step definition from structured text.
    - If 'NO INVARIANT NEEDED' is found, returns None.
    - Otherwise, extracts the metadata fields and appends the code block to the specified module file.
    """
    text = text.strip()
    if not text:
        return None

    # Skip steps with no invariant needed
    if re.search(r"\bNO INVARIANT NEEDED\b", text, re.IGNORECASE):
        return None

    # Extract fields
    step_num_match = re.search(r"Step Number:\s*(\d+)", text)
    assertion_match = re.search(r"Assertion Name:\s*(.*)", text)
    reasoning_match = re.search(r"Reasoning:\s*(.*?)(?=\s*Primary Step Number:)", text, re.DOTALL)
    primary_step_match = re.search(r"Primary Step Number:\s*(\d+)", text)
    check_logic_match = re.search(r"Check Logic:\s*(.*?)(?=\s*Violation Condition:)", text, re.DOTALL)
    violation_match = re.search(r"Violation Condition:\s*(.*?)(?=\s*Python Code:)", text, re.DOTALL)
    code_match = re.search(r"Python Code:\s*([\s\S]*)", text)

    if not all([step_num_match, assertion_match, reasoning_match, primary_step_match, check_logic_match, violation_match, code_match]):
        return None  # skip malformed input

    # Extract text
    step_number = int(step_num_match.group(1).strip())
    assertion_name = assertion_match.group(1).strip()
    reasoning = reasoning_match.group(1).strip()
    primary_step_number = int(primary_step_match.group(1).strip())
    check_logic = check_logic_match.group(1).strip()
    violation_condition = violation_match.group(1).strip()

    # --- Normalize the code block ---
    raw_code = code_match.group(1)

    # 1) Convert HTML entities (&lt;, &gt;, &amp;, etc.) back to real characters
    raw_code = html.unescape(raw_code)

    # 2) Remove leading code fences if present
    raw_code_stripped = raw_code.strip()
    if raw_code_stripped.startswith("```"):
        # Remove the first and last fence lines
        lines = raw_code.splitlines()
        # find opening fence
        start = 0
        while start < len(lines) and not lines[start].strip().startswith("```"):
            start += 1
        if start < len(lines):
            lines = lines[start + 1:]
            # find closing fence
            end = len(lines) - 1
            while end >= 0 and not lines[end].strip().startswith("```"):
                end -= 1
            if end >= 0:
                lines = lines[:end]
        raw_code = "\n".join(lines)

    # 3) Dedent robustly: prepend a newline so the first line’s indentation is ignored
    #    (classic trick to make dedent compute indentation from subsequent lines)
    code_block = textwrap.dedent("\n" + raw_code).lstrip("\n").rstrip()

    # 4) Optional safety: validate that the code is syntactically correct before appending
    try:
        ast.parse(code_block)
    except SyntaxError as e:
        # As a fallback, try one more normalization (rarely needed)
        code_block_alt = textwrap.dedent(raw_code).strip()
        try:
            ast.parse(code_block_alt)
            code_block = code_block_alt
        except SyntaxError:
            # If still invalid, skip writing this block to avoid corrupting the module
            # (or log the error for investigation)
            # print(f"Skipping invalid code block for step {step_number}: {e}")
            return None

    # Append code to the Python module (ensure separation)
    # Determine where to persist this dynamic invariant implementation
    # Use the global path if no module_path is provided
    resolved_module_path = module_path if module_path is not None else g.DYNAMIC_INVARIANTS_MODULE_PATH
    if not os.path.isabs(resolved_module_path):
        resolved_module_path = os.path.join(os.path.dirname(__file__), resolved_module_path)

    if resolved_module_path.endswith(".py"):
        base_dir = os.path.dirname(resolved_module_path)
        default_filename = os.path.basename(resolved_module_path) or "task_default.py"
    else:
        base_dir = resolved_module_path
        default_filename = "task_default.py"

    filename = f"task_{task_id}.py" if task_id is not None else default_filename
    module_file_path = os.path.join(base_dir, filename)

    os.makedirs(base_dir, exist_ok=True)

    with open(module_file_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + code_block + "\n")

    # Return structured metadata dict
    return {
        "step_number": step_number,
        "assertion_name": assertion_name,
        "reasoning": reasoning,
        "primary_step_number": primary_step_number,
        "check_logic": check_logic,
        "violation_condition": violation_condition,
        "module_file_path": module_file_path,
    }


def format_violations(violations):
    """Format a list of violation dicts for logging.

    Each violation dict is expected to have keys:
      - step_num (int)
      - assertion_name (str)
      - assertion_logic (str)
    Gracefully handles missing keys.
    """
    if not violations:
        return "No violations for this step."
    lines = []
    for i, v in enumerate(violations, 1):
        step = v.get('step_num', 'N/A')
        name = v.get('assertion_name', 'UNKNOWN_ASSERTION')
        logic = v.get('assertion_logic', '')
        lines.append(f"{i}. Step {step} -> {name}")
        if logic:
            # Truncate very large logic blocks for readability
            short_logic = logic if len(logic) < 300 else logic[:300] + '...'
            lines.append(f"   Logic: {short_logic}")
        lines.append("")
    return "\n".join(lines).rstrip()

def extract_corrected_code(llm_response: str) -> Optional[str]:
    
    """Extract Python code from LLM reflection response."""

    if not llm_response:
        print("### DEBUG [extract_corrected_code]: Empty LLM response")
        return None

    # Try multiple patterns for code blocks in order of preference
    
    # Pattern 1: ```python with content
    code_block_pattern = r"```python\s*\n(.*?)```"
    matches = re.findall(code_block_pattern, llm_response, re.DOTALL)
    if matches:
        print(f"### DEBUG [extract_corrected_code]: Found {len(matches)} matches with pattern 1 (```python\\n...```)")
        return max(matches, key=len).strip()
    
    # Pattern 2: ```python without newline
    code_block_pattern = r"```python\s+(.*?)```"
    matches = re.findall(code_block_pattern, llm_response, re.DOTALL)
    if matches:
        print(f"### DEBUG [extract_corrected_code]: Found {len(matches)} matches with pattern 2 (```python ...```)")
        return max(matches, key=len).strip()
    
    # Pattern 3: Just ``` without language identifier
    code_block_pattern = r"```\s*\n(.*?)```"
    matches = re.findall(code_block_pattern, llm_response, re.DOTALL)
    if matches:
        print(f"### DEBUG [extract_corrected_code]: Found {len(matches)} matches with pattern 3 (```\\n...```)")
        # Filter to only include blocks that look like Python (start with def or have Python keywords)
        python_matches = [m for m in matches if m.strip().startswith('def ') or 'return' in m]
        if python_matches:
            print(f"### DEBUG [extract_corrected_code]: {len(python_matches)} look like Python code")
            return max(python_matches, key=len).strip()
    
    # Pattern 4: Code block without closing ``` (incomplete response)
    code_block_pattern = r"```(?:python)?\s*\n(def\s+\w+\s*\(.*?):.*"
    matches = re.findall(code_block_pattern, llm_response, re.DOTALL)
    if matches:
        print(f"### DEBUG [extract_corrected_code]: Found {len(matches)} matches with pattern 4 (incomplete code block)")
        # Take everything from the opening ``` to end of response
        start_idx = llm_response.find('```')
        if start_idx != -1:
            # Skip the ``` and optional python keyword
            code_start = llm_response.find('\n', start_idx) + 1
            if code_start > start_idx:
                extracted = llm_response[code_start:].strip()
                # Remove trailing ``` if present
                if extracted.endswith('```'):
                    extracted = extracted[:-3].strip()
                print(f"### DEBUG [extract_corrected_code]: Extracted {len(extracted)} chars from incomplete block")
                return extracted
    
    # Pattern 5: Raw Python code starting with def (NO code fences at all)
    # This catches cases where LLM returns pure Python without markdown formatting
    if llm_response.strip().startswith('def '):
        print(f"### DEBUG [extract_corrected_code]: Found raw Python code (starts with 'def')")
        # Extract from 'def' to the end, or until we hit another def or significant dedent
        # For now, just take the whole response if it starts with def
        return llm_response.strip()
    
    # Pattern 6: Look for def function anywhere in the text (more lenient fallback)
    def_pattern = r"(def\s+\w+\s*\([^)]*\):.*?)(?=\n(?:def\s+\w+|class\s+\w+|\Z))"
    matches = re.findall(def_pattern, llm_response, re.DOTALL)
    if matches:
        print(f"### DEBUG [extract_corrected_code]: Found {len(matches)} matches with pattern 6 (raw def anywhere)")
        # Take the longest match (most complete function)
        return max(matches, key=len).strip()
    
    print("### DEBUG [extract_corrected_code]: No matches found with any pattern")
    print(f"### DEBUG [extract_corrected_code]: Response starts with: {llm_response[:200]}")
    return None

def update_invariants_module(assertion_name: str,
                             corrected_code: str,
                             module_file_path: Optional[str] = None) -> bool:
    """
    Update the invariants module with corrected code.
    Returns True if it the update was successful, False otherwise.
    """
    try:
        # Read current module content
        if os.path.exists(module_file_path):
            with open(module_file_path, 'r') as f:
                content = f.read()
        else:
            content = ""
        
        # Use AST-based approach to find and replace function
        try:
            tree = ast.parse(content)
            function_found = False
            start_line = None
            end_line = None
            
            # Find the function in the AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == assertion_name:
                    function_found = True
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno  # exclusive when slicing
                    break
            
            if function_found:
                # Replace the function
                lines = content.splitlines(keepends=True)
                new_content = ''.join(lines[:start_line]) + corrected_code + '\n' + ''.join(lines[end_line:])
            else:
                # Append new function
                new_content = content + "\n\n" + corrected_code + "\n"
                
        except SyntaxError:
            # Fallback to regex-based approach if AST parsing fails
            # Escape the function name for regex
            escaped_name = re.escape(assertion_name)
            pattern = rf"def {escaped_name}\s*\([^)]*\):.*?(?=\ndef\s|\Z)"
            
            if re.search(pattern, content, re.DOTALL):
                # Replace existing function
                new_content = re.sub(pattern, corrected_code, content, flags=re.DOTALL)
            else:
                # Append new function
                new_content = content + "\n\n" + corrected_code + "\n"
        
        # Write back to file
        with open(module_file_path, 'w') as f:
            f.write(new_content)

        print(f"Successfully updated the invariants module with corrected '{assertion_name}' in {module_file_path}")
        return True
        
    except Exception as e:
        import traceback
        print(f"Failed to update invariants module for {assertion_name} in {module_file_path} because of the exception:\n{e}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return False


def load_function_source_from_file(module_file_path: str, function_name: str) -> Optional[str]:
    """Best-effort attempt to extract a function definition from a module file."""
    resolved_path = module_file_path
    if not os.path.isabs(resolved_path):
        resolved_path = os.path.join(os.path.dirname(__file__), resolved_path)

    if not os.path.exists(resolved_path):
        return None

    try:
        with open(resolved_path, "r", encoding="utf-8") as module_file:
            content = module_file.read()
    except OSError:
        return None

    pattern = rf"def {re.escape(function_name)}\s*\(.*?\):\s*(?:\"\"\".*?\"\"\"\s*)?.*?(?=\ndef\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(0).strip()
    return None

def get_invariant_source(
        fn,
        module_file_path: Optional[str],
        function_name: str,
    ) -> str:
        """Retrieve the source code for a dynamic invariant function for reflection."""
        source = ""
        if fn is not None:
            try:
                source = inspect.getsource(fn)
            except OSError:
                source = ""

        if source or not module_file_path:
            return source

        file_source = load_function_source_from_file(module_file_path, function_name)
        return file_source or ""
