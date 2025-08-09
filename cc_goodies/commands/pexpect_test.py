"""Pexpect test command for testing pexpect functionality."""

import sys
import time
import typer
from typing import Optional
import pexpect
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def pexpect_test_command(
    command: Optional[str] = typer.Argument(
        None,
        help="Command to run with pexpect. If not provided, runs interactive tests."
    ),
    timeout: int = typer.Option(
        30,
        "--timeout", "-t",
        help="Timeout in seconds for pexpect operations"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Run in interactive mode for testing"
    ),
):
    """
    Test pexpect functionality with various commands and scenarios.
    
    Examples:
        cc-goodies pexpect-test
        cc-goodies pexpect-test "echo hello"
        cc-goodies pexpect-test "python3 -c 'name = input(\"Name: \"); print(f\"Hello {name}\")'" -i
    """
    
    console.print("[bold cyan]Pexpect Test Suite[/bold cyan]\n")
    
    if command is None:
        # Run built-in test scenarios
        run_test_suite(timeout)
    else:
        # Run user-provided command
        run_custom_command(command, timeout, interactive)


def run_test_suite(timeout: int):
    """Run a series of pexpect tests."""
    
    tests = [
        ("Basic echo test", test_echo),
        ("Python interactive test", test_python_interactive),
        ("Shell prompt test", test_shell_prompt),
        ("Timeout handling test", test_timeout),
    ]
    
    for name, test_func in tests:
        console.print(f"\n[yellow]Running: {name}[/yellow]")
        try:
            result = test_func(timeout)
            if result:
                console.print(f"[green]✓[/green] {name} passed")
            else:
                console.print(f"[red]✗[/red] {name} failed")
        except Exception as e:
            console.print(f"[red]✗[/red] {name} error: {e}")


def test_echo(timeout: int) -> bool:
    """Test basic echo command."""
    try:
        child = pexpect.spawn('echo "Hello from pexpect"', timeout=timeout)
        child.expect(pexpect.EOF)
        output = child.before.decode() if child.before else ""
        console.print(f"Output: {output.strip()}")
        return "Hello from pexpect" in output
    except Exception as e:
        console.print(f"Error: {e}")
        return False


def test_python_interactive(timeout: int) -> bool:
    """Test Python interactive session."""
    try:
        child = pexpect.spawn('python3', timeout=timeout)
        
        # Wait for Python prompt
        child.expect('>>>')
        console.print("Got Python prompt")
        
        # Send a command
        child.sendline('print("Testing pexpect with Python")')
        child.expect('Testing pexpect with Python')
        console.print("Successfully executed Python command")
        
        # Exit Python
        child.sendline('exit()')
        child.expect(pexpect.EOF)
        
        return True
    except Exception as e:
        console.print(f"Error: {e}")
        return False


def test_shell_prompt(timeout: int) -> bool:
    """Test shell command with prompt detection."""
    try:
        child = pexpect.spawn('/bin/sh', timeout=timeout)
        
        # Wait for shell prompt ($ or #)
        child.expect(['\\$', '#'])
        console.print("Got shell prompt")
        
        # Run a command
        child.sendline('echo $SHELL')
        child.expect(['\\$', '#'])
        output = child.before.decode() if child.before else ""
        console.print(f"Shell output: {output.strip()}")
        
        # Exit shell
        child.sendline('exit')
        child.expect(pexpect.EOF)
        
        return True
    except Exception as e:
        console.print(f"Error: {e}")
        return False


def test_timeout(timeout: int) -> bool:
    """Test timeout handling."""
    try:
        # Use a short timeout for this test
        child = pexpect.spawn('sleep 10', timeout=2)
        child.expect(pexpect.EOF)  # This should timeout
        return False  # Should not reach here
    except pexpect.TIMEOUT:
        console.print("Timeout occurred as expected")
        return True
    except Exception as e:
        console.print(f"Unexpected error: {e}")
        return False


def run_custom_command(command: str, timeout: int, interactive: bool):
    """Run a custom command with pexpect."""
    
    console.print(f"[cyan]Running command:[/cyan] {command}")
    console.print(f"[cyan]Timeout:[/cyan] {timeout} seconds")
    console.print(f"[cyan]Interactive:[/cyan] {interactive}\n")
    
    try:
        child = pexpect.spawn(command, timeout=timeout)
        
        if interactive:
            # Interactive mode - allow user to interact with the spawned process
            console.print("[yellow]Interactive mode - you can interact with the process[/yellow]")
            console.print("[yellow]Press Ctrl+D to exit[/yellow]\n")
            
            child.interact()
        else:
            # Non-interactive mode - just capture and display output
            output_lines = []
            
            while True:
                try:
                    # Read output line by line
                    index = child.expect(['\r\n', '\n', pexpect.EOF, pexpect.TIMEOUT], timeout=1)
                    
                    if child.before:
                        line = child.before.decode('utf-8', errors='replace')
                        output_lines.append(line)
                        console.print(line, end='')
                    
                    if index in [0, 1]:  # newline
                        console.print()  # Print newline
                    elif index == 2:  # EOF
                        break
                    elif index == 3:  # TIMEOUT
                        # Check if process is still alive
                        if not child.isalive():
                            break
                        
                except pexpect.TIMEOUT:
                    # Check if process is still alive
                    if not child.isalive():
                        break
            
            # Get any remaining output
            if child.before:
                remaining = child.before.decode('utf-8', errors='replace')
                if remaining:
                    output_lines.append(remaining)
                    console.print(remaining)
            
            # Wait for process to complete
            child.close()
            
            # Display summary
            console.print(f"\n[green]Process completed with exit code: {child.exitstatus}[/green]")
            
            if output_lines:
                output_text = '\n'.join(output_lines)
                panel = Panel(
                    Syntax(output_text, "text", theme="monokai", line_numbers=False),
                    title="[bold]Output Summary[/bold]",
                    border_style="green"
                )
                console.print("\n", panel)
    
    except pexpect.TIMEOUT:
        console.print(f"\n[red]Command timed out after {timeout} seconds[/red]")
        sys.exit(1)
    except pexpect.ExceptionPexpect as e:
        console.print(f"\n[red]Pexpect error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    typer.run(pexpect_test_command)