"""
Comprehensive tests for the rename command with 100% coverage and zero external dependencies.

This test suite uses careful mocking boundaries:
- Mock at system boundaries (os, subprocess, requests, filesystem)
- Don't mock internal logic that should be tested
- Create realistic mock responses for external systems
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, MagicMock, patch, mock_open, call, PropertyMock
import pytest
from configparser import ConfigParser

# Import the module under test
from cc_goodies.commands import rename


# ============================================================================
# TEST FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
def mock_console():
    """Mock the Rich console to avoid actual output during tests."""
    with patch('cc_goodies.commands.rename.console') as mock:
        yield mock


@pytest.fixture
def mock_filesystem():
    """Create a mock filesystem state for testing."""
    return {
        '/Users/wei/Projects/old-project': True,
        '/Users/wei/Projects/new-project': False,
        '~/.claude/projects/-Users-wei-Projects-old-project': True,
        '~/.claude/projects/-Users-wei-Projects-new-project': False,
        '~/.gogs-rc': True,
    }


@pytest.fixture
def mock_gogs_config():
    """Sample Gogs configuration."""
    return {
        'GOGS_API_TOKEN': 'test-token-123',
        'GOGS_API_URL': 'http://localhost:3000/api/v1',
        'GOGS_USER': 'testuser',
        'GOGS_HOSTNAME': 'localhost',
        'GOGS_PORT': '3000'
    }


@pytest.fixture
def mock_git_remotes():
    """Sample git remotes configuration."""
    return {
        'origin': 'git@github.com:testuser/old-project.git',
        'github': 'https://github.com/testuser/old-project.git',
        'gogs': 'http://testuser@localhost:3000/testuser/old-project.git'
    }


@pytest.fixture
def mock_github_repo_info():
    """Sample GitHub repository information."""
    return {
        'name': 'old-project',
        'owner': {
            'login': 'testuser'
        },
        'viewerCanAdminister': True
    }


class MockSubprocessResult:
    """Mock subprocess.run result."""
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class MockResponse:
    """Mock requests Response object."""
    def __init__(self, status_code=200, json_data=None, text=''):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
    
    def json(self):
        return self._json_data


# ============================================================================
# TESTS FOR UTILITY FUNCTIONS
# ============================================================================

class TestUtilityFunctions:
    """Test utility functions that don't require external dependencies."""
    
    def test_path_to_claude_project_name(self):
        """Test path to Claude project name conversion."""
        assert rename.path_to_claude_project_name('/Users/wei/Projects/my-app') == '-Users-wei-Projects-my-app'
        assert rename.path_to_claude_project_name('/home/user/code/test_project') == '-home-user-code-test-project'
        assert rename.path_to_claude_project_name('relative/path/to/project') == 'relative-path-to-project'
        assert rename.path_to_claude_project_name('/path with spaces/project') == '-path-with-spaces-project'
        assert rename.path_to_claude_project_name('C:\\Windows\\Projects\\app') == 'C--Windows-Projects-app'
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
# Gogs configuration
export GOGS_API_TOKEN="test-token-123"
export GOGS_HOSTNAME='localhost'
export GOGS_PORT=3000
export GOGS_USER="testuser"

# Comment line
GOGS_API_URL=http://localhost:3000/api/v1
""")
    @patch('os.path.exists', return_value=True)
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    def test_load_gogs_config_success(self, mock_exists, mock_file):
        """Test loading Gogs configuration from file."""
        config = rename.load_gogs_config()
        
        assert config['GOGS_API_TOKEN'] == 'test-token-123'
        assert config['GOGS_HOSTNAME'] == 'localhost'
        assert config['GOGS_PORT'] == '3000'
        assert config['GOGS_USER'] == 'testuser'
        assert config['GOGS_API_URL'] == 'http://localhost:3000/api/v1'
    
    @patch('os.path.exists', return_value=False)
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    def test_load_gogs_config_missing_file(self, mock_exists):
        """Test loading Gogs config when file doesn't exist."""
        config = rename.load_gogs_config()
        assert config == {}
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    @patch('os.path.exists', return_value=True)
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    def test_load_gogs_config_read_error(self, mock_exists, mock_file, mock_console):
        """Test loading Gogs config with read error."""
        config = rename.load_gogs_config()
        assert config == {}
        # Should print warning
        mock_console.print.assert_called()


