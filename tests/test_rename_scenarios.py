"""
Comprehensive tests for complex rename command scenarios.

This test file covers advanced scenarios and state transitions in the rename command
that are not covered by the existing test files, including:
- Fix mismatch mode (--fix-mismatch flag)
- Sync mode detection (when directory already renamed)
- Recovery mode (--recover flag)
- Complete orchestration flow
- Working directory change scenarios
- User confirmation prompts
- GitHub ownership validation
- Complex error scenarios with rollback
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open, call, PropertyMock
import pytest
import subprocess
import shutil
from typing import Dict, List, Optional, Any

from cc_goodies.commands import rename
import click


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_console():
    """Mock the Rich console to avoid actual output during tests."""
    with patch('cc_goodies.commands.rename.console') as mock:
        yield mock


@pytest.fixture
def mock_typer_confirm():
    """Mock typer.confirm for user confirmation prompts."""
    with patch('typer.confirm') as mock:
        mock.return_value = True
        yield mock


# ============================================================================
# FIX MISMATCH MODE TESTS
# ============================================================================

class TestFixMismatchMode:
    """Test the --fix-mismatch flag functionality."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/my-awesome-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='my-awesome-project')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('shutil.move')
    @patch('typer.confirm', return_value=True)
    def test_fix_mismatch_finds_wrong_project(
        self, mock_confirm, mock_move, mock_exists, mock_listdir,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test fix_mismatch when it finds a wrongly named Claude project."""
        # Setup: Claude projects directory contains mismatched project
        # The code checks if current_dir_name is IN the Claude project name
        # So "-blah-my-awesome-project-blah" would match since it contains "my-awesome-project"
        mock_listdir.return_value = [
            '-Users-wei-Projects-v2-my-awesome-project',  # Contains the directory name
            '-Users-wei-Projects-other-project'
        ]
        
        # The wrongly named project exists, correct one doesn't
        def exists_check(path):
            if 'v2-my-awesome-project' in path:
                return True
            if path.endswith('-Users-wei-Projects-my-awesome-project'):
                return False
            return True
        
        mock_exists.side_effect = exists_check
        
        # Run the command
        with pytest.raises(click.exceptions.Exit) as exc_info:
            rename.rename_command(fix_mismatch=True, force=False)
        
        assert exc_info.value.exit_code == 0
        
        # Should have prompted for confirmation
        mock_confirm.assert_called_once()
        
        # Should have attempted to move the mismatched project
        mock_move.assert_called_once()
        expected_old = '/Users/wei/.claude/projects/-Users-wei-Projects-v2-my-awesome-project'
        expected_new = '/Users/wei/.claude/projects/-Users-wei-Projects-my-awesome-project'
        mock_move.assert_called_with(expected_old, expected_new)
        
        # Should print success message
        mock_console.print.assert_any_call("[green]✓ Fixed Claude project mapping![/green]")
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/test-app')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='test-app')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.listdir')
    def test_fix_mismatch_no_mismatch_found(
        self, mock_listdir, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test fix_mismatch when no mismatched project is found."""
        # Claude projects directory doesn't contain anything matching
        mock_listdir.return_value = [
            '-Users-wei-Projects-other-project',
            '-Users-wei-Projects-another-project'
        ]
        
        with pytest.raises(click.exceptions.Exit) as exc_info:
            rename.rename_command(fix_mismatch=True, force=True)
        
        assert exc_info.value.exit_code == 0
        
        # Should print not found message
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('No mismatched Claude project found' in str(call) for call in calls)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/my-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='my-project')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('shutil.move', side_effect=PermissionError("Access denied"))
    @patch('typer.confirm', return_value=True)
    def test_fix_mismatch_move_error(
        self, mock_confirm, mock_move, mock_exists, mock_listdir,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test fix_mismatch when move operation fails."""
        mock_listdir.return_value = ['-Users-wei-Projects-my_project']
        mock_exists.side_effect = [False]  # Target doesn't exist
        
        with pytest.raises(click.exceptions.Exit) as exc_info:
            rename.rename_command(fix_mismatch=True)
        
        assert exc_info.value.exit_code == 0
        
        # Should print error message
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Failed to fix' in str(call) for call in calls)


# ============================================================================
# SYNC MODE TESTS
# ============================================================================

class TestSyncMode:
    """Test sync mode when directory is already renamed."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/new-name')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='new-name')
    @patch('os.path.exists', return_value=True)
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    def test_sync_mode_detection(
        self, mock_auth, mock_subprocess, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test detection of sync mode when directory already has target name."""
        # Git remotes still have old name
        mock_subprocess.side_effect = [
            # get_git_remotes
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-name.git\n'),
            # get_current_repo_name
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-name.git\n'),
            # Additional git operations...
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-name.git\n'),
            # gh repo view
            Mock(returncode=0, stdout=json.dumps({
                'name': 'old-name',
                'owner': {'login': 'user'},
                'viewerCanAdminister': True
            })),
            # gh api user
            Mock(returncode=0, stdout='user\n'),
            # gh repo rename
            Mock(returncode=0),
            # git remote set-url
            Mock(returncode=0),
        ]
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-name', force=True, only_remotes=True)
        
        # Should print sync mode message
        mock_console.print.assert_any_call(
            "[cyan]📍 Sync mode: Directory already has target name, checking other components...[/cyan]"
        )
        mock_console.print.assert_any_call("  • Git remotes still use old name: old-name")
        mock_console.print.assert_any_call("  • Will update to match directory: new-name")
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project-name')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project-name')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_sync_mode_claude_project_check(
        self, mock_subprocess, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test sync mode checking Claude project status."""
        # Directory and Claude project already match
        def exists_check(path):
            if 'claude/projects' in path and 'project-name' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_check
        
        # Git remotes already match too
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='origin\tgit@github.com:user/project-name.git\n'
        )
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('project-name', force=True, dry_run=True)
        
        # Should detect everything is already in sync
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('already' in str(call).lower() or 'sync' in str(call).lower() for call in calls)


# ============================================================================
# RECOVERY MODE TESTS
# ============================================================================

class TestRecoveryMode:
    """Test recovery mode for partially completed renames."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='old-project')
    @patch('os.path.exists')
    @patch('os.chdir')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('subprocess.run')
    def test_recovery_mode_directory_already_renamed(
        self, mock_subprocess, mock_chdir, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test recovery when directory was renamed but remotes weren't."""
        # Directory already renamed
        def exists_check(path):
            if '/Users/wei/Projects/new-project' == str(path):
                return True
            if '/Users/wei/Projects/old-project' == str(path):
                return False
            if 'claude' in str(path) and 'new-project' in str(path):
                return True
            if 'claude' in str(path) and 'old-project' in str(path):
                return False
            return False
        
        mock_exists.side_effect = exists_check
        
        # Git remotes still have old name
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='origin\tgit@github.com:user/old-project.git\n'
        )
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-project', recover=True, force=True, only_remotes=True)
        
        # Should detect partial rename
        mock_console.print.assert_any_call(
            "[cyan]🔄 Recovery mode: Checking for partial rename...[/cyan]"
        )
        mock_console.print.assert_any_call(
            "[yellow]Directory appears to be already renamed to: /Users/wei/Projects/new-project[/yellow]"
        )
        
        # Should switch to new directory
        mock_chdir.assert_called_with('/Users/wei/Projects/new-project')
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/current-dir')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='current-dir')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('os.path.exists')
    def test_recovery_mode_claude_already_renamed(
        self, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test recovery when Claude project was already renamed."""
        # Claude project renamed, directory not
        def exists_check(path):
            if 'claude' in str(path) and 'new-dir' in str(path):
                return True
            if 'claude' in str(path) and 'current-dir' in str(path):
                return False
            if '/Users/wei/Projects/new-dir' == str(path):
                return False
            return True
        
        mock_exists.side_effect = exists_check
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout='')
            
            with pytest.raises(click.exceptions.Exit):
                rename.rename_command('new-dir', recover=True, force=True, dry_run=True)
        
        # Should detect Claude project already renamed
        mock_console.print.assert_any_call("[green]✓ Claude project already renamed[/green]")


# ============================================================================
# ORCHESTRATION FLOW TESTS
# ============================================================================

class TestOrchestrationFlow:
    """Test the complete orchestration flow with all components."""
    
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
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    def test_complete_rename_flow_with_working_directory_change(
        self, mock_gogs_config, mock_gh_auth, mock_confirm,
        mock_requests_patch, mock_requests_get, mock_subprocess,
        mock_move, mock_chdir, mock_exists, mock_basename,
        mock_dirname, mock_getcwd, mock_console
    ):
        """Test complete rename with working directory change."""
        # Setup mocks
        mock_exists.side_effect = [
            False,  # New directory doesn't exist
            True,   # Old Claude project exists
            False,  # New Claude project doesn't exist
            True,   # Additional checks
        ] * 2  # Repeat for multiple checks
        
        mock_gogs_config.return_value = {
            'GOGS_API_TOKEN': 'test-token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'testuser'
        }
        
        # Mock subprocess calls
        mock_subprocess.side_effect = [
            # Initial git operations
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-project.git\n'),
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-project.git\n'),
            Mock(returncode=0, stdout='origin\tgit@github.com:user/old-project.git\n'),
            # GitHub operations
            Mock(returncode=0, stdout=json.dumps({
                'name': 'old-project',
                'owner': {'login': 'user'},
                'viewerCanAdminister': True
            })),
            Mock(returncode=0, stdout='user\n'),
            Mock(returncode=0),  # gh repo rename
            # Git remote update
            Mock(returncode=0),
        ]
        
        # Mock Gogs API
        mock_requests_get.return_value = Mock(status_code=200)
        mock_requests_patch.return_value = Mock(status_code=200)
        
        # Execute rename
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-project', force=True)
        
        # Verify operations were performed in correct order
        assert mock_move.call_count >= 1  # Directory and/or Claude project moved
        assert mock_chdir.called  # Working directory changed
        assert mock_subprocess.call_count >= 3  # Git operations performed
        
        # Verify success messages
        mock_console.print.assert_any_call('[green]✓[/green] Directory renamed successfully')
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('shutil.move', side_effect=[None, OSError("Permission denied")])
    @patch('subprocess.run')
    @patch('os.chdir')
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    def test_rollback_on_claude_project_rename_failure(
        self, mock_chdir, mock_subprocess, mock_move, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test rollback when Claude project rename fails after directory rename."""
        mock_subprocess.return_value = Mock(returncode=0, stdout='')
        
        # Directory rename succeeds, Claude project rename fails
        with pytest.raises(click.exceptions.Exit) as exc_info:
            rename.rename_command('new-name', force=True)
        
        # Should exit with error
        assert exc_info.value.exit_code == 1
        
        # Should print error about Claude project rename failure
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Failed' in str(call) for call in calls)


# ============================================================================
# USER CONFIRMATION TESTS
# ============================================================================

class TestUserConfirmation:
    """Test user confirmation prompts in various scenarios."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/important-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='important-project')
    @patch('os.path.exists', return_value=False)
    @patch('os.path.expanduser', lambda x: x.replace('~', '/Users/wei'))
    @patch('os.path.join', lambda *args: '/'.join(args))
    @patch('typer.confirm')
    @patch('subprocess.run')
    def test_confirmation_prompt_not_forced(
        self, mock_subprocess, mock_confirm, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test that confirmation is requested when not forced."""
        mock_confirm.return_value = False  # User declines
        # Mock git remotes to avoid issues
        mock_subprocess.return_value = Mock(returncode=0, stdout='')
        
        with pytest.raises(click.exceptions.Exit) as exc_info:
            rename.rename_command('new-name', force=False, dry_run=False)
        
        # Should have asked for confirmation
        mock_confirm.assert_called()
        
        # Should exit without performing operations
        assert exc_info.value.exit_code == 0
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('typer.confirm')
    @patch('subprocess.run')
    def test_no_confirmation_when_forced(
        self, mock_subprocess, mock_confirm, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test that confirmation is skipped when forced."""
        mock_subprocess.return_value = Mock(returncode=0, stdout='')
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-name', force=True, dry_run=True)
        
        # Should NOT have asked for confirmation
        mock_confirm.assert_not_called()


# ============================================================================
# GITHUB OWNERSHIP VALIDATION TESTS
# ============================================================================

class TestGitHubOwnershipValidation:
    """Test GitHub repository ownership validation."""
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    def test_github_ownership_check_organization(
        self, mock_auth, mock_subprocess, mock_console
    ):
        """Test GitHub rename blocked for organization repositories."""
        mock_subprocess.side_effect = [
            # gh repo view - organization owned
            Mock(returncode=0, stdout=json.dumps({
                'name': 'repo',
                'owner': {'login': 'some-org'},
                'viewerCanAdminister': True
            })),
            # gh api user
            Mock(returncode=0, stdout='my-user\n'),
        ]
        
        result = rename.rename_github_repo('repo', 'new-repo', dry_run=False)
        
        assert result is False
        
        # Should print ownership error
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Cannot rename: Repository is owned by 'some-org'" in str(call) for call in calls)
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    def test_github_ownership_check_bypass(
        self, mock_auth, mock_subprocess, mock_console
    ):
        """Test bypassing GitHub ownership check."""
        mock_subprocess.side_effect = [
            # gh repo view
            Mock(returncode=0, stdout=json.dumps({
                'name': 'repo',
                'owner': {'login': 'org'}
            })),
            # gh repo rename (skipped ownership check)
            Mock(returncode=0),
        ]
        
        result = rename.rename_github_repo(
            'repo', 'new-repo', dry_run=False, skip_ownership_check=True
        )
        
        assert result is True
        
        # Should have performed rename without checking ownership
        assert mock_subprocess.call_count == 2  # view and rename


# ============================================================================
# COMPLEX ERROR SCENARIOS
# ============================================================================

class TestComplexErrorScenarios:
    """Test complex error scenarios and recovery."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists')
    @patch('shutil.move')
    @patch('os.chdir')
    @patch('subprocess.run')
    @patch('requests.get')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_multiple_failures_with_partial_success(
        self, mock_gogs_config, mock_gh_auth, mock_requests_get,
        mock_subprocess, mock_chdir, mock_move, mock_exists,
        mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test handling multiple failures with some successes."""
        mock_exists.return_value = False
        
        # Directory rename succeeds
        mock_move.side_effect = [None, None]  # Both moves succeed
        
        # GitHub fails
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout='origin\tgit@github.com:user/project.git\n'),
            Mock(returncode=0, stdout='origin\tgit@github.com:user/project.git\n'),
            Mock(returncode=0, stdout='origin\tgit@github.com:user/project.git\n'),
            Mock(returncode=0, stdout=json.dumps({'name': 'project', 'owner': {'login': 'user'}})),
            Mock(returncode=0, stdout='user\n'),
            Mock(returncode=1, stderr='API rate limit exceeded'),  # GitHub rename fails
        ]
        
        # Gogs fails
        mock_gogs_config.return_value = {
            'GOGS_API_TOKEN': 'token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'user'
        }
        mock_requests_get.side_effect = Exception("Network error")
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-name', force=True)
        
        # Should show partial success
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Directory renamed successfully' in str(call) for call in calls)
        assert any('Failed' in str(call) or 'Error' in str(call) for call in calls)
    
    @patch('os.getcwd', return_value='/restricted/project')
    @patch('os.path.dirname', return_value='/restricted')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('shutil.move', side_effect=OSError("Read-only filesystem"))
    def test_filesystem_error_stops_operation(
        self, mock_move, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test that filesystem errors stop the entire operation."""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout='')
            
            with pytest.raises(SystemExit) as exc_info:
                rename.rename_command('new-name', force=True)
        
        # Should exit with error
        assert exc_info.value.exit_code == 1
        
        # Should show filesystem error
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Read-only filesystem' in str(call) or 'Failed' in str(call) for call in calls)


# ============================================================================
# EDGE CASES AND SPECIAL SCENARIOS
# ============================================================================

class TestEdgeCasesAndSpecialScenarios:
    """Test edge cases and special scenarios."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    def test_new_path_option_with_full_path(
        self, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test using --new-path with a full path to move project."""
        new_path = Path('/Users/wei/NewLocation/renamed-project')
        
        with patch('os.path.exists', return_value=False):
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0, stdout='')
                
                with pytest.raises(click.exceptions.Exit):
                    rename.rename_command(new_path=new_path, force=True, dry_run=True)
        
        # Should use the full path
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('/Users/wei/NewLocation/renamed-project' in str(call) for call in calls)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    def test_both_name_and_path_provided(
        self, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test behavior when both new_name and new_path are provided."""
        # new_path should take precedence
        new_path = Path('/Different/Location/different-name')
        
        with patch('os.path.exists', return_value=False):
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0, stdout='')
                
                with pytest.raises(click.exceptions.Exit):
                    rename.rename_command(
                        new_name='ignored-name',
                        new_path=new_path,
                        force=True,
                        dry_run=True
                    )
        
        # Should use the path, not the name
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('different-name' in str(call) for call in calls)
        assert not any('ignored-name' in str(call) for call in calls)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('subprocess.run')
    def test_only_claude_flag(
        self, mock_subprocess, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test --only-claude flag to skip remote operations."""
        mock_subprocess.return_value = Mock(returncode=0, stdout='')
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-name', only_claude=True, force=True, dry_run=True)
        
        # Should not attempt any git operations
        mock_subprocess.assert_not_called()
        
        # Should mention only Claude operations
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Claude' in str(call) for call in calls)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=True)  # Directory already exists
    @patch('subprocess.run')
    def test_only_remotes_flag(
        self, mock_subprocess, mock_exists, mock_basename, mock_dirname, mock_getcwd, mock_console
    ):
        """Test --only-remotes flag to skip Claude project operations."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='origin\tgit@github.com:user/project.git\n'
        )
        
        with patch('shutil.move') as mock_move:
            with pytest.raises(click.exceptions.Exit):
                rename.rename_command('project', only_remotes=True, force=True, dry_run=True)
            
            # Should not attempt to move any directories
            mock_move.assert_not_called()


# ============================================================================
# DRY RUN MODE COMPREHENSIVE TESTS
# ============================================================================

class TestDryRunModeComprehensive:
    """Comprehensive tests for dry-run mode across all operations."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('shutil.move')
    @patch('subprocess.run')
    @patch('requests.get')
    @patch('requests.patch')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.load_gogs_config')
    def test_dry_run_complete_flow(
        self, mock_gogs_config, mock_gh_auth, mock_patch, mock_get,
        mock_subprocess, mock_move, mock_exists, mock_basename,
        mock_dirname, mock_getcwd, mock_console
    ):
        """Test that dry-run mode doesn't perform any actual operations."""
        mock_gogs_config.return_value = {
            'GOGS_API_TOKEN': 'token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'user'
        }
        
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='origin\tgit@github.com:user/project.git\n'
        )
        mock_get.return_value = Mock(status_code=200)
        
        with pytest.raises(click.exceptions.Exit):
            rename.rename_command('new-name', force=True, dry_run=True)
        
        # No actual operations should be performed
        mock_move.assert_not_called()
        mock_patch.assert_not_called()
        
        # Should show dry-run messages
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('Would' in str(call) or 'DRY RUN' in str(call) or 'dry' in str(call).lower() for call in calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])