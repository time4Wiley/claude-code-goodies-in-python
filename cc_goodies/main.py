"""Main entry point for cc-goodies CLI."""

import typer
from typing import Optional

from cc_goodies.commands.progress import progress_command
from cc_goodies.commands.status import status_command
from cc_goodies.commands.pexpect_test import pexpect_test_command
from cc_goodies.commands.rename import rename_command

app = typer.Typer(
    name="cc-goodies",
    help="Claude Code Goodies - A collection of useful tools for Claude AI",
    add_completion=True,
    no_args_is_help=True,
)

# Add subcommands
app.command(name="progress", help="Track Claude's thinking progress")(progress_command)
app.command(name="status", help="Display system status with rich formatting")(status_command)
app.command(name="pexpect-test", help="Test pexpect functionality")(pexpect_test_command)
app.command(name="rename", help="Rename Claude Code project and remote repositories")(rename_command)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, 
        "--version", 
        "-v", 
        help="Show version and exit",
        is_eager=True,
    )
):
    """
    Claude Code Goodies - Useful tools for working with Claude AI.
    
    A collection of CLI tools to enhance your Claude experience, including:
    - Progress tracking for long-running Claude queries
    - (More tools coming soon!)
    
    Use --install-completion to enable shell auto-completion.
    """
    if version:
        from cc_goodies import __version__
        typer.echo(f"cc-goodies version {__version__}")
        raise typer.Exit()
    
    # Show help if no command is provided
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()