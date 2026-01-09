#!/usr/bin/env python3
"""Tests for yolo CLI tool - TDD style."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Import will fail until we create the module
try:
    import yolo
except ImportError:
    yolo = None


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing."""

    def test_no_args_returns_default_mode(self):
        """No arguments should result in default mode."""
        args = yolo.parse_args([])
        self.assertIsNone(args.tree)
        self.assertIsNone(args.create)
        self.assertFalse(args.new)

    def test_help_flag(self):
        """--help should exit with usage info."""
        with self.assertRaises(SystemExit) as cm:
            yolo.parse_args(['--help'])
        self.assertEqual(cm.exception.code, 0)

    def test_tree_with_name(self):
        """--tree NAME should set tree to NAME."""
        args = yolo.parse_args(['--tree', 'feature-x'])
        self.assertEqual(args.tree, 'feature-x')

    def test_tree_without_name(self):
        """--tree without name should set tree to empty string (generate random)."""
        args = yolo.parse_args(['--tree'])
        self.assertEqual(args.tree, '')

    def test_create_with_name(self):
        """--create NAME should set create to NAME."""
        args = yolo.parse_args(['--create', 'myproject'])
        self.assertEqual(args.create, 'myproject')

    def test_create_requires_name(self):
        """--create without NAME should fail."""
        with self.assertRaises(SystemExit):
            yolo.parse_args(['--create'])

    def test_new_flag(self):
        """--new should set new to True."""
        args = yolo.parse_args(['--new'])
        self.assertTrue(args.new)

    def test_new_with_tree(self):
        """--new can combine with --tree."""
        args = yolo.parse_args(['--new', '--tree', 'test'])
        self.assertTrue(args.new)
        self.assertEqual(args.tree, 'test')


class TestGuards(unittest.TestCase):
    """Test guard conditions and validations."""

    def test_tmux_guard_raises_when_in_tmux(self):
        """Should error when TMUX env var is set."""
        with mock.patch.dict(os.environ, {'TMUX': '/tmp/tmux-1000/default,12345,0'}):
            with self.assertRaises(SystemExit) as cm:
                yolo.check_tmux_guard()
            self.assertIn('tmux', str(cm.exception.code).lower())

    def test_tmux_guard_passes_when_not_in_tmux(self):
        """Should pass when TMUX env var is not set."""
        env = os.environ.copy()
        env.pop('TMUX', None)
        with mock.patch.dict(os.environ, env, clear=True):
            # Should not raise
            yolo.check_tmux_guard()


