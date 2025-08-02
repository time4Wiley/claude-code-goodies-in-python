"""Main entry point for cc-goodies CLI."""

import typer
from typing import Optional

from cc_goodies.commands.progress import progress_command

app = typer.Typer(
    name="cc-goodies",
    help="Claude Code Goodies - A collection of useful tools for Claude AI",
    add_completion=True,
    no_args_is_help=True,
)

# Add subcommands
app.command(name="progress", help="Track Claude's thinking progress")(progress_command)


@app.callback()
def main(
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


if __name__ == "__main__":
    app()