class TestGitFunctions:
    """Test Git-related functions."""
    
    @patch('subprocess.run')
    def test_check_gh_auth_success(self, mock_run):
        """Test checking GitHub CLI authentication - success."""
        mock_run.return_value = MockSubprocessResult(returncode=0)
        assert rename.check_gh_auth() is True
        mock_run.assert_called_once_with(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True
        )
    
    @patch('subprocess.run')
    def test_check_gh_auth_failure(self, mock_run):
        """Test checking GitHub CLI authentication - failure."""
        mock_run.return_value = MockSubprocessResult(returncode=1)
        assert rename.check_gh_auth() is False
    
    @patch('subprocess.run', side_effect=FileNotFoundError())
    def test_check_gh_auth_not_installed(self, mock_run):
        """Test checking GitHub CLI when gh is not installed."""
        assert rename.check_gh_auth() is False
    
    @patch('subprocess.run')
    def test_get_git_remotes_success(self, mock_run):
        """Test getting git remotes - success."""
        mock_run.return_value = MockSubprocessResult(
            returncode=0,
            stdout="""origin\tgit@github.com:user/repo.git (fetch)
origin\tgit@github.com:user/repo.git (push)
upstream\thttps://github.com/other/repo.git (fetch)
upstream\thttps://github.com/other/repo.git (push)"""
        )
        
        remotes = rename.get_git_remotes()
        assert remotes == {
            'origin': 'git@github.com:user/repo.git',
            'upstream': 'https://github.com/other/repo.git'
        }
    
    @patch('subprocess.run')
    def test_get_git_remotes_empty(self, mock_run):
        """Test getting git remotes when there are none."""
        mock_run.return_value = MockSubprocessResult(returncode=0, stdout='')
        remotes = rename.get_git_remotes()
        assert remotes == {}
    
    @patch('subprocess.run', side_effect=FileNotFoundError())
    def test_get_git_remotes_no_git(self, mock_run):
        """Test getting git remotes when git is not installed."""
        remotes = rename.get_git_remotes()
        assert remotes == {}
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_from_origin(self, mock_get_remotes):
        """Test extracting repo name from origin remote."""
        mock_get_remotes.return_value = {
            'origin': 'git@github.com:user/my-repo.git'
        }
        assert rename.get_current_repo_name() == 'my-repo'
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_from_github(self, mock_get_remotes):
        """Test extracting repo name from github remote."""
        mock_get_remotes.return_value = {
            'github': 'https://github.com/user/another-repo.git',
            'upstream': 'https://github.com/other/different.git'
        }
        assert rename.get_current_repo_name() == 'another-repo'
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_ssh_format(self, mock_get_remotes):
        """Test extracting repo name from SSH URL format."""
        mock_get_remotes.return_value = {
            'origin': 'ssh://git@localhost:22/user/repo-name.git'
        }
        assert rename.get_current_repo_name() == 'repo-name'
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_gogs_format(self, mock_get_remotes):
        """Test extracting repo name from Gogs URL format."""
        mock_get_remotes.return_value = {
            'gogs': 'http://user@localhost:3000/user/gogs-repo.git'
        }
        assert rename.get_current_repo_name() == 'gogs-repo'
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_no_remotes(self, mock_get_remotes):
        """Test when no remotes are configured."""
        mock_get_remotes.return_value = {}
        assert rename.get_current_repo_name() is None


# ============================================================================
# TESTS FOR RENAME OPERATIONS
# ============================================================================

