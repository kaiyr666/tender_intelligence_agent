"""Checks that the kit's safety hooks behave as intended."""

import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).parents[2] / ".claude" / "hooks" / "guard_secrets.py"
FAKE_KEY = "sk-ant-" + "a1B2c3D4" * 5


def guard(tool: str, **tool_input) -> int:
    event = json.dumps({"tool_name": tool, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, str(GUARD)], input=event, text=True, capture_output=True
    ).returncode


def test_writing_an_api_key_into_code_is_blocked():
    assert guard("Write", file_path="src/app/x.py", content=f'KEY = "{FAKE_KEY}"') == 2


def test_editing_the_real_env_file_is_blocked():
    assert guard("Edit", file_path="/repo/.env", new_string="X=1") == 2


def test_editing_env_example_is_allowed():
    assert guard("Edit", file_path="/repo/.env.example", new_string="X=") == 0


def test_reading_env_from_the_shell_is_blocked():
    assert guard("Bash", command="cat .env") == 2


def test_creating_env_from_the_template_is_allowed():
    assert guard("Bash", command="cp .env.example .env") == 0


def test_normal_code_and_commands_pass():
    assert guard("Write", file_path="src/app/x.py", content="import os\n") == 0
    assert guard("Bash", command="uv run pytest -q") == 0