class TestGitDetection(unittest.TestCase):
    """Test git repository detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_find_git_root_at_root(self):
        """Should find git root when at repo root."""
        git_dir = Path(self.tmpdir) / '.git'
        git_dir.mkdir()
        os.chdir(self.tmpdir)

        result = yolo.find_git_root()
        self.assertEqual(result, Path(self.tmpdir))

    def test_find_git_root_in_subdirectory(self):
        """Should find git root when in subdirectory."""
        git_dir = Path(self.tmpdir) / '.git'
        git_dir.mkdir()
        subdir = Path(self.tmpdir) / 'src' / 'lib'
        subdir.mkdir(parents=True)
        os.chdir(subdir)

        result = yolo.find_git_root()
        self.assertEqual(result, Path(self.tmpdir))

    def test_find_git_root_returns_none_outside_repo(self):
        """Should return None when not in a git repo."""
        os.chdir(self.tmpdir)

        result = yolo.find_git_root()
        self.assertIsNone(result)


class TestRandomNameGeneration(unittest.TestCase):
    """Test random name generation for worktrees."""

    def test_generate_random_name_format(self):
        """Should generate adjective-noun format."""
        name = yolo.generate_random_name()
        parts = name.split('-')
        self.assertEqual(len(parts), 2)

    def test_generate_random_name_uses_wordlists(self):
        """Generated name should use defined word lists."""
        name = yolo.generate_random_name()
        adj, noun = name.split('-')
        self.assertIn(adj, yolo.ADJECTIVES)
        self.assertIn(noun, yolo.NOUNS)

    def test_generate_random_name_is_random(self):
        """Should generate different names (probabilistically)."""
        names = {yolo.generate_random_name() for _ in range(20)}
        # With 10 adjectives and 10 nouns, getting same name 20 times is unlikely
        self.assertGreater(len(names), 1)


class TestTemplateSystem(unittest.TestCase):
    """Test .devcontainer template scaffolding."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_scaffold_devcontainer_creates_directory(self):
        """Should create .devcontainer directory."""
        os.chdir(self.tmpdir)
        yolo.scaffold_devcontainer('testproject')

        devcontainer_dir = Path(self.tmpdir) / '.devcontainer'
        self.assertTrue(devcontainer_dir.exists())
        self.assertTrue(devcontainer_dir.is_dir())

    def test_scaffold_devcontainer_creates_json(self):
        """Should create devcontainer.json with project name."""
        os.chdir(self.tmpdir)
        yolo.scaffold_devcontainer('testproject')

        json_file = Path(self.tmpdir) / '.devcontainer' / 'devcontainer.json'
        self.assertTrue(json_file.exists())
        content = json_file.read_text()
        self.assertIn('"name": "testproject"', content)

    def test_scaffold_devcontainer_creates_dockerfile(self):
        """Should create Dockerfile."""
        os.chdir(self.tmpdir)
        yolo.scaffold_devcontainer('testproject')

        dockerfile = Path(self.tmpdir) / '.devcontainer' / 'Dockerfile'
        self.assertTrue(dockerfile.exists())
        content = dockerfile.read_text()
        self.assertIn('FROM localhost/emacs-gui:latest', content)

    def test_scaffold_warns_if_exists(self):
        """Should warn but not error if .devcontainer exists."""
        os.chdir(self.tmpdir)
        devcontainer_dir = Path(self.tmpdir) / '.devcontainer'
        devcontainer_dir.mkdir()
        (devcontainer_dir / 'devcontainer.json').write_text('existing')

        # Should not raise, should return False (not created)
        result = yolo.scaffold_devcontainer('testproject')
        self.assertFalse(result)

        # Original file should be preserved
        content = (devcontainer_dir / 'devcontainer.json').read_text()
        self.assertEqual(content, 'existing')


