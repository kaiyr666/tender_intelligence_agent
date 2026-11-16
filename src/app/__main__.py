"""Command line entry point: uv run python -m app "some text"."""

import json
import sys

from app.pipeline import run


def main() -> None:
    text = " ".join(sys.argv[1:]) or "Leeds City Council invites bids worth £250,000."
    print(json.dumps(run(text), indent=2))


if __name__ == "__main__":
    main()
