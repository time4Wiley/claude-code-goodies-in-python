"""
Comprehensive tests for the rename command - Additional coverage.

This file contains additional tests to achieve 100% coverage, focusing on
complex command scenarios and edge cases.
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open, call
import pytest
import click

from cc_goodies.commands import rename


class TestMainCommandScenarios:
    """Test complex scenarios in the main rename command."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/old-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename')
    @patch('os.path.expanduser')
    @patch('os.path.join')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('shutil.move')
    @patch('cc_goodies.commands.rename.console')
    def test_fix_mismatch_finds_and_fixes(
        self, mock_console, mock_move, mock_listdir, mock_exists,
        mock_join, mock_expanduser, mock_basename, mock_dirname, mock_getcwd
    ):
        """Test fix_mismatch when it finds a mismatched project."""
        # Setup mocks
        mock_basename.return_value = 'old-project'
        mock_expanduser.side_effect = lambda x: x.replace('~', '/Users/wei')
        mock_join.side_effect = lambda *args: '/'.join(args)
        
        # Claude projects directory contains a mismatched project
        mock_listdir.return_value = [
            '-Users-wei-Projects-wrong-project',
            '-Users-wei-Projects-other-project'
        ]
        
        # Simulate that the wrong one exists but correct one doesn't
        def exists_side_effect(path):
            if 'wrong-project' in path:
                return True
            if '-Users-wei-Projects-old-project' in path:
                return False
            return True
        
        mock_exists.side_effect = exists_side_effect
        
        # Run the command
        with pytest.raises(SystemExit) as exc_info:
            rename.rename_command(fix_mismatch=True, force=True)
        
        assert exc_info.value.code == 0
        # Should have attempted to move the mismatched project
        mock_move.assert_called_once()
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/new-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='new-project')
    @patch('os.path.expanduser')
    @patch('os.path.join')
    @patch('os.path.exists')
    @patch('os.chdir')
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.console')
    def test_recover_mode_with_partial_rename(
        self, mock_console, mock_subprocess, mock_chdir, 
        mock_exists, mock_join, mock_expanduser,
        mock_basename, mock_dirname, mock_getcwd
    ):
        """Test recover mode when directory was already renamed."""
        mock_expanduser.side_effect = lambda x: x.replace('~', '/Users/wei')
        mock_join.side_effect = lambda *args: '/'.join(args)
        
        # Setup: new directory exists, old doesn't; Claude project already renamed
        def exists_side_effect(path):
            if '/Users/wei/Projects/new-project' in str(path):
                return True
            if '/Users/wei/Projects/old-project' in str(path):
                return False
            if '-Users-wei-Projects-new-project' in str(path):
                return True
            if '-Users-wei-Projects-old-project' in str(path):
                return False
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock git remotes that still have old name
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='origin\tgit@github.com:user/old-project.git (fetch)\n'
        )
        
        with pytest.raises(SystemExit) as exc_info:
            rename.rename_command(
                'new-project',
                recover=True,
                force=True,
                github=False,
                gogs=False
            )
        
        # Should have detected the partial rename and handled it
        assert exc_info.value.code == 0
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project-name')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project-name')
    @patch('os.path.exists', return_value=False)
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.console')
    def test_github_rename_skip_ownership_check(
        self, mock_console, mock_auth, mock_subprocess,
        mock_exists, mock_basename, mock_dirname, mock_getcwd
    ):
        """Test GitHub rename with skip_ownership_check flag."""
        # Mock subprocess calls
        mock_subprocess.side_effect = [
            # get_git_remotes
            Mock(returncode=0, stdout='origin\tgit@github.com:org/project-name.git\n'),
            # get_current_repo_name
            Mock(returncode=0, stdout='origin\tgit@github.com:org/project-name.git\n'),
            # get_git_remotes for table
            Mock(returncode=0, stdout='origin\tgit@github.com:org/project-name.git\n'),
            # gh repo view
            Mock(returncode=0, stdout='{"name": "project-name", "owner": {"login": "org"}}'),
            # gh repo rename
            Mock(returncode=0, stdout=''),
            # git remote set-url
            Mock(returncode=0, stdout=''),
        ]
        
        with pytest.raises(SystemExit):
            rename.rename_command(
                'new-name',
                skip_github_check=True,
                force=True,
                only_remotes=True
            )
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='project')
    @patch('os.path.exists', return_value=False)
    @patch('cc_goodies.commands.rename.load_gogs_config')
    @patch('requests.get')
    @patch('requests.patch')
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.console')
    def test_gogs_rename_with_missing_api_url(
        self, mock_console, mock_subprocess, mock_patch, mock_get,
        mock_config, mock_exists, mock_basename, mock_dirname, mock_getcwd
    ):
        """Test Gogs rename when API URL needs to be constructed."""
        # Config without GOGS_API_URL
        mock_config.return_value = {
            'GOGS_API_TOKEN': 'token',
            'GOGS_HOSTNAME': 'gogs.example.com',
            'GOGS_PORT': '3000',
            'GOGS_USER': 'testuser'
        }
        
        # Mock subprocess for git operations
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='gogs\thttp://testuser@gogs.example.com:3000/testuser/project.git\n'
        )
        
        # Mock successful API calls
        mock_get.return_value = Mock(status_code=200)
        mock_patch.return_value = Mock(status_code=200)
        
        with pytest.raises(SystemExit):
            rename.rename_command(
                'new-project',
                force=True,
                only_remotes=True,
                github=False
            )
        
        # Verify API calls were made with constructed URL
        mock_get.assert_called_once()
        assert 'gogs.example.com:3000' in str(mock_get.call_args)
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/my-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='my-project')
    @patch('os.path.exists', return_value=False)
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.console')
    def test_update_git_remotes_various_formats(
        self, mock_console, mock_subprocess,
        mock_exists, mock_basename, mock_dirname, mock_getcwd
    ):
        """Test updating git remotes with various URL formats."""
        # Mock git remotes with different formats
        mock_subprocess.side_effect = [
            # get_git_remotes - various formats
            Mock(
                returncode=0,
                stdout=(
                    'origin\tgit@github.com:user/my-project.git\n'
                    'backup\tssh://git@backup.com:22/user/my-project\n'
                    'mirror\thttps://mirror.com/user/my-project\n'
                )
            ),
            # get_current_repo_name
            Mock(
                returncode=0,
                stdout='origin\tgit@github.com:user/my-project.git\n'
            ),
            # get_git_remotes for update
            Mock(
                returncode=0,
                stdout=(
                    'origin\tgit@github.com:user/my-project.git\n'
                    'backup\tssh://git@backup.com:22/user/my-project\n'
                    'mirror\thttps://mirror.com/user/my-project\n'
                )
            ),
            # git remote set-url calls
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0),
        ]
        
        with pytest.raises(SystemExit):
            rename.rename_command(
                'new-name',
                force=True,
                only_remotes=True,
                github=False,
                gogs=False
            )
        
        # Should have updated all three remotes
        assert mock_subprocess.call_count >= 3


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.console')
    def test_github_rename_organization_repo(
        self, mock_console, mock_auth, mock_subprocess
    ):
        """Test GitHub rename error for organization repository."""
        mock_subprocess.side_effect = [
            # gh repo view
            Mock(returncode=0, stdout='{"name": "repo", "owner": {"login": "org"}}'),
            # gh api user
            Mock(returncode=0, stdout='user\n'),
            # gh repo rename fails
            Mock(
                returncode=1,
                stderr='You need organization owner permissions to rename this repository'
            )
        ]
        
        result = rename.rename_github_repo('repo', 'new-repo', dry_run=False)
        
        assert result is False
        # Should have detected it's an org repo
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('organization' in call.lower() or 'permission' in call.lower() for call in calls)
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.console')
    def test_github_rename_json_parse_error(
        self, mock_console, mock_auth, mock_subprocess
    ):
        """Test GitHub rename when JSON parsing fails."""
        mock_subprocess.side_effect = [
            # gh repo view with invalid JSON
            Mock(returncode=0, stdout='not valid json'),
            # gh repo rename - should still try
            Mock(returncode=0)
        ]
        
        result = rename.rename_github_repo(
            'repo', 'new-repo', dry_run=False, skip_ownership_check=True
        )
        
        assert result is True
    
    @patch('cc_goodies.commands.rename.load_gogs_config')
    @patch('requests.get')
    @patch('cc_goodies.commands.rename.console')
    def test_gogs_rename_repo_not_found(
        self, mock_console, mock_get, mock_config
    ):
        """Test Gogs rename when repository is not found."""
        mock_config.return_value = {
            'GOGS_API_TOKEN': 'token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'user'
        }
        
        mock_get.return_value = Mock(status_code=404)
        
        result = rename.rename_gogs_repo('repo', 'new-repo', dry_run=False)
        
        assert result is False
        mock_console.print.assert_called_with(
            '[yellow]Repository not found on Gogs or no access[/yellow]'
        )
    
    @patch('os.path.exists', return_value=True)
    @patch('shutil.move', side_effect=PermissionError("Access denied"))
    @patch('cc_goodies.commands.rename.console')
    def test_rename_with_permission_error(
        self, mock_console, mock_move, mock_exists
    ):
        """Test handling of permission errors during rename."""
        result = rename.rename_filesystem_directory(
            '/protected/dir', '/new/dir', dry_run=False
        )
        
        assert result is False
        mock_console.print.assert_called_with(
            '[red]Failed to rename directory: Access denied[/red]'
        )