class TestSecretsManagement(unittest.TestCase):
    """Test secrets fetching from pass and environment."""

    def test_get_secrets_from_env(self):
        """Should get secrets from environment when pass unavailable."""
        env = {
            'ANTHROPIC_API_KEY': 'sk-ant-test123',
            'OPENAI_API_KEY': 'sk-openai-test456'
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch('shutil.which', return_value=None):
                secrets = yolo.get_secrets()

        self.assertEqual(secrets['ANTHROPIC_API_KEY'], 'sk-ant-test123')
        self.assertEqual(secrets['OPENAI_API_KEY'], 'sk-openai-test456')

    def test_get_secrets_from_pass(self):
        """Should get secrets from pass when available."""
        def mock_run(cmd, *args, **kwargs):
            result = mock.Mock()
            result.returncode = 0
            if 'api/llm/anthropic' in cmd:
                result.stdout = 'sk-ant-from-pass\n'
            elif 'api/llm/openai' in cmd:
                result.stdout = 'sk-openai-from-pass\n'
            return result

        with mock.patch('shutil.which', return_value='/usr/bin/pass'):
            with mock.patch('subprocess.run', side_effect=mock_run):
                secrets = yolo.get_secrets()

        self.assertEqual(secrets['ANTHROPIC_API_KEY'], 'sk-ant-from-pass')
        self.assertEqual(secrets['OPENAI_API_KEY'], 'sk-openai-from-pass')


class TestContainerNaming(unittest.TestCase):
    """Test container name generation."""

    def test_container_name_from_project(self):
        """Should derive container name from project directory."""
        name = yolo.get_container_name('/home/user/myproject', None)
        self.assertEqual(name, 'myproject')

    def test_container_name_with_worktree(self):
        """Should include worktree name in container name."""
        name = yolo.get_container_name('/home/user/myproject', 'feature-x')
        self.assertEqual(name, 'myproject-feature-x')

    def test_container_name_lowercase(self):
        """Should convert to lowercase."""
        name = yolo.get_container_name('/home/user/MyProject', None)
        self.assertEqual(name, 'myproject')


class TestWorktreePaths(unittest.TestCase):
    """Test worktree path computation."""

    def test_worktree_path_computation(self):
        """Should compute worktree path as ../PROJECT-worktrees/NAME."""
        path = yolo.get_worktree_path('/dev/myapp', 'feature-x')
        self.assertEqual(path, Path('/dev/myapp-worktrees/feature-x'))

    def test_worktree_path_with_trailing_slash(self):
        """Should handle trailing slash in project path."""
        path = yolo.get_worktree_path('/dev/myapp/', 'feature-x')
        self.assertEqual(path, Path('/dev/myapp-worktrees/feature-x'))


class TestModeValidation(unittest.TestCase):
    """Test validation for different modes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_tree_mode_requires_git_repo(self):
        """--tree should fail if not in git repo."""
        os.chdir(self.tmpdir)  # Not a git repo

        with self.assertRaises(SystemExit) as cm:
            yolo.validate_tree_mode()
        self.assertIn('git', str(cm.exception.code).lower())

    def test_create_mode_forbids_git_repo(self):
        """--create should fail if already in git repo."""
        git_dir = Path(self.tmpdir) / '.git'
        git_dir.mkdir()
        os.chdir(self.tmpdir)

        with self.assertRaises(SystemExit) as cm:
            yolo.validate_create_mode('newproject')
        self.assertIn('git', str(cm.exception.code).lower())

    def test_create_mode_forbids_existing_directory(self):
        """--create should fail if directory exists."""
        os.chdir(self.tmpdir)
        existing = Path(self.tmpdir) / 'existing'
        existing.mkdir()

        with self.assertRaises(SystemExit) as cm:
            yolo.validate_create_mode('existing')
        self.assertIn('exists', str(cm.exception.code).lower())


class TestWorktreeDevcontainer(unittest.TestCase):
    """Test worktree-specific devcontainer configuration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_add_git_mount_to_devcontainer(self):
        """Should add mount for main repo .git directory."""
        import json

        # Create a devcontainer.json
        devcontainer_dir = Path(self.tmpdir) / '.devcontainer'
        devcontainer_dir.mkdir()
        json_file = devcontainer_dir / 'devcontainer.json'

        original = {
            "name": "test",
            "mounts": ["source=/tmp,target=/tmp,type=bind"]
        }
        json_file.write_text(json.dumps(original))

        # Add git mount
        main_git_dir = Path('/home/user/project/.git')
        yolo.add_worktree_git_mount(json_file, main_git_dir)

        # Verify mount was added
        updated = json.loads(json_file.read_text())
        self.assertEqual(len(updated['mounts']), 2)

        git_mount = updated['mounts'][1]
        self.assertIn('/home/user/project/.git', git_mount)
        self.assertIn('source=', git_mount)
        self.assertIn('target=', git_mount)

    def test_add_git_mount_creates_mounts_array(self):
        """Should create mounts array if not present."""
        import json

        devcontainer_dir = Path(self.tmpdir) / '.devcontainer'
        devcontainer_dir.mkdir()
        json_file = devcontainer_dir / 'devcontainer.json'

        original = {"name": "test"}
        json_file.write_text(json.dumps(original))

        main_git_dir = Path('/home/user/project/.git')
        yolo.add_worktree_git_mount(json_file, main_git_dir)

        updated = json.loads(json_file.read_text())
        self.assertIn('mounts', updated)
        self.assertEqual(len(updated['mounts']), 1)


if __name__ == '__main__':
    unittest.main()
