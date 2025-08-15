"""Claude progress tracking command."""

import typer
from typing import List, Optional
import sys

from ..core.progress_tracker import ClaudeProgressTracker, parse_arguments


def progress_command(
    query: List[str] = typer.Argument(
        ..., 
        help="Your query to Claude (no quotes needed)"
    ),
    model: Optional[str] = typer.Option(
        "opus",
        "--model", "-m",
        help="Claude model to use (e.g., opus, sonnet, haiku, claude-3-5-haiku-20241022)"
    ),
):
    """
    Track Claude's thinking progress with real-time updates.
    
    Shows:
    - Animated progress spinner
    - Elapsed time tracking  
    - Turn counter
    - Content preview during thinking
    - Clean final output
    - Completion statistics
    
    Examples:
        cc-goodies progress What is quantum computing?
        
        cc-goodies progress --model sonnet Explain git rebase
        
        cc-goodies progress tell me about machine learning
    """
    if not query:
        typer.echo("Error: No query provided", err=True)
        raise typer.Exit(1)
    
    # Combine all query parts
    full_query = ' '.join(query)
    
    # Build args list for the tracker
    args = []
    if model != "opus":
        args.extend(["--model", model])
    args.append(full_query)
    
    # Parse arguments and run
    _, claude_args = parse_arguments(args)
    
    # Run with progress tracking
    tracker = ClaudeProgressTracker()
    return_code = tracker.run(claude_args)
    
    raise typer.Exit(return_code)