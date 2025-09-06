"""Comprehensive tests for recursive Claude project operations."""

import os
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cc_goodies.commands.mv import (
    find_all_claude_projects,
    validate_all_project_updates,
    update_all_claude_projects,
    TransactionManager
)
from cc_goodies.commands.rename import (
    find_all_claude_projects as rename_find_all_claude_projects,
    validate_all_project_renames,
    rename_all_claude_projects
)


class TestRecursiveProjectDiscovery:
    """Test recursive Claude project discovery functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.fake_claude_projects = tempfile.mkdtemp()
        
        # Create test directory structure
        self.root_project = os.path.join(self.temp_dir, "main-project")
        self.nested_project = os.path.join(self.root_project, "sub", "nested-project")
        self.deep_project = os.path.join(self.root_project, "very", "deep", "path", "deep-project")
        
        os.makedirs(self.root_project)
        os.makedirs(self.nested_project)
        os.makedirs(self.deep_project)
        
        # Create corresponding Claude project directories
        self.root_claude_name = self.root_project.replace("/", "-").replace("\\", "-")
        self.nested_claude_name = self.nested_project.replace("/", "-").replace("\\", "-")
        self.deep_claude_name = self.deep_project.replace("/", "-").replace("\\", "-")
        
        os.makedirs(os.path.join(self.fake_claude_projects, self.root_claude_name))
        os.makedirs(os.path.join(self.fake_claude_projects, self.nested_claude_name))
        os.makedirs(os.path.join(self.fake_claude_projects, self.deep_claude_name))
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.fake_claude_projects, ignore_errors=True)
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_find_all_claude_projects_basic(self, mock_expanduser):
        """Test basic recursive project discovery."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        projects = find_all_claude_projects(self.root_project)
        
        assert len(projects) == 3
        
        # Check root project
        root_found = [p for p in projects if p['relative_path'] == '.']
        assert len(root_found) == 1
        assert root_found[0]['path'] == self.root_project
        
        # Check nested projects
        nested_paths = [p['relative_path'] for p in projects if p['relative_path'] != '.']
        expected_relative_paths = [
            os.path.relpath(self.nested_project, self.root_project),
            os.path.relpath(self.deep_project, self.root_project)
        ]
        
        for expected in expected_relative_paths:
            assert expected in nested_paths
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_find_all_claude_projects_no_projects(self, mock_expanduser):
        """Test discovery when no Claude projects exist."""
        mock_expanduser.return_value = "/nonexistent/claude/projects"
        
        projects = find_all_claude_projects(self.root_project)
        
        assert len(projects) == 0
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_find_all_claude_projects_partial_projects(self, mock_expanduser):
        """Test discovery when only some subdirectories are Claude projects."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        # Remove one Claude project
        shutil.rmtree(os.path.join(self.fake_claude_projects, self.deep_claude_name))
        
        projects = find_all_claude_projects(self.root_project)
        
        assert len(projects) == 2
        project_paths = [p['path'] for p in projects]
        assert self.root_project in project_paths
        assert self.nested_project in project_paths
        assert self.deep_project not in project_paths


class TestProjectUpdateValidation:
    """Test validation of project update operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.fake_claude_projects = tempfile.mkdtemp()
        
        # Create test projects
        self.projects = [
            {
                'path': os.path.join(self.temp_dir, 'project1'),
                'project_name': 'project1',
                'relative_path': '.'
            },
            {
                'path': os.path.join(self.temp_dir, 'project1', 'sub'),
                'project_name': 'project1-sub',
                'relative_path': 'sub'
            }
        ]
        
        # Create corresponding Claude project directories
        for project in self.projects:
            claude_path = os.path.join(self.fake_claude_projects, project['project_name'])
            os.makedirs(claude_path)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.fake_claude_projects, ignore_errors=True)
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_validate_all_project_updates_success(self, mock_expanduser):
        """Test successful validation of all project updates."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        old_root = os.path.join(self.temp_dir, 'project1')
        new_root = os.path.join(self.temp_dir, 'project1-renamed')
        
        valid, errors = validate_all_project_updates(self.projects, old_root, new_root)
        
        assert valid is True
        assert len(errors) == 0
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_validate_all_project_updates_missing_source(self, mock_expanduser):
        """Test validation failure when source project is missing."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        # Remove one source project
        shutil.rmtree(os.path.join(self.fake_claude_projects, 'project1'))
        
        old_root = os.path.join(self.temp_dir, 'project1')
        new_root = os.path.join(self.temp_dir, 'project1-renamed')
        
        valid, errors = validate_all_project_updates(self.projects, old_root, new_root)
        
        assert valid is False
        assert len(errors) == 1
        assert "Source project missing: project1" in errors[0]
    
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_validate_all_project_updates_target_exists(self, mock_expanduser):
        """Test validation failure when target project already exists."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        old_root = os.path.join(self.temp_dir, 'project1')
        new_root = os.path.join(self.temp_dir, 'project1-renamed')
        
        # Create conflicting target project
        new_project_name = new_root.replace("/", "-").replace("\\", "-")
        os.makedirs(os.path.join(self.fake_claude_projects, new_project_name))
        
        valid, errors = validate_all_project_updates(self.projects, old_root, new_root)
        
        assert valid is False
        assert len(errors) == 1
        assert "Target project already exists" in errors[0]


class TestTransactionManager:
    """Test transaction management and rollback functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.fake_claude_projects = tempfile.mkdtemp()
        self.transaction = TransactionManager()
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.fake_claude_projects, ignore_errors=True)
    
    def test_add_operation(self):
        """Test adding operations to transaction."""
        self.transaction.add_operation(
            'move_directory',
            '/old/path',
            '/new/path',
            {'metadata': 'test'}
        )
        
        assert len(self.transaction.operations) == 1
        op = self.transaction.operations[0]
        assert op['type'] == 'move_directory'
        assert op['source'] == '/old/path'
        assert op['target'] == '/new/path'
        assert op['metadata']['metadata'] == 'test'
        assert op['completed'] is False
    
    def test_validate_operations_conflict(self):
        """Test validation fails with conflicting operations."""
        self.transaction.add_operation('move_directory', '/path1', '/target')
        self.transaction.add_operation('move_directory', '/path2', '/target')
        
        valid, errors = self.transaction.validate_all_operations()
        
        assert valid is False
        assert len(errors) == 1
        assert "Conflict: Multiple operations target /target" in errors[0]
    
    @patch('cc_goodies.commands.mv.console')
    def test_execute_move_directory_dry_run(self, mock_console):
        """Test directory move in dry run mode."""
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir)
        
        self.transaction.add_operation('move_directory', source_dir, target_dir)
        
        result = self.transaction.execute_all_operations(dry_run=True)
        
        assert result is True
        assert os.path.exists(source_dir)  # Source still exists in dry run
        assert not os.path.exists(target_dir)  # Target not created in dry run
    
    @patch('cc_goodies.commands.mv.console')
    def test_execute_move_directory_real(self, mock_console):
        """Test actual directory move."""
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir)
        
        # Create a file in source to verify move
        test_file = os.path.join(source_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test content')
        
        self.transaction.add_operation('move_directory', source_dir, target_dir)
        
        result = self.transaction.execute_all_operations(dry_run=False)
        
        assert result is True
        assert not os.path.exists(source_dir)  # Source moved
        assert os.path.exists(target_dir)  # Target created
        assert os.path.exists(os.path.join(target_dir, 'test.txt'))  # File moved
    
    @patch('cc_goodies.commands.mv.console')
    def test_rollback_move_directory(self, mock_console):
        """Test rollback of directory move operation."""
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir)
        
        # Create test file
        test_file = os.path.join(source_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test content')
        
        self.transaction.add_operation('move_directory', source_dir, target_dir)
        
        # Execute first operation
        operation = self.transaction.operations[0]
        result = self.transaction.execute_operation(operation, dry_run=False)
        assert result is True
        self.transaction.completed_operations.append(operation)
        
        # Verify move happened
        assert not os.path.exists(source_dir)
        assert os.path.exists(target_dir)
        
        # Rollback
        self.transaction.rollback()
        
        # Verify rollback
        assert os.path.exists(source_dir)  # Source restored
        assert not os.path.exists(target_dir)  # Target removed
        assert os.path.exists(os.path.join(source_dir, 'test.txt'))  # File restored
    
    @patch('cc_goodies.commands.mv.console')
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_execute_rename_claude_project(self, mock_expanduser, mock_console):
        """Test Claude project rename operation."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        # Create source Claude project
        source_name = 'old-project'
        target_name = 'new-project'
        source_path = os.path.join(self.fake_claude_projects, source_name)
        os.makedirs(source_path)
        
        # Create test file in project
        test_file = os.path.join(source_path, 'config.json')
        with open(test_file, 'w') as f:
            f.write('{"test": "config"}')
        
        self.transaction.add_operation('rename_claude_project', source_name, target_name)
        
        result = self.transaction.execute_all_operations(dry_run=False)
        
        assert result is True
        
        # Verify rename
        target_path = os.path.join(self.fake_claude_projects, target_name)
        assert not os.path.exists(source_path)  # Source moved
        assert os.path.exists(target_path)  # Target created
        assert os.path.exists(os.path.join(target_path, 'config.json'))  # File moved


class TestIntegrationScenarios:
    """Test complex integration scenarios with multiple nested projects."""
    
    def setup_method(self):
        """Set up complex test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.fake_claude_projects = tempfile.mkdtemp()
        
        # Create complex project structure
        self.create_complex_project_structure()
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.fake_claude_projects, ignore_errors=True)
    
    def create_complex_project_structure(self):
        """Create a complex nested project structure for testing."""
        # Main project with multiple nested projects
        structure = {
            'main-app': {
                'frontend': {},  # Claude project
                'backend': {
                    'api': {},  # Claude project
                    'database': {}  # Not a Claude project
                },
                'shared': {
                    'utils': {}  # Claude project
                }
            }
        }
        
        def create_dirs(base_path, struct, claude_projects):
            for name, children in struct.items():
                dir_path = os.path.join(base_path, name)
                os.makedirs(dir_path, exist_ok=True)
                
                # Create corresponding Claude project for some directories
                if name in ['main-app', 'frontend', 'api', 'utils']:
                    claude_name = dir_path.replace("/", "-").replace("\\", "-")
                    claude_path = os.path.join(claude_projects, claude_name)
                    os.makedirs(claude_path, exist_ok=True)
                    
                    # Add some content to Claude projects
                    config_file = os.path.join(claude_path, 'settings.json')
                    with open(config_file, 'w') as f:
                        f.write(f'{{"project": "{name}"}}')
                
                if children:
                    create_dirs(dir_path, children, claude_projects)
        
        create_dirs(self.temp_dir, structure, self.fake_claude_projects)
        
        self.main_app_path = os.path.join(self.temp_dir, 'main-app')
    
    @patch('cc_goodies.commands.mv.console')
    @patch('cc_goodies.commands.mv.os.path.expanduser')
    def test_complex_recursive_update(self, mock_expanduser, mock_console):
        """Test recursive update of complex project structure."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        # Find all Claude projects
        projects = find_all_claude_projects(self.main_app_path)
        
        # Should find: main-app, frontend, api, utils (4 projects)
        assert len(projects) >= 4
        
        # Verify specific projects are found
        project_names = [p['project_name'] for p in projects]
        main_app_name = self.main_app_path.replace("/", "-").replace("\\", "-")
        assert main_app_name in project_names
        
        # Test update validation
        new_root = os.path.join(self.temp_dir, 'renamed-main-app')
        valid, errors = validate_all_project_updates(projects, self.main_app_path, new_root)
        
        assert valid is True
        assert len(errors) == 0
        
        # Test actual update in dry run mode
        result = update_all_claude_projects(self.main_app_path, new_root, dry_run=True)
        
        assert result is True
    
    @patch('cc_goodies.commands.mv.console')
    @patch('cc_goodies.commands.mv.os.path.expanduser') 
    def test_partial_project_failure_recovery(self, mock_expanduser, mock_console):
        """Test recovery from partial project update failures."""
        mock_expanduser.return_value = self.fake_claude_projects
        
        # Find projects and simulate failure scenario
        projects = find_all_claude_projects(self.main_app_path)
        
        # Remove one Claude project to simulate missing source
        if projects:
            missing_project = projects[1]  # Remove second project
            missing_path = os.path.join(self.fake_claude_projects, missing_project['project_name'])
            if os.path.exists(missing_path):
                shutil.rmtree(missing_path)
        
        new_root = os.path.join(self.temp_dir, 'renamed-main-app')
        
        # Validation should fail
        valid, errors = validate_all_project_updates(projects, self.main_app_path, new_root)
        
        assert valid is False
        assert len(errors) > 0
        assert any("Source project missing" in error for error in errors)


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transaction = TransactionManager()
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('cc_goodies.commands.mv.console')
    def test_permission_error_handling(self, mock_console):
        """Test handling of permission errors."""
        # Create source directory
        source_dir = os.path.join(self.temp_dir, 'source')
        os.makedirs(source_dir)
        
        # Create target in a way that will cause permission error
        target_dir = "/root/system_protected_dir"  # Should fail
        
        self.transaction.add_operation('move_directory', source_dir, target_dir)
        
        # Should handle permission error gracefully
        result = self.transaction.execute_all_operations(dry_run=False)
        
        assert result is False
        # Source directory should still exist after failed operation
        assert os.path.exists(source_dir)
    
    @patch('cc_goodies.commands.mv.console')
    @patch('cc_goodies.commands.mv.shutil.move')
    def test_rollback_failure_handling(self, mock_move, mock_console):
        """Test handling of rollback failures."""
        source_dir = os.path.join(self.temp_dir, 'source')
        target_dir = os.path.join(self.temp_dir, 'target')
        os.makedirs(source_dir)
        
        self.transaction.add_operation('move_directory', source_dir, target_dir)
        
        # First move succeeds
        operation = self.transaction.operations[0]
        operation['rollback_data'] = {
            'action': 'move_back',
            'original_source': source_dir,
            'original_target': target_dir
        }
        operation['completed'] = True
        self.transaction.completed_operations.append(operation)
        
        # Mock rollback failure
        mock_move.side_effect = OSError("Rollback failed")
        
        # Rollback should handle the error gracefully
        self.transaction.rollback()
        
        # Should not crash, should log error
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Failed to rollback operation" in call for call in calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])