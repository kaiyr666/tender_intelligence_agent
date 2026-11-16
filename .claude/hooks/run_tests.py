"""Run the test suite whenever Claude finishes a turn.

If tests fail, Claude is told to fix them before stopping (exit code 2).
To avoid an endless loop, it only pushes back once per stop attempt.
"""

import json
import os
import subprocess
import sys


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        event = {}

    if event.get("stop_hook_active"):
        return  # already pushed back once; let Claude stop and report

    result = subprocess.run(
        ["pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        check=False,
        cwd=os.environ.get("CLAUDE_PROJECT_DIR") or None,
    )
    # 0 = passed, 5 = no tests collected yet (fine at the very start)
    if result.returncode in (0, 5):
        return

    tail = "\n".join(result.stdout.strip().splitlines()[-25:])
    print(
        "Tests are failing. Fix them before finishing, or explain clearly why not:\n" + tail,
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
