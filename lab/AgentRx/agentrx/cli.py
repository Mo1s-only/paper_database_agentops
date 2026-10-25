"""CLI entrypoint for the agentrx package.

Delegates to the run module's main() function so that the package
can be invoked as either:
    agentrx <args>          (console script)
    python -m agentrx <args>
    python run.py <args>    (backward-compatible)
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    # Ensure the repo root is available for data/ lookups when installed
    # and run from outside the repo.
    run_module_path = os.path.join(os.path.dirname(__file__), "..", "run.py")
    if os.path.exists(run_module_path):
        # Running from a repo checkout – import run.py directly
        import importlib.util
        spec = importlib.util.spec_from_file_location("run", run_module_path)
        run_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_mod)
        run_mod.main()
    else:
        # Fallback: run.py not found (e.g. pure wheel install)
        print("Error: run.py not found. Please run from the repository root.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
