"""Format and lint each Python file right after Claude edits it.

Formatting and safe fixes are applied silently. Remaining lint errors are
reported back to Claude (exit code 2) so it fixes them straight away.
"""

import json
import subprocess
import sys


def main() -> None:
    try:
        # Claude Code sends UTF-8; reading with the Windows code page garbles non-ASCII paths.
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    path = (event.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return

    subprocess.run(["ruff", "format", "--quiet", path], check=False)
    subprocess.run(["ruff", "check", "--fix", "--quiet", path], check=False)
    result = subprocess.run(
        ["ruff", "check", "--output-format", "concise", path],
        capture_output=True,
        text=True,
        encoding="utf-8",  # ruff writes UTF-8; the Windows default code page cannot decode it
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        print(f"Lint errors remain in {path}; please fix:\n{result.stdout}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
