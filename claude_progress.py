#!/usr/bin/env python3
"""
claude-progress: A lightweight progress tracker for `claude -p` command.

This tool shows thinking time, turn counts, and content previews while Claude
processes your query. It defaults to the opus model and automatically adds
the necessary flags for progress tracking.

Usage:
    ./claude_progress.py "Your question here"
    ./claude_progress.py --model sonnet "Your question"
    ./claude_progress.py explain quantum computing
"""

import sys
import json
import subprocess
import time
import threading
import signal
import shutil
import os
from typing import Optional, List, Tuple


class ClaudeProgressTracker:
    """Handles progress display for claude -p commands."""
    
    def __init__(self):
        self.spinner_chars = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        self.spinner_index = 0
        self.start_time = time.time()
        self.turn_count = 0
        self.spinner_active = False
        self.spinner_thread: Optional[threading.Thread] = None
        self.last_preview = ""
        self.collected_content = []  # Collect all content pieces
        
        # Find claude binary
        self.claude_path = self._find_claude_binary()
        
    def _find_claude_binary(self) -> str:
        """Find the claude binary, checking common locations."""
        # Check if CLAUDE_PATH env var is set
        if 'CLAUDE_PATH' in os.environ:
            return os.environ['CLAUDE_PATH']
            
        # Try to find claude in PATH
        claude_in_path = shutil.which('claude')
        if claude_in_path:
            return claude_in_path
            
        # Check common locations
        common_paths = [
            '/Users/wei/bin/claude',
            '/usr/local/bin/claude',
            '/opt/homebrew/bin/claude',
            os.path.expanduser('~/bin/claude'),
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
                
        raise FileNotFoundError(
            "Could not find claude binary. "
            "Please ensure claude is in PATH or set CLAUDE_PATH environment variable."
        )
    
    def show_spinner(self):
        """Display animated spinner with elapsed time and turn count."""
        while self.spinner_active:
            elapsed = int(time.time() - self.start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            char = self.spinner_chars[self.spinner_index]
            
            # Build status line
            status = f"\r{char} Claude thinking... [{mins:02d}:{secs:02d}] Turns: {self.turn_count}"
            if self.last_preview:
                status += f" › {self.last_preview}"
            
            # Write to stderr to avoid mixing with stdout
            sys.stderr.write(status)
            sys.stderr.flush()
            
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
            time.sleep(0.1)
    
    def clear_line(self):
        """Clear the current line."""
        sys.stderr.write('\r\033[K')
        sys.stderr.flush()
    
    def start_spinner(self):
        """Start the spinner in a background thread."""
        if not self.spinner_active:
            self.spinner_active = True
            self.spinner_thread = threading.Thread(target=self.show_spinner)
            self.spinner_thread.daemon = True
            self.spinner_thread.start()
    
    def stop_spinner(self):
        """Stop the spinner thread."""
        if self.spinner_active:
            self.spinner_active = False
            if self.spinner_thread:
                self.spinner_thread.join(timeout=0.5)
            self.clear_line()
    
    def format_preview(self, text: str, max_len: int = 70) -> str:
        """Format content preview for display."""
        if not text:
            return ""
        # Remove newlines and extra spaces
        preview = ' '.join(text.split())[:max_len]
        if len(text) > max_len:
            preview += "..."
        return preview
    
    def run(self, args: List[str]) -> int:
        """Run claude command with progress tracking."""
        try:
            # Start claude subprocess
            proc = subprocess.Popen(
                [self.claude_path] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Start progress indicator
            self.start_spinner()
            
            # Process streaming output
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    msg_type = data.get('type', '')
                    
                    if msg_type == 'assistant':
                        self.turn_count += 1
                        # Extract content preview
                        message = data.get('message', {})
                        content_items = message.get('content', [])
                        if content_items and isinstance(content_items, list):
                            text_content = content_items[0].get('text', '')
                            if text_content:
                                self.last_preview = self.format_preview(text_content)
                                self.collected_content.append(text_content)
                    
                    elif msg_type == 'result':
                        # Stop spinner before final output
                        self.stop_spinner()
                        
                        # Extract and print final content
                        content = data.get('content', '')
                        
                        # If no content in result, use collected content
                        if not content and self.collected_content:
                            content = self.collected_content[-1]  # Use last collected content
                        
                        if content:
                            # Ensure content is visible by printing it clearly
                            print("\n" + content)
                            sys.stdout.flush()  # Force flush to ensure output
                        else:
                            # If still no content, show what we collected
                            if self.collected_content:
                                print("\n" + self.collected_content[-1])
                                sys.stdout.flush()
                        
                        # Show summary statistics
                        total_turns = data.get('num_turns', self.turn_count)
                        duration_ms = data.get('duration_ms', 0)
                        
                        if duration_ms > 0:
                            duration_secs = duration_ms / 1000
                            plural = 's' if total_turns != 1 else ''
                            sys.stderr.write(
                                f"\n✓ Done! {total_turns} turn{plural} in {duration_secs:.3f}s\n"
                            )
                        else:
                            sys.stderr.write("\n✓ Done!\n")
                        
                except json.JSONDecodeError:
                    # If not valid JSON, just pass through
                    print(line)
            
            # Wait for process to complete
            return_code = proc.wait()
            
            # Handle any stderr output
            stderr_output = proc.stderr.read()
            if stderr_output:
                sys.stderr.write(stderr_output)
            
            return return_code
            
        except KeyboardInterrupt:
            # Clean shutdown on Ctrl+C
            self.stop_spinner()
            sys.stderr.write("\n⚠️  Interrupted\n")
            return 130  # Standard Unix SIGINT return code
        except Exception as e:
            self.stop_spinner()
            sys.stderr.write(f"\n❌ Error: {e}\n")
            return 1
        finally:
            self.stop_spinner()


def parse_arguments(args: List[str]) -> Tuple[str, List[str]]:
    """
    Parse command line arguments to extract model and build claude args.
    Returns: (model, claude_args)
    """
    model = "opus"  # Default model
    claude_args = []
    text_parts = []
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--model' and i + 1 < len(args):
            # Handle --model flag
            model = args[i + 1]
            i += 2
        elif arg.startswith('--model='):
            # Handle --model=value format
            model = arg.split('=', 1)[1]
            i += 1
        elif arg.startswith('-') or arg.startswith('/'):
            # Other flags - pass through to claude
            claude_args.append(arg)
            i += 1
        else:
            # Regular text - collect for joining
            text_parts.append(arg)
            i += 1
    
    # Build final claude arguments
    final_args = [
        '--dangerously-skip-permissions',
        '--model', model,
        '-p',  # Always use progress flag
        '--output-format', 'stream-json',
        '--verbose'
    ]
    
    # Add any other flags
    final_args.extend(claude_args)
    
    # Join text parts as the query
    if text_parts:
        final_args.append(' '.join(text_parts))
    
    return model, final_args


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: No query provided", file=sys.stderr)
        return 1
    
    # Parse arguments
    model, claude_args = parse_arguments(sys.argv[1:])
    
    # Run with progress tracking
    tracker = ClaudeProgressTracker()
    return tracker.run(claude_args)


if __name__ == '__main__':
    sys.exit(main())