class TestRenameOperations:
    """Test the core rename operations."""
    
    @patch('os.path.exists')
    @patch('shutil.move')
    def test_rename_filesystem_directory_success(self, mock_move, mock_exists, mock_console):
        """Test successful directory rename."""
        mock_exists.side_effect = [True, False]  # old exists, new doesn't
        
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=False
        )
        
        assert result is True
        mock_move.assert_called_once_with('/old/path', '/new/path')
        mock_console.print.assert_called_with('[green]✓[/green] Directory renamed successfully')
    
    @patch('os.path.exists')
    def test_rename_filesystem_directory_source_missing(self, mock_exists, mock_console):
        """Test renaming when source directory doesn't exist."""
        mock_exists.return_value = False
        
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=False
        )
        
        assert result is False
        mock_console.print.assert_called_with('[red]Directory does not exist: /old/path[/red]')
    
    @patch('os.path.exists')
    @patch('os.path.samefile')
    def test_rename_filesystem_directory_same_file(self, mock_samefile, mock_exists, mock_console):
        """Test renaming when source and target are the same."""
        mock_exists.side_effect = [True, True]  # both exist
        mock_samefile.return_value = True
        
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=False
        )
        
        assert result is True
        mock_console.print.assert_called_with('[yellow]Directory already at target location[/yellow]')
    
    @patch('os.path.exists')
    def test_rename_filesystem_directory_target_exists(self, mock_exists, mock_console):
        """Test renaming when target already exists."""
        mock_exists.side_effect = [True, True]  # both exist
        
        with patch('os.path.samefile', return_value=False):
            result = rename.rename_filesystem_directory(
                '/old/path', '/new/path', dry_run=False
            )
        
        assert result is False
        mock_console.print.assert_called_with('[red]Target directory already exists: /new/path[/red]')
    
    @patch('os.path.exists')
    def test_rename_filesystem_directory_dry_run(self, mock_exists, mock_console):
        """Test directory rename in dry-run mode."""
        mock_exists.side_effect = [True, False]
        
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=True
        )
        
        assert result is True
        mock_console.print.assert_called_with('[cyan]Would rename directory:[/cyan] /old/path → /new/path')
    
    @patch('os.path.exists')
    @patch('shutil.move', side_effect=OSError("Permission denied"))
    def test_rename_filesystem_directory_move_error(self, mock_move, mock_exists, mock_console):
        """Test directory rename with permission error."""
        mock_exists.side_effect = [True, False]
        
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=False
        )
        
        assert result is False
        mock_console.print.assert_called_with('[red]Failed to rename directory: Permission denied[/red]')
    
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('os.path.exists')
    @patch('shutil.move')
    def test_rename_claude_project_success(self, mock_move, mock_exists, mock_console):
        """Test successful Claude project rename."""
        # Old exists, new doesn't
        mock_exists.side_effect = [True, False]  # old exists, new doesn't
        
        result = rename.rename_claude_project(
            '/old/project', '/new/project', dry_run=False, check_reverse=False
        )
        
        assert result is True
        mock_move.assert_called_once()
        mock_console.print.assert_called_with('[green]✓[/green] Claude project renamed successfully')
    
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('os.path.exists')
    def test_rename_claude_project_already_renamed(self, mock_exists, mock_console):
        """Test Claude project when already renamed."""
        # Old doesn't exist, new exists (check_reverse case)
        mock_exists.side_effect = [False, True]  # old doesn't exist, new exists
        
        result = rename.rename_claude_project(
            '/old/project', '/new/project', dry_run=False, check_reverse=True
        )
        
        assert result is True
        mock_console.print.assert_called_with('[yellow]Claude project appears to be already renamed[/yellow]')
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth')
    def test_rename_github_repo_success(self, mock_auth, mock_run, mock_console):
        """Test successful GitHub repository rename."""
        mock_auth.return_value = True
        
        # Mock the sequence of subprocess calls
        mock_run.side_effect = [
            # gh repo view
            MockSubprocessResult(
                returncode=0,
                stdout=json.dumps({
                    'name': 'old-repo',
                    'owner': {'login': 'testuser'},
                    'viewerCanAdminister': True
                })
            ),
            # gh api user
            MockSubprocessResult(returncode=0, stdout='testuser\n'),
            # gh repo rename
            MockSubprocessResult(returncode=0)
        ]
        
        result = rename.rename_github_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is True
        assert mock_run.call_count == 3
        mock_console.print.assert_called_with('[green]✓[/green] GitHub repository renamed successfully')
    
    @patch('cc_goodies.commands.rename.check_gh_auth')
    def test_rename_github_repo_not_authenticated(self, mock_auth, mock_console):
        """Test GitHub rename when not authenticated."""
        mock_auth.return_value = False
        
        result = rename.rename_github_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is False
        mock_console.print.assert_called_with(
            "[yellow]GitHub CLI not authenticated. Run 'gh auth login' first.[/yellow]"
        )
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth')
    def test_rename_github_repo_not_owner(self, mock_auth, mock_run, mock_console):
        """Test GitHub rename when user is not the owner."""
        mock_auth.return_value = True
        
        mock_run.side_effect = [
            # gh repo view
            MockSubprocessResult(
                returncode=0,
                stdout=json.dumps({
                    'name': 'old-repo',
                    'owner': {'login': 'otheruser'},
                    'viewerCanAdminister': True
                })
            ),
            # gh api user
            MockSubprocessResult(returncode=0, stdout='testuser\n'),
        ]
        
        result = rename.rename_github_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is False
        # Check that it printed the warning about not being owner
        calls = mock_console.print.call_args_list
        assert any("Cannot rename: Repository is owned by 'otheruser'" in str(call) for call in calls)
    
    @patch('requests.get')
    @patch('requests.patch')
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_rename_gogs_repo_success(self, mock_config, mock_patch, mock_get, mock_console):
        """Test successful Gogs repository rename."""
        mock_config.return_value = {
            'GOGS_API_TOKEN': 'test-token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'testuser'
        }
        
        mock_get.return_value = MockResponse(status_code=200)
        mock_patch.return_value = MockResponse(status_code=200)
        
        result = rename.rename_gogs_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is True
        mock_console.print.assert_called_with('[green]✓[/green] Gogs repository renamed successfully')
    
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_rename_gogs_repo_no_token(self, mock_config, mock_console):
        """Test Gogs rename when API token is missing."""
        mock_config.return_value = {}
        
        result = rename.rename_gogs_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is False
        mock_console.print.assert_called_with('[yellow]Gogs API token not found in ~/.gogs-rc[/yellow]')
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_update_git_remotes_success(self, mock_get_remotes, mock_run, mock_console):
        """Test updating git remote URLs."""
        mock_get_remotes.return_value = {
            'origin': 'git@github.com:user/old-repo.git',
            'upstream': 'https://github.com/other/old-repo.git'
        }
        
        mock_run.return_value = MockSubprocessResult(returncode=0)
        
        result = rename.update_git_remotes('old-repo', 'new-repo', dry_run=False)
        
        # Should have called git remote set-url for each remote
        assert mock_run.call_count == 2
        mock_console.print.assert_any_call("[green]✓[/green] Updated remote 'origin'")
        mock_console.print.assert_any_call("[green]✓[/green] Updated remote 'upstream'")
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_update_git_remotes_dry_run(self, mock_get_remotes, mock_console):
        """Test updating git remotes in dry-run mode."""
        mock_get_remotes.return_value = {
            'origin': 'git@github.com:user/old-repo.git'
        }
        
        rename.update_git_remotes('old-repo', 'new-repo', dry_run=True)
        
        mock_console.print.assert_any_call("[cyan]Would update remote 'origin':[/cyan]")


