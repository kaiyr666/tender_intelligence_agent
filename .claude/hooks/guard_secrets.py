"""Block edits and commands that would expose secrets.

Runs before every Edit/Write/Bash call. Exit code 2 blocks the action and
the message on stderr is shown to Claude so it can change course.
"""

import json
import re
import sys
from pathlib import PurePath

SECRET_PATTERNS = [
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "an Anthropic API key"),
    (r"sk-(proj-|svcacct-)?[A-Za-z0-9_\-]{32,}", "an OpenAI API key"),
    (r"AKIA[0-9A-Z]{16}", "an AWS access key"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "a GitHub token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"),
]

# Shell commands that would print or stage the real .env file.
ENV_COMMAND = re.compile(
    r"(cat|less|more|head|tail|type|bat|grep|cp|mv|source|\.)\s+[^|;&]*\.env(\s|$|[;&|])"
    r"|git\s+add\s+[^|;&]*(-f|--force)[^|;&]*\.env"
)
# Creating the empty .env from the template is allowed (it holds no keys yet).
ENV_FROM_TEMPLATE = re.compile(r"\s*cp\s+(-n\s+)?\.env\.example\s+\.env\s*")


def is_real_env_file(path: str) -> bool:
    name = PurePath(path).name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def block(reason: str) -> None:
    print(f"BLOCKED by guard_secrets: {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # nothing to check

    tool = event.get("tool_name", "")
    data = event.get("tool_input", {}) or {}

    if tool == "Bash":
        command = data.get("command", "")
        if not ENV_FROM_TEMPLATE.fullmatch(command) and ENV_COMMAND.search(command):
            block("this command would read or stage the .env file. Keys must stay out of the chat.")
        texts = [command]
    else:
        path = data.get("file_path", "")
        if path and is_real_env_file(path):
            block(f"{path} holds real API keys. Only the human edits it; use .env.example.")
        texts = [data.get("content", ""), data.get("new_string", "")]
        texts += [e.get("new_string", "") for e in data.get("edits", []) or []]

    for text in texts:
        for pattern, label in SECRET_PATTERNS:
            if text and re.search(pattern, text):
                block(f"looks like {label}. Read keys from environment variables instead.")


if __name__ == "__main__":
    main()
