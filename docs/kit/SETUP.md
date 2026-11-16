# One-time setup

Do this once on your computer, at least a day before the take-home. About 20 minutes. Open the **Terminal** app (Mac) or **PowerShell** (Windows) and paste each command.

## 1. Install the tools

| Tool | What it is | Mac | Windows (PowerShell) |
|---|---|---|---|
| **Git** | Saves versions of your work | `xcode-select --install` | Download from git-scm.com and install |
| **uv** | Installs Python and the project's libraries | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **Node.js** | Needed to install Codex | Download the LTS version from nodejs.org | Same |
| **Claude Code** | The builder | `curl -fsSL https://claude.ai/install.sh \| bash` | `irm https://claude.ai/install.ps1 \| iex` |
| **Codex CLI** | The reviewer | `npm install -g @openai/codex` | `npm install -g @openai/codex` |
| **GitHub CLI** | Lets the terminal upload to your GitHub | `brew install gh` (or download from cli.github.com) | Download from cli.github.com and install |

Close and reopen the terminal after installing, then check each one answers with a version number:
```
git --version
uv --version
claude --version
codex --version
gh --version
```

## 2. Sign in (no API keys needed for the tools)
- **Claude Code:** run `claude`, then follow the browser sign-in with your Claude account. Type `/exit` to leave.
- **Codex:** run `codex login` and choose **Sign in with ChatGPT**. Check with `codex login status`.
- **GitHub:** run `gh auth login`, choose **GitHub.com → HTTPS → Yes (authenticate Git) → Login with a web browser**. This lets Claude push your work after every slice. Check with `gh auth status`.

Both tools then use your subscriptions. A long build session uses a lot of Claude usage, so make sure your plan has headroom for five hours of work.

## 3. Get an API key (skip if you have Claude Max, which includes API credits) for the product
Your subscriptions pay for the tools, not for the LLM calls your *product* makes. For those you need one API key:
1. Go to console.anthropic.com (or platform.openai.com), create a key and **set a monthly spending limit** (USD 20 is plenty).
2. Keep the key somewhere safe. You paste it into the project's `.env` file during `/setup`. Never paste it into a chat.

## 4. Make your own copy of the kit
1. On GitHub, open the `ai-native-starter` repo → **Settings** → tick **Template repository** (only once).
2. For each new project: click **Use this template → Create a new repository**, give it a name, then copy its URL.
3. In the terminal:
   ```
   git clone <the URL>
   cd <the repo name>
   claude
   ```
4. Inside Claude Code, type `/setup`.

## If something goes wrong
- **"command not found"**: close and reopen the terminal; if it still fails, reinstall that tool.
- **Codex says not logged in**: run `codex login` again.
- **Claude says it hit a usage limit**: wait or upgrade the plan; meanwhile Codex can continue the build (`codex`, then describe the next slice).
