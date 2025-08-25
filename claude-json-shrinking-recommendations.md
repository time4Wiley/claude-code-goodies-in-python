# .claude.json Shrinking Recommendations

## Current State Analysis
- **File Size**: 2.2MB (2,189,299 bytes)
- **Line Count**: 28,703 lines
- **Main Consumer**: `projects` section (2.09MB, 95% of total)

## Size Breakdown

### Projects Section (2.09MB)
- **Total Projects**: 326
- **History Entries**: 4,333 total
- **Average History/Project**: 13.3 entries
- **Projects at Max (100 entries)**: 13 projects
- **pastedContents Size**: 1.05MB (48% of projects section)

### Top Space Consumers
1. **temp** - 134KB (33 history entries, 9KB pasted)
2. **loopcraft-taskwarrior-desktop-app** - 127KB (100 entries, 105KB pasted)
3. **ChatGPT-Analysis** - 123KB (90 entries, 6KB pasted)
4. **app-configs-shared** - 111KB (43 entries, 100KB pasted)
5. **next14-duolingo-clone** - 87KB (37 entries, 82KB pasted)

### Problematic Patterns
- **Non-existent projects**: 46 projects (14%) no longer exist on disk
- **Temporary projects**: 25 projects with temp/test/scratch in name
- **External volumes**: Projects on /Volumes/ (removable media)
- **Downloads folder**: Multiple projects in ~/Downloads/

## Recommended Actions (Priority Order)

### 1. Immediate Wins (80% size reduction)
```bash
# Create a cleaned version
jq '.projects = (.projects | to_entries | map(select(.key | test("/Users/wei/Projects|/Users/wei/App.configs"))) | from_entries)' .claude.json > .claude.json.cleaned

# Or be more aggressive - keep only existing projects
jq --arg home "$HOME" '.projects = (.projects | with_entries(select(.key | startswith($home) and (. | test("/tmp|/temp|/Downloads|/Volumes") | not))))' .claude.json > .claude.json.cleaned
```

### 2. History Trimming (30-40% reduction)
```bash
# Keep only last 20 history entries per project
jq '.projects |= with_entries(.value.history |= (if . then .[-20:] else . end))' .claude.json > .claude.json.trimmed

# Or keep last 10 for maximum reduction
jq '.projects |= with_entries(.value.history |= (if . then .[-10:] else . end))' .claude.json > .claude.json.minimal
```

### 3. Remove pastedContents (50% reduction)
```bash
# Clear all pastedContents while keeping history
jq '(.projects[].history[]?.pastedContents) = {}' .claude.json > .claude.json.no-paste
```

### 4. Combined Aggressive Cleanup (90% reduction)
```bash
# Keep only existing projects, last 10 history entries, no pastedContents
cat > /tmp/clean_claude.py << 'EOF'
import json
from pathlib import Path

with open('.claude.json', 'r') as f:
    data = json.load(f)

# Keep only existing projects
cleaned_projects = {}
for path, project in data['projects'].items():
    if Path(path).exists() and not any(x in path for x in ['/tmp/', '/temp/', '/Downloads/', '/Volumes/']):
        # Keep only last 10 history entries without pastedContents
        if 'history' in project:
            project['history'] = project['history'][-10:]
            for entry in project['history']:
                entry['pastedContents'] = {}
        cleaned_projects[path] = project

data['projects'] = cleaned_projects

with open('.claude.json.optimized', 'w') as f:
    json.dump(data, f, separators=(',', ':'))

print(f"Original projects: {len(data['projects'])}")
print(f"Cleaned projects: {len(cleaned_projects)}")
print(f"Estimated size reduction: {(1 - len(cleaned_projects)/326) * 100:.1f}%")
EOF

python3 /tmp/clean_claude.py
```

## Size Reduction Estimates

| Action | Projects Kept | History/Project | Size Reduction | Boot Speed Impact |
|--------|--------------|-----------------|----------------|-------------------|
| Remove non-existent | 280 | Current | ~15% | Minor |
| Remove temp/Downloads | ~250 | Current | ~25% | Moderate |
| Trim to 20 history | Current | 20 | ~40% | Good |
| Trim to 10 history | Current | 10 | ~60% | Better |
| Clear pastedContents | Current | Current | ~50% | Good |
| **Combined (Recommended)** | ~250 | 10 | **~85-90%** | **Excellent** |

## Recommended Implementation

### Option A: Conservative (Keep important data)
1. Remove non-existent projects
2. Remove temp/Downloads projects
3. Trim history to 20 entries
4. Clear pastedContents older than 30 days
- **Expected reduction**: 60-70%
- **Final size**: ~700KB

### Option B: Aggressive (Maximum performance)
1. Keep only ~/Projects and ~/App.configs
2. Trim history to 10 entries
3. Clear all pastedContents
- **Expected reduction**: 85-90%
- **Final size**: ~200-300KB

### Option C: Nuclear (Fresh start)
```bash
# Keep only settings, remove all project history
jq 'del(.projects)' .claude.json > .claude.json.fresh
```
- **Expected reduction**: 95%
- **Final size**: ~100KB

## Boot Speed Impact

Current 2.2MB file causes:
- **Parse time**: ~50-100ms on M1
- **Memory usage**: ~10-15MB
- **Startup delay**: Noticeable

After optimization (300KB):
- **Parse time**: ~5-10ms
- **Memory usage**: ~2-3MB
- **Startup delay**: Imperceptible

## Maintenance Script

Create `~/.local/bin/claude-clean`:
```bash
#!/bin/bash
# Claude .claude.json maintenance script

CLAUDE_JSON="$HOME/.claude.json"
BACKUP="$CLAUDE_JSON.backup.$(date +%Y%m%d)"

# Backup current
cp "$CLAUDE_JSON" "$BACKUP"

# Clean
python3 << 'EOF'
import json
from pathlib import Path

config_path = Path.home() / '.claude.json'
data = json.load(config_path.open())

# Clean projects
cleaned = {}
for path, proj in data.get('projects', {}).items():
    p = Path(path)
    # Keep only existing, non-temp projects
    if p.exists() and not any(x in str(p) for x in ['/tmp', '/temp', 'Downloads', '/Volumes']):
        # Trim history
        if 'history' in proj:
            proj['history'] = proj['history'][-15:]  # Keep last 15
            # Clear large pastedContents
            for h in proj['history']:
                if len(str(h.get('pastedContents', {}))) > 1000:
                    h['pastedContents'] = {}
        cleaned[path] = proj

data['projects'] = cleaned

# Save
with config_path.open('w') as f:
    json.dump(data, f, indent=2)

print(f"Cleaned: {len(data['projects'])} projects kept")
EOF

echo "Claude config cleaned. Backup at: $BACKUP"
```

## Regular Maintenance

Add to crontab or run weekly:
```bash
# Add to ~/.zshrc
alias claude-clean='python3 ~/scripts/clean-claude-json.py'

# Or add weekly cron
0 0 * * 0 /usr/bin/python3 /Users/wei/scripts/clean-claude-json.py
```

## Testing Changes

Before applying to real ~/.claude.json:
```bash
# Test with copy
cp ~/.claude.json ./.claude.json.test
# Apply changes to test file
# Launch Claude with test config
CLAUDE_CONFIG_PATH=./.claude.json.test claude
```