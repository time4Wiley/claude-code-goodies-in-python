#!/bin/zsh

# Auto-commit function for cc-goodies progress changes
cgc() {
    local query="${1:-/init}"
    local output
    
    # Run cc-goodies progress and capture output
    output=$(cc-goodies progress "$query" 2>/dev/null)
    
    # Check if there are changes to commit
    if [[ -n $(git status --porcelain) ]]; then
        git add -A
        git commit -m "AI: $query

Output:
$output

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
        echo "✅ Changes committed"
    else
        echo "No changes to commit"
    fi
}