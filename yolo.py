#!/usr/bin/env python3
"""yolo - Devcontainer + Git Worktree Launcher.

A CLI tool that bootstraps devcontainer environments with git worktree support.
Target location: ~/.local/bin/yolo
"""

import argparse
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

# Word lists for random name generation
ADJECTIVES = ['brave', 'swift', 'calm', 'bold', 'keen',
              'wild', 'warm', 'cool', 'fair', 'wise']
NOUNS = ['panda', 'falcon', 'river', 'mountain', 'oak',
         'wolf', 'hawk', 'cedar', 'fox', 'bear']

# Templates
DEVCONTAINER_JSON_TEMPLATE = '''{
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
}'''

DOCKERFILE_TEMPLATE = '''FROM localhost/emacs-gui:latest

USER root
RUN apk add --no-cache nodejs npm
LABEL devcontainer.metadata='[{"remoteUser":"tsb","workspaceFolder":"/workspace"}]'

WORKDIR /workspace

USER tsb
'''


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='yolo',
        description='Devcontainer + Git Worktree Launcher',
        epilog='Run with no arguments to start devcontainer in current git project.'
    )

    parser.add_argument(
        '--tree',
        nargs='?',
        const='',
        default=None,
        metavar='NAME',
        help='Create git worktree and start devcontainer there. '
             'If NAME not provided, generates random name.'
    )

    parser.add_argument(
        '--create',
        metavar='NAME',
        help='Create new project with git + devcontainer'
    )

    parser.add_argument(
        '--new',
        action='store_true',
        help='Remove existing container before starting'
    )

    return parser.parse_args(argv)


def check_tmux_guard() -> None:
    """Check if already inside tmux session."""
    if os.environ.get('TMUX'):
        sys.exit('Error: Already in tmux session. Nested tmux not supported.')


def find_git_root(start_path: Path | None = None) -> Path | None:
    """Find git repository root by traversing up from start_path.

    Returns None if not in a git repository.
    """
    if start_path is None:
        start_path = Path.cwd()

    current = Path(start_path).resolve()

    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent

    # Check root directory too
    if (current / '.git').exists():
        return current

    return None


def generate_random_name() -> str:
    """Generate random adjective-noun name for worktree."""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f'{adj}-{noun}'


def scaffold_devcontainer(project_name: str, target_dir: Path | None = None) -> bool:
    """Create .devcontainer directory with templates.

    Returns True if created, False if already exists.
    """
    if target_dir is None:
        target_dir = Path.cwd()

    devcontainer_dir = target_dir / '.devcontainer'

    if devcontainer_dir.exists():
        print(f'Warning: Using existing .devcontainer/', file=sys.stderr)
        return False

    devcontainer_dir.mkdir(parents=True)

    # Write devcontainer.json with substituted project name
    json_content = DEVCONTAINER_JSON_TEMPLATE.replace('PROJECT_NAME', project_name)
    (devcontainer_dir / 'devcontainer.json').write_text(json_content)

    # Write Dockerfile
    (devcontainer_dir / 'Dockerfile').write_text(DOCKERFILE_TEMPLATE)

    return True


def get_secrets() -> dict[str, str]:
    """Get API secrets from pass or environment variables."""
    secrets = {}

    # Check if pass is available
    pass_available = shutil.which('pass') is not None

    if pass_available:
        # Try to get secrets from pass
        for key, pass_path in [
            ('ANTHROPIC_API_KEY', 'api/llm/anthropic'),
            ('OPENAI_API_KEY', 'api/llm/openai')
        ]:
            try:
                result = subprocess.run(
                    ['pass', 'show', pass_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    secrets[key] = result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Fallback to environment variables for any missing secrets
    for key in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY']:
        if key not in secrets:
            secrets[key] = os.environ.get(key, '')

    return secrets


def get_container_name(project_path: str, worktree_name: str | None) -> str:
    """Generate container name from project path and optional worktree name."""
    project_name = Path(project_path.rstrip('/')).name.lower()

    if worktree_name:
        return f'{project_name}-{worktree_name}'
    return project_name


def get_worktree_path(project_path: str, worktree_name: str) -> Path:
    """Compute worktree path: ../PROJECT-worktrees/NAME."""
    project_path = Path(project_path.rstrip('/'))
    project_name = project_path.name
    worktrees_dir = project_path.parent / f'{project_name}-worktrees'
    return worktrees_dir / worktree_name


def validate_tree_mode() -> Path:
    """Validate that --tree mode is being run inside a git repo.

    Returns the git root path.
    """
    git_root = find_git_root()
    if git_root is None:
        sys.exit('Error: Not in a git repository. --tree requires an existing repo.')
    return git_root


def validate_create_mode(name: str) -> None:
    """Validate that --create mode is NOT being run inside a git repo."""
    git_root = find_git_root()
    if git_root is not None:
        sys.exit('Error: Already in a git repository. Use --tree for worktrees.')

    target_dir = Path.cwd() / name
    if target_dir.exists():
        sys.exit(f'Error: Directory already exists: {target_dir}')


def devcontainer_up(workspace_dir: Path, remove_existing: bool = False) -> bool:
    """Start devcontainer with devcontainer up.

    Returns True if successful.
    """
    cmd = ['devcontainer', 'up', '--workspace-folder', str(workspace_dir)]

    if remove_existing:
        cmd.append('--remove-existing-container')

    result = subprocess.run(cmd)
    return result.returncode == 0


def devcontainer_exec_tmux(workspace_dir: Path) -> None:
    """Execute into container and attach/create tmux session."""
    cmd = [
        'devcontainer', 'exec',
        '--workspace-folder', str(workspace_dir),
        'sh', '-c', 'tmux attach-session -t dev || tmux new-session -s dev'
    ]

    subprocess.run(cmd)


def run_default_mode(args: argparse.Namespace) -> None:
    """Run default mode: start devcontainer in current git project."""
    git_root = find_git_root()

    if git_root is None:
        sys.exit('Error: Not in a git repository.')

    os.chdir(git_root)
    project_name = git_root.name

    # Scaffold .devcontainer if missing
    scaffold_devcontainer(project_name)

    # Set up secrets in environment
    secrets = get_secrets()
    os.environ.update(secrets)

    # Start devcontainer
    if not devcontainer_up(git_root, remove_existing=args.new):
        sys.exit('Error: Failed to start devcontainer')

    # Attach to tmux
    devcontainer_exec_tmux(git_root)


def run_tree_mode(args: argparse.Namespace) -> None:
    """Run --tree mode: create worktree and start devcontainer."""
    git_root = validate_tree_mode()

    # Generate name if not provided
    worktree_name = args.tree if args.tree else generate_random_name()

    # Compute paths
    worktree_path = get_worktree_path(str(git_root), worktree_name)

    # Check if worktree already exists
    if worktree_path.exists():
        sys.exit(f'Error: Directory already exists: {worktree_path}')

    # Create worktrees directory if needed
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Create git worktree with new branch
    result = subprocess.run(
        ['git', 'worktree', 'add', '-b', worktree_name, str(worktree_path)],
        cwd=git_root
    )
    if result.returncode != 0:
        sys.exit('Error: Failed to create git worktree')

    # Copy .devcontainer to worktree
    src_devcontainer = git_root / '.devcontainer'
    dst_devcontainer = worktree_path / '.devcontainer'

    if src_devcontainer.exists():
        shutil.copytree(src_devcontainer, dst_devcontainer)
    else:
        # Scaffold new .devcontainer
        project_name = git_root.name
        container_name = get_container_name(str(git_root), worktree_name)
        scaffold_devcontainer(container_name, worktree_path)

    print(f'Created worktree: {worktree_path}')
    print(f'Branch: {worktree_name}')

    # Set up secrets in environment
    secrets = get_secrets()
    os.environ.update(secrets)

    # Start devcontainer in worktree
    if not devcontainer_up(worktree_path, remove_existing=args.new):
        sys.exit('Error: Failed to start devcontainer')

    # Attach to tmux
    devcontainer_exec_tmux(worktree_path)


def run_create_mode(args: argparse.Namespace) -> None:
    """Run --create mode: create new project with devcontainer."""
    validate_create_mode(args.create)

    project_name = args.create
    project_path = Path.cwd() / project_name

    # Create project directory
    project_path.mkdir()

    # Initialize git repo
    result = subprocess.run(['git', 'init'], cwd=project_path)
    if result.returncode != 0:
        sys.exit('Error: Failed to initialize git repository')

    # Scaffold .devcontainer
    scaffold_devcontainer(project_name, project_path)

    print(f'Created project: {project_path}')

    # Set up secrets in environment
    secrets = get_secrets()
    os.environ.update(secrets)

    # Start devcontainer
    if not devcontainer_up(project_path, remove_existing=args.new):
        sys.exit('Error: Failed to start devcontainer')

    # Attach to tmux
    devcontainer_exec_tmux(project_path)


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    # Check guards
    check_tmux_guard()

    # Dispatch to appropriate mode
    if args.create:
        run_create_mode(args)
    elif args.tree is not None:
        run_tree_mode(args)
    else:
        run_default_mode(args)


if __name__ == '__main__':
    main()