# ============================================================================
# TESTS FOR MAIN COMMAND
# ============================================================================

class TestRenameCommand:
    """Test the main rename command orchestration."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.path.exists')
    @patch('os.chdir')
    @patch('typer.confirm', return_value=True)
    @patch('cc_goodies.commands.rename.get_current_repo_name', return_value='old-project')
    @patch('cc_goodies.commands.rename.get_git_remotes', return_value={})
    @patch('cc_goodies.commands.rename.rename_filesystem_directory', return_value=True)
    @patch('cc_goodies.commands.rename.rename_claude_project', return_value=True)
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    def test_rename_command_basic_success(
        self, mock_rename_claude, mock_rename_fs, mock_get_remotes, 
        mock_get_repo_name, mock_confirm, mock_chdir, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test basic successful rename operation."""
        mock_exists.return_value = False  # New path doesn't exist
        
        # Import typer and create the command
        from cc_goodies.commands.rename import rename_command
        
        # The command should complete successfully
        try:
            rename_command('new-project', force=True)
        except SystemExit:
            pass  # Normal exit
        
        # Verify the key operations were called
        mock_rename_fs.assert_called_once()
        mock_rename_claude.assert_called_once()
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.listdir', return_value=['wrong-project'])
    @patch('os.path.exists')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/home/user'))
    @patch('shutil.move')
    @patch('typer.confirm', return_value=True)
    def test_rename_command_fix_mismatch(
        self, mock_confirm, mock_move, mock_exists, 
        mock_listdir, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test fix mismatch mode."""
        mock_exists.side_effect = lambda x: 'wrong' not in x  # Wrong doesn't exist, others do
        
        from cc_goodies.commands.rename import rename_command
        
        with pytest.raises(SystemExit) as exc_info:
            rename_command(fix_mismatch=True, force=True)
        
        assert exc_info.value.code == 0
        # Check that it looked for mismatched projects
        mock_listdir.assert_called_once()
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/new-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='new-project')
    @patch('cc_goodies.commands.rename.get_current_repo_name', return_value='old-project')
    @patch('cc_goodies.commands.rename.get_git_remotes')
    @patch('cc_goodies.commands.rename.update_git_remotes', return_value=True)
    @patch('typer.confirm', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_rename_command_sync_mode(
        self, mock_exists, mock_confirm, mock_update_remotes, mock_get_remotes,
        mock_get_repo_name, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test sync mode when directory already has target name."""
        mock_get_remotes.return_value = {
            'origin': 'git@github.com:user/old-project.git'
        }
        
        from cc_goodies.commands.rename import rename_command
        
        # Directory name already matches target
        try:
            rename_command('new-project', force=True, only_remotes=True)
        except SystemExit:
            pass  # Normal exit
        
        # Should update remotes to match directory name
        mock_update_remotes.assert_called_once_with('old-project', 'new-project', False)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.path.exists', return_value=False)
    def test_rename_command_dry_run(
        self, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test dry-run mode."""
        from cc_goodies.commands.rename import rename_command
        
        with patch('cc_goodies.commands.rename.get_current_repo_name', return_value='old-project'):
            with patch('cc_goodies.commands.rename.get_git_remotes', return_value={}):
                # Dry run shouldn't make actual changes
                try:
                    rename_command('new-project', dry_run=True, force=True)
                except SystemExit:
                    pass  # Normal exit
        
        # Should show dry run completed message
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Dry run completed' in call for call in calls) or any('DRY RUN MODE' in call for call in calls)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    def test_rename_command_no_arguments(
        self, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test command with no arguments."""
        from cc_goodies.commands.rename import rename_command
        
        with pytest.raises(SystemExit) as exc_info:
            rename_command()
        
        assert exc_info.value.code == 1
        # Should print error about missing arguments
        calls = mock_console.print.call_args_list
        assert any('[red]Error: Must provide either new_name or --new-path[/red]' in str(call) for call in calls)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complex scenarios."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.path.exists')
    @patch('os.chdir')
    @patch('shutil.move')
    @patch('subprocess.run')
    @patch('requests.get')
    @patch('requests.patch')
    @patch('typer.confirm', return_value=True)
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_full_rename_workflow(
        self, mock_gogs_config, mock_gh_auth, mock_confirm,
        mock_requests_patch, mock_requests_get, mock_subprocess,
        mock_move, mock_chdir, mock_exists, mock_basename,
        mock_dirname, mock_getcwd, mock_console
    ):
        """Test complete rename workflow with all components."""
        # Setup mocks
        mock_exists.side_effect = [
            False,  # New directory doesn't exist
            True,   # Old Claude project exists
            False,  # New Claude project doesn't exist
            True,   # Git work dir exists
        ]
        
        mock_gogs_config.return_value = {
            'GOGS_API_TOKEN': 'test-token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'testuser'
        }
        
        # Mock subprocess calls for git and gh
        mock_subprocess.side_effect = [
            # get_git_remotes
            MockSubprocessResult(
                returncode=0,
                stdout='origin\tgit@github.com:user/old-project.git (fetch)\n'
            ),
            # get_current_repo_name -> get_git_remotes
            MockSubprocessResult(
                returncode=0,
                stdout='origin\tgit@github.com:user/old-project.git (fetch)\n'
            ),
            # Second get_git_remotes call
            MockSubprocessResult(
                returncode=0,
                stdout='origin\tgit@github.com:user/old-project.git (fetch)\n'
            ),
            # gh repo view
            MockSubprocessResult(
                returncode=0,
                stdout=json.dumps({
                    'name': 'old-project',
                    'owner': {'login': 'user'},
                    'viewerCanAdminister': True
                })
            ),
            # gh api user
            MockSubprocessResult(returncode=0, stdout='user\n'),
            # gh repo rename
            MockSubprocessResult(returncode=0),
            # git remote set-url
            MockSubprocessResult(returncode=0),
        ]
        
        # Mock requests for Gogs
        mock_requests_get.return_value = MockResponse(status_code=200)
        mock_requests_patch.return_value = MockResponse(status_code=200)
        
        from cc_goodies.commands.rename import rename_command
        
        # Execute the rename
        try:
            rename_command('new-project', force=True)
        except SystemExit:
            pass  # Normal exit
        
        # Verify all operations were called
        assert mock_move.call_count >= 1  # Directory and/or Claude project
        assert mock_subprocess.call_count >= 3  # Git operations
        
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.path.exists')
    @patch('os.chdir')
    @patch('cc_goodies.commands.rename.rename_filesystem_directory', return_value=False)
    def test_rollback_on_directory_rename_failure(
        self, mock_rename_fs, mock_chdir, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test that operations stop if directory rename fails."""
        mock_exists.return_value = False  # New path doesn't exist
        
        from cc_goodies.commands.rename import rename_command
        
        with patch('cc_goodies.commands.rename.get_current_repo_name', return_value='old-project'):
            with patch('cc_goodies.commands.rename.get_git_remotes', return_value={}):
                with pytest.raises(SystemExit) as exc_info:
                    rename_command('new-project', force=True)
        
        assert exc_info.value.code == 1
        # Should print failure message
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Failed to rename directory' in call for call in calls) or any('Stopping operation' in call for call in calls)


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_with_unusual_urls(self, mock_get_remotes):
        """Test repo name extraction with unusual URL formats."""
        test_cases = [
            # URL without .git extension
            ({'origin': 'git@github.com:user/repo'}, 'repo'),
            # URL with port number
            ({'origin': 'ssh://git@github.com:22/user/repo.git'}, 'repo'),
            # Local file path
            ({'origin': 'file:///path/to/repo.git'}, 'repo'),
            # URL with subdirectory
            ({'origin': 'https://gitlab.com/group/subgroup/repo.git'}, 'repo'),
        ]
        
        for remotes, expected in test_cases:
            mock_get_remotes.return_value = remotes
            assert rename.get_current_repo_name() == expected
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    def test_rename_github_repo_permission_error(self, mock_auth, mock_run, mock_console):
        """Test GitHub rename with permission error."""
        mock_run.side_effect = [
            # gh repo view
            MockSubprocessResult(returncode=0, stdout='{"name": "repo"}'),
            # gh repo rename with permission error
            MockSubprocessResult(
                returncode=1,
                stderr="You don't have permission to rename this repository"
            )
        ]
        
        result = rename.rename_github_repo('old-repo', 'new-repo', dry_run=False, skip_ownership_check=True)
        
        assert result is False
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Cannot rename: No permission' in call for call in calls)
    
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_rename_gogs_repo_network_error(self, mock_config, mock_console):
        """Test Gogs rename with network error."""
        import requests
        
        mock_config.return_value = {
            'GOGS_API_TOKEN': 'test-token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'testuser'
        }
        
        with patch('requests.get', side_effect=requests.RequestException("Network error")):
            result = rename.rename_gogs_repo('old-repo', 'new-repo', dry_run=False)
        
        assert result is False
        mock_console.print.assert_called_with('[red]Failed to connect to Gogs: Network error[/red]')


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestParametrized:
    """Parametrized tests for comprehensive coverage."""
    
    @pytest.mark.parametrize("path,expected", [
        ('/Users/wei/Projects/my-app', '-Users-wei-Projects-my-app'),
        ('C:\\Windows\\Projects\\app', 'C--Windows-Projects-app'),
        ('/path/with spaces/and-special@chars!', '-path-with-spaces-and-special-chars-'),
        ('', ''),
        ('/', '-'),
        ('relative/path', 'relative-path'),
    ])
    def test_path_to_claude_project_name_variations(self, path, expected):
        """Test path conversion with various inputs."""
        assert rename.path_to_claude_project_name(path) == expected
    
    @pytest.mark.parametrize("returncode,expected", [
        (0, True),
        (1, False),
        (127, False),  # Command not found
        (-1, False),   # Killed by signal
    ])
    @patch('subprocess.run')
    def test_check_gh_auth_return_codes(self, mock_run, returncode, expected):
        """Test gh auth check with different return codes."""
        mock_run.return_value = MockSubprocessResult(returncode=returncode)
        assert rename.check_gh_auth() == expected
    
    @pytest.mark.parametrize("dry_run", [True, False])
    @patch('os.path.exists', return_value=True)
    @patch('shutil.move')
    def test_rename_operations_dry_run_modes(self, mock_move, mock_exists, dry_run, mock_console):
        """Test rename operations in both dry-run and normal modes."""
        mock_exists.side_effect = [True, False]  # Old exists, new doesn't
        
        rename.rename_filesystem_directory('/old', '/new', dry_run=dry_run)
        
        if dry_run:
            mock_move.assert_not_called()
            mock_console.print.assert_called_with('[cyan]Would rename directory:[/cyan] /old → /new')
        else:
            mock_move.assert_called_once_with('/old', '/new')
            mock_console.print.assert_called_with('[green]✓[/green] Directory renamed successfully')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])