class TestDryRunMode:
    """Test dry-run mode for all operations."""
    
    @patch('os.path.exists', side_effect=[True, False])
    @patch('shutil.move')
    @patch('cc_goodies.commands.rename.console')
    def test_dry_run_filesystem(self, mock_console, mock_move, mock_exists):
        """Test dry-run mode for filesystem operations."""
        result = rename.rename_filesystem_directory(
            '/old/path', '/new/path', dry_run=True
        )
        
        assert result is True
        mock_move.assert_not_called()
        mock_console.print.assert_called_with(
            '[cyan]Would rename directory:[/cyan] /old/path → /new/path'
        )
    
    @patch('subprocess.run')
    @patch('cc_goodies.commands.rename.check_gh_auth', return_value=True)
    @patch('cc_goodies.commands.rename.console')
    def test_dry_run_github(self, mock_console, mock_auth, mock_subprocess):
        """Test dry-run mode for GitHub operations."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"name": "repo", "owner": {"login": "user"}}'
        )
        
        result = rename.rename_github_repo(
            'repo', 'new-repo', dry_run=True, skip_ownership_check=True
        )
        
        assert result is True
        # Should not have called rename
        assert mock_subprocess.call_count == 1  # Only view, not rename
        mock_console.print.assert_called_with(
            '[cyan]Would rename GitHub repo:[/cyan] repo → new-repo'
        )
    
    @patch('cc_goodies.commands.rename.load_gogs_config')
    @patch('requests.get')
    @patch('requests.patch')
    @patch('cc_goodies.commands.rename.console')
    def test_dry_run_gogs(
        self, mock_console, mock_patch, mock_get, mock_config
    ):
        """Test dry-run mode for Gogs operations."""
        mock_config.return_value = {
            'GOGS_API_TOKEN': 'token',
            'GOGS_API_URL': 'http://localhost:3000/api/v1',
            'GOGS_USER': 'user'
        }
        
        mock_get.return_value = Mock(status_code=200)
        
        result = rename.rename_gogs_repo('repo', 'new-repo', dry_run=True)
        
        assert result is True
        mock_patch.assert_not_called()
        mock_console.print.assert_called_with(
            '[cyan]Would rename Gogs repo:[/cyan] repo → new-repo'
        )


class TestPathHandling:
    """Test various path handling scenarios."""
    
    @patch('os.getcwd', return_value='/Users/wei/Projects/my-project')
    @patch('os.path.dirname', return_value='/Users/wei/Projects')
    @patch('os.path.basename', return_value='my-project')
    @patch('os.path.exists', return_value=False)
    @patch('cc_goodies.commands.rename.console')
    def test_new_path_option(
        self, mock_console, mock_exists,
        mock_basename, mock_dirname, mock_getcwd
    ):
        """Test using --new-path option for moving projects."""
        from pathlib import Path
        
        with patch('cc_goodies.commands.rename.get_current_repo_name', return_value='my-project'):
            with patch('cc_goodies.commands.rename.get_git_remotes', return_value={}):
                with pytest.raises(SystemExit):
                    rename.rename_command(
                        new_path=Path('/Users/wei/NewProjects/renamed-project'),
                        force=True,
                        dry_run=True
                    )
        
        # Should show the new path in output
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any('renamed-project' in call for call in calls)


class TestHelperFunctions:
    """Test remaining helper functions and edge cases."""
    
    def test_path_to_claude_project_name_empty(self):
        """Test path conversion with empty string."""
        assert rename.path_to_claude_project_name('') == ''
    
    def test_path_to_claude_project_name_special_chars(self):
        """Test path conversion with various special characters."""
        test_cases = [
            ('path!@#$%^&*()', 'path----------'),
            ('path_with_underscores', 'path-with-underscores'),
            ('path.with.dots', 'path-with-dots'),
            ('パス/日本語/test', '---test'),  # Non-ASCII chars
        ]
        
        for input_path, expected in test_cases:
            assert rename.path_to_claude_project_name(input_path) == expected
    
    @patch('subprocess.run')
    def test_get_git_remotes_malformed_output(self, mock_subprocess):
        """Test get_git_remotes with malformed output."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='malformed output without tabs\norigin git@github.com:user/repo.git'
        )
        
        remotes = rename.get_git_remotes()
        # Should handle malformed lines gracefully
        assert remotes == {}
    
    @patch('cc_goodies.commands.rename.get_git_remotes')
    def test_get_current_repo_name_colon_in_path(self, mock_get_remotes):
        """Test repo name extraction with colon in path."""
        mock_get_remotes.return_value = {
            'origin': 'file:///C:/Users/repo.git'
        }
        
        assert rename.get_current_repo_name() == 'repo'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])