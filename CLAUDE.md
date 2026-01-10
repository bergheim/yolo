# yolo - Devcontainer + Git Worktree Launcher

A script to quickly spin up devcontainer environments with git worktree support and Claude with no limits.

## Overview

`yolo` is a CLI tool that:
- Bootstraps devcontainer environments for any project
- Creates git worktrees with isolated devcontainers
- Scaffolds new projects with git + devcontainer setup
- Runs Claude in "dangerously-skip-permissions" mode inside tmux

Target location: `~/.local/bin/yolo`

## Usage

```
yolo [OPTIONS]

OPTIONS:
    (none)              Start devcontainer in current git project
    --tree [NAME]       Create git worktree and start devcontainer there
    --create NAME       Create new project with git + devcontainer
    --new               Remove existing container before starting
    --help              Show usage information

FUTURE OPTIONS (not MVP):
    --stop              Stop the current project's container
    --list              List running containers / worktrees
    --attach            Attach to already-running container
    --detach, -d        Start container without attaching
    --verbose           Debug output
    --prune             Clean up stopped containers / stale worktrees
    --from BRANCH       Create worktree from specific branch (use with --tree)
```

## Core Behaviors

### Default Mode (no flags)

1. Detect git root (if in subdirectory, navigate to root)
2. If `.devcontainer/` missing, create it from template
3. Start devcontainer
4. Attach to tmux session `dev` (reattach if exists, else create)

### `--tree [NAME]`

1. Must be inside an existing git repo (error otherwise)
2. If NAME not provided, generate random adjective-noun (e.g., `brave-panda`)
3. Create worktree at `../PROJECT-worktrees/NAME`
   - Example: in `/dev/myapp`, `--tree foo` creates `/dev/myapp-worktrees/foo`
4. Create and checkout branch named `NAME`
5. Copy `.devcontainer/` to the new worktree
6. Start devcontainer in the worktree
7. Attach to tmux session

### `--create NAME`

1. Must NOT be inside a git repo (error otherwise)
2. Create directory `NAME` in current location
3. Initialize git repo (`git init`)
4. Scaffold `.devcontainer/` from template with project name
5. Start devcontainer
6. Attach to tmux session

### `--new`

- Remove existing container before starting (passes `--remove-existing-container` to devcontainer CLI)
- Can combine with other modes

## Guards and Validations

| Condition | Behavior |
|-----------|----------|
| Already inside tmux | Error: "Already in tmux session. Nested tmux not supported." |
| `--tree` outside git repo | Error: "Not in a git repository. --tree requires an existing repo." |
| `--create` inside git repo | Error: "Already in a git repository. Use --tree for worktrees." |
| Target directory exists | Error: "Directory already exists: PATH" |
| `.devcontainer/` exists | Warn: "Using existing .devcontainer/" and continue |
| Container already running | Just attach (don't error or recreate) |

## Secrets Management

Check for secrets in this order:

1. If `pass` command available:
   ```sh
   ANTHROPIC_API_KEY=$(pass show api/llm/anthropic)
   OPENAI_API_KEY=$(pass show api/llm/openai)
   ```

2. Fallback to environment variables (assume already exported)

## Container Configuration

### Naming Convention

- Default: `projectname`
- Worktree: `projectname-worktreename`

### tmux Session

- Session name: `dev`
- Behavior: attach if exists, create if not (`tmux attach-session -t dev || tmux new-session -s dev`)

### Network / Ports

- Services should bind to `0.0.0.0` (not `127.0.0.1`) for tailscale network access
- Any port accessible on host is accessible via tailscale IP

### Base Image

- Currently: `localhost/emacs-gui:latest`
- Hardcoded for now; user will update manually as needed

## Template: `.devcontainer/`

When scaffolding, copy from a template with these substitutions:

| Placeholder | Value |
|-------------|-------|
| `PROJECT_NAME` | Directory/project name |

### `devcontainer.json` template

```json
{
    "name": "PROJECT_NAME",
    "build": {
        "dockerfile": "Dockerfile"
    },
    "mounts": [
        "source=/tmp/.X11-unix,target=/tmp/.X11-unix,type=bind",
        "source=${localEnv:HOME}/.claude,target=/home/tsb/.claude,type=bind",
        "source=${localEnv:HOME}/.claude.json,target=/home/tsb/.claude.json,type=bind",
        "source=${localEnv:HOME}/.zshrc,target=/home/tsb/.zshrc,type=bind,readonly",
        "source=${localEnv:HOME}/.tmux.conf,target=/home/tsb/.tmux.conf,type=bind,readonly",
        "source=${localEnv:HOME}/.config/tmux,target=/home/tsb/.config/tmux,type=bind,readonly",
        "source=${localEnv:XDG_RUNTIME_DIR}/${localEnv:WAYLAND_DISPLAY},target=/tmp/runtime-1000/${localEnv:WAYLAND_DISPLAY},type=bind",
        "source=${localEnv:HOME}/.config/emacs,target=/home/tsb/.config/emacs,type=bind",
        "source=${localEnv:HOME}/.cache/emacs,target=/home/tsb/.cache/emacs,type=bind"
    ],
    "containerEnv": {
        "TERM": "xterm-256color",
        "DISPLAY": "${localEnv:DISPLAY}",
        "WAYLAND_DISPLAY": "${localEnv:WAYLAND_DISPLAY}",
        "XDG_RUNTIME_DIR": "/tmp/runtime-1000",
        "ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY}",
        "OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY}"
    },
    "postStartCommand": "/home/tsb/entrypoint.sh"
}
```

### `Dockerfile` template

```dockerfile
FROM localhost/emacs-gui:latest

USER root
RUN apk add --no-cache nodejs npm
LABEL devcontainer.metadata='[{"remoteUser":"tsb","workspaceFolder":"/workspace"}]'

WORKDIR /workspace

USER tsb
```

## Random Name Generation

For `--tree` without a name argument, generate adjective-noun combinations:

**Adjectives:** brave, swift, calm, bold, keen, wild, warm, cool, fair, wise

**Nouns:** panda, falcon, river, mountain, oak, wolf, hawk, cedar, fox, bear

Example output: `brave-panda`, `swift-falcon`, `calm-river`

## Future Enhancements (Not MVP)

### Additional Flags

- `--stop` — Stop container for current project
- `--list` — Show running containers and worktrees for current project
- `--attach` — Explicitly attach to running container
- `--detach` / `-d` — Start container in background without attaching
- `--verbose` — Print debug information
- `--prune` — Remove stopped containers and/or stale worktrees
- `--from BRANCH` — Create worktree from specific branch instead of HEAD

### Configuration Files

**Global config:** `~/.config/yolo/config`
```sh
# Example future config
BASE_IMAGE=localhost/emacs-gui:latest
DEFAULT_SHELL=zsh
PASS_PATH_ANTHROPIC=api/llm/anthropic
PASS_PATH_OPENAI=api/llm/openai
```

**Per-project config:** `.yolo.conf`
```sh
# Override defaults for this project
BASE_IMAGE=localhost/node-dev:latest
```

## Dependencies

Assumed available on host:
- `devcontainer` CLI
- `git`
- `tmux`
- `pass` (optional, for secrets)
- Tailscale (for network access)

## Reference Files

- `reference/Containerfile` — Base image build file
- `reference/entrypoint.sh` — Container entrypoint (tmux/emacs startup)
- `.devcontainer/` — Current working devcontainer config
