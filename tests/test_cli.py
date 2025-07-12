import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from testpilot import cli


def test_cli_parser():
    """Test that CLI parser works correctly."""
    parser = cli.create_parser()
    
    # Test generate command parsing
    args = parser.parse_args(['generate', 'test.py', '--use-context', '--validate'])
    assert args.command == 'generate'
    assert args.source_file == 'test.py'
    assert args.use_context is True
    assert args.validate is True
    assert args.provider == 'openai'  # default
    
    # Test run command parsing
    args = parser.parse_args(['run', 'test_file.py', '--create-issues', '--repo', 'user/repo'])
    assert args.command == 'run'
    assert args.test_file == 'test_file.py'
    assert args.create_issues is True
    assert args.repo == 'user/repo'


def test_cli_generate_command_basic():
    """Test basic generate command functionality without API calls."""
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def add(a, b):
    """Add two numbers."""
    return a + b
''')
        temp_file = f.name

    try:
        # Mock the core generation function to avoid API calls
        with patch('testpilot.cli.generate_tests_llm') as mock_generate:
            mock_generate.return_value = "def test_add():\n    assert True"
            
            # Create mock args for generate command
            args = MagicMock()
            args.source_file = temp_file
            args.provider = 'openai'
            args.model = None
            args.api_key = 'fake-key'
            args.temperature = None
            args.max_tokens = None
            args.use_context = False
            args.validate = False
            args.show_analysis = False
            args.show_validation = False
            args.prompt_file = None
            args.prompt_name = None
            args.output = None
            args.overwrite = True
            args.append = False
            args.quiet = True
            args.run = False
            
            result = cli.handle_generate_command(args)
            assert result == 0  # Success
            
            # Verify the function was called
            mock_generate.assert_called_once()
            
            # Check that a test file was created
            expected_output = f"test_{Path(temp_file).name}"
            assert os.path.exists(expected_output)
            
            # Clean up generated test file
            if os.path.exists(expected_output):
                os.unlink(expected_output)
    
    finally:
        # Clean up temp file
        os.unlink(temp_file)
