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
    --init              Initialize git + devcontainer in current directory
    --tree [NAME]       Create git worktree and start devcontainer there
    --create NAME       Create new project with git + devcontainer
    --new               Remove existing container before starting
    --sync              Regenerate .devcontainer from template
    --list              List containers and worktrees for current project
    --list --all        List all running devcontainers globally
    --stop              Stop the current project's container
    --stop --all        Stop all containers for project (worktrees + main)
    --prune             Clean up stopped containers and stale worktrees
    --attach            Attach to running container (error if not running)
    --detach, -d        Start container without attaching
    --from BRANCH       Create worktree from specific branch (use with --tree)
    --verbose, -v       Print commands being executed
    --help              Show usage information
```

## Quick Examples

```bash
# Start devcontainer in current project
yolo

# Initialize git + devcontainer in existing directory
yolo --init

# Create a new worktree with random name
yolo --tree

# Create a named worktree from a specific branch
yolo --tree feature-x --from develop

# Create a new project (from outside any git repo)
yolo --create myproject

# Start container in background (works from inside tmux)
yolo -d --create newproject
yolo -d --tree experiment

# List all running containers
yolo --list --all

# Stop all project containers and clean up
yolo --stop --all
yolo --prune
```

## Usage Notes

**Argument ordering with `--create`:** When using `-d` with `--create`, put `-d` first:
```bash
yolo -d --create NAME    # correct
yolo --create NAME -d    # correct
yolo --create -d NAME    # wrong - argparse sees -d as NAME
```

**Running from inside tmux:** Use `--detach` to start containers without attaching:
```bash
yolo -d                  # start current project
yolo -d --tree feature   # create worktree and start
```

## Core Behaviors

### Default Mode (no flags)

1. Detect git root (if in subdirectory, navigate to root)
2. If `.devcontainer/` missing, create it from template
3. Start devcontainer (skip if already running)
4. Attach to tmux session `dev`

### `--init`

1. Must NOT be inside a git repo (error otherwise)
2. Initialize git repo in current directory
3. Scaffold `.devcontainer/` from template
4. Commit `.devcontainer/`
5. Start devcontainer
6. Attach to tmux session

### `--tree [NAME]`

1. Must be inside an existing git repo (error otherwise)
2. If NAME not provided, generate random adjective-noun (e.g., `brave-panda`)
3. Create worktree at `../PROJECT-worktrees/NAME`
4. Create and checkout branch named `NAME` (optionally from `--from BRANCH`)
5. Copy `.devcontainer/` to the new worktree (with git mount for worktree support)
6. Start devcontainer in the worktree
7. Attach to tmux session

### `--create NAME`

1. Must NOT be inside a git repo (error otherwise)
2. Create directory `NAME` in current location
3. Initialize git repo and commit `.devcontainer/`
4. Scaffold `.devcontainer/` from template
5. Start devcontainer
6. Attach to tmux session

### `--sync`

Regenerate `.devcontainer/` from template using current config. Useful for updating existing projects with new base image or settings.

Can be combined with `--new` to sync and rebuild in one command:
```bash
yolo --sync --new    # sync config and rebuild container
```

### `--list`

Show containers and worktrees for current project:
```
Project: myproject

Containers:
  * myproject            running    (main)
  * myproject-feature    running    (feature)
    myproject-old        stopped    (old)

Worktrees:
    feature              feature         [abc1234]
    old                  old             [def5678]
```

With `--all`, shows all devcontainers globally (not just current project).

### `--stop`

Stop the container for current project. With `--all`, stops all worktree containers first, then main.

### `--prune`

Find and remove:
- Stopped containers for the project
- Stale worktrees (directories that no longer exist)

Prompts for confirmation before deletion.

### `--attach`

Explicitly attach to a running container. Errors if container is not running (use plain `yolo` to start and attach).

### `--detach` / `-d`

Start container without attaching to tmux. Useful for:
- Running from inside tmux (bypasses tmux guard)
- Starting multiple containers in batch
- Scripting

## Guards and Validations

| Condition | Behavior |
|-----------|----------|
| Already inside tmux | Error (unless `--detach` is used) |
| `--tree` outside git repo | Error: "Not in a git repository" |
| `--init` inside git repo | Error: "Already in a git repository" |
| `--create` inside git repo | Error: "Already in a git repository" |
| `--from` branch doesn't exist | Error: "Branch does not exist" |
| Target directory exists | Error: "Directory already exists" |
| `.devcontainer/` exists | Warn and continue |
| Container already running | Just attach (don't recreate) |

## Configuration

Configuration is loaded in order (later overrides earlier):
1. Built-in defaults
2. Global config: `~/.config/yolo/config.toml`
3. Project config: `.yolo.toml`

### Config File Format (TOML)

```toml
# ~/.config/yolo/config.toml or .yolo.toml
base_image = "localhost/emacs-gui:latest"
pass_path_anthropic = "api/llm/anthropic"
pass_path_openai = "api/llm/openai"
```

### Available Options

| Option | Default | Description |
|--------|---------|-------------|
| `base_image` | `localhost/emacs-gui:latest` | Docker image for Dockerfile |
| `pass_path_anthropic` | `api/llm/anthropic` | Pass path for Anthropic API key |
| `pass_path_openai` | `api/llm/openai` | Pass path for OpenAI API key |

## Secrets Management

Secrets are loaded in this order:

1. If `pass` command available, fetch from password store using configured paths
2. Fallback to environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)

## Container Configuration

### Naming Convention

- Default: `projectname`
- Worktree: `projectname-worktreename`

### tmux Session

- Session name: `dev`
- Behavior: attach if exists, create if not

### Network / Ports

- Services should bind to `0.0.0.0` for tailscale network access
- Any port accessible on host is accessible via tailscale IP

## Template: `.devcontainer/`

### `devcontainer.json`

```json
{
    "name": "PROJECT_NAME",
    "build": {
        "dockerfile": "Dockerfile"
    },
    "mounts": [
        "source=/tmp/.X11-unix,target=/tmp/.X11-unix,type=bind",
        "source=${localEnv:HOME}/.claude,target=/home/${localEnv:USER}/.claude,type=bind",
        "source=${localEnv:HOME}/.claude.json,target=/home/${localEnv:USER}/.claude.json,type=bind",
        "source=${localEnv:HOME}/.zshrc,target=/home/${localEnv:USER}/.zshrc,type=bind,readonly",
        "source=${localEnv:HOME}/.tmux.conf,target=/home/${localEnv:USER}/.tmux.conf,type=bind,readonly",
        "source=${localEnv:HOME}/.gitconfig,target=/home/${localEnv:USER}/.gitconfig,type=bind,readonly",
        "source=${localEnv:HOME}/.config/tmux,target=/home/${localEnv:USER}/.config/tmux,type=bind,readonly",
        "source=${localEnv:HOME}/.config/emacs,target=/home/${localEnv:USER}/.config/emacs,type=bind",
        "source=${localEnv:HOME}/.cache/emacs,target=/home/${localEnv:USER}/.cache/emacs,type=bind",
        "source=${localEnv:HOME}/.gnupg/pubring.kbx,target=/home/${localEnv:USER}/.gnupg/pubring.kbx,type=bind,readonly",
        "source=${localEnv:HOME}/.gnupg/trustdb.gpg,target=/home/${localEnv:USER}/.gnupg/trustdb.gpg,type=bind,readonly",
        "source=${localEnv:XDG_RUNTIME_DIR}/gnupg/S.gpg-agent,target=/home/${localEnv:USER}/.gnupg/S.gpg-agent,type=bind",
        "source=${localEnv:HOME}/.config/gh,target=/home/${localEnv:USER}/.config/gh,type=bind,readonly"
    ],
    "containerEnv": {
        "TERM": "xterm-256color",
        "DISPLAY": "${localEnv:DISPLAY}",
        "WAYLAND_DISPLAY": "${localEnv:WAYLAND_DISPLAY}",
        "XDG_RUNTIME_DIR": "/tmp/container-runtime",
        "ANTHROPIC_API_KEY": "${localEnv:ANTHROPIC_API_KEY}",
        "OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY}"
    }
}
```

**Conditional mount:** When `WAYLAND_DISPLAY` is set, an additional Wayland socket mount is included:
```
"source=${localEnv:XDG_RUNTIME_DIR}/${localEnv:WAYLAND_DISPLAY},target=/tmp/container-runtime/${localEnv:WAYLAND_DISPLAY},type=bind"
```

### `Dockerfile`

```dockerfile
FROM BASE_IMAGE

USER root
RUN apk add --no-cache nodejs npm
LABEL devcontainer.metadata='[{"remoteUser":"CONTAINER_USER","workspaceFolder":"/workspace"}]'

WORKDIR /workspace

USER CONTAINER_USER
```

Note: `BASE_IMAGE` is replaced with the configured base image (default: `localhost/emacs-gui:latest`). `CONTAINER_USER` is replaced with the current `$USER`.

Note: For worktrees, an additional mount is added for the main repo's `.git` directory to enable git operations.

## Random Name Generation

For `--tree` without a name argument:

**Adjectives:** brave, swift, calm, bold, keen, wild, warm, cool, fair, wise

**Nouns:** panda, falcon, river, mountain, oak, wolf, hawk, cedar, fox, bear

Example: `brave-panda`, `swift-falcon`, `calm-river`

## Dependencies

Required on host:
- `devcontainer` CLI
- `git`
- `tmux`
- `docker` or `podman`
- `pass` (optional, for secrets)

## Development

```bash
# Run tests
python3 -m unittest discover -s /workspaces/yolo -p 'test_*.py'

# Install
cp yolo.py ~/.local/bin/yolo && chmod +x ~/.local/bin/yolo
```
