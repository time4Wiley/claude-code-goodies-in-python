#!/usr/bin/env python3
"""
Claude .claude.json optimizer
Reduces file size for faster boot times while preserving important data
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import argparse

def analyze_config(config_path):
    """Analyze current config size and content"""
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    file_size = config_path.stat().st_size
    projects = data.get('projects', {})
    
    total_history = sum(len(p.get('history', [])) for p in projects.values())
    pasted_size = sum(
        len(json.dumps(h.get('pastedContents', {})))
        for p in projects.values()
        for h in p.get('history', [])
    )
    
    non_existent = sum(1 for path in projects if not Path(path).exists())
    temp_projects = sum(1 for path in projects 
                       if any(x in path.lower() for x in ['/tmp', 'temp', 'test', 'scratch', 'downloads', '/volumes']))
    
    return {
        'file_size': file_size,
        'total_projects': len(projects),
        'total_history': total_history,
        'pasted_size': pasted_size,
        'non_existent': non_existent,
        'temp_projects': temp_projects,
        'data': data
    }

def clean_config(data, mode='moderate', keep_history=20):
    """Clean config based on mode"""
    projects = data.get('projects', {})
    cleaned_projects = {}
    
    for path, project in projects.items():
        path_obj = Path(path)
        
        # Skip based on mode
        if mode in ['moderate', 'aggressive']:
            # Skip non-existent
            if not path_obj.exists():
                continue
            
            # Skip temp/test/downloads
            if any(x in path.lower() for x in ['/tmp', '/temp/', 'test', 'scratch', '/downloads/', '/volumes/']):
                continue
        
        if mode == 'aggressive':
            # Only keep Projects and App.configs
            if not any(x in path for x in ['/Projects', '/App.configs', '/.config']):
                continue
        
        # Trim history
        if 'history' in project and project['history']:
            project['history'] = project['history'][-keep_history:]
            
            # Clear pastedContents
            for entry in project['history']:
                if 'pastedContents' in entry:
                    # Keep small ones, clear large ones
                    if len(json.dumps(entry['pastedContents'])) > 500:
                        entry['pastedContents'] = {}
        
        cleaned_projects[path] = project
    
    data['projects'] = cleaned_projects
    return data

def main():
    parser = argparse.ArgumentParser(description='Optimize Claude .claude.json for faster boot')
    parser.add_argument('--input', default='.claude.json', help='Input file path')
    parser.add_argument('--output', help='Output file path (default: input.optimized)')
    parser.add_argument('--mode', choices=['light', 'moderate', 'aggressive'], default='moderate',
                       help='Cleanup mode: light (minimal), moderate (recommended), aggressive (maximum)')
    parser.add_argument('--history', type=int, default=20, help='Number of history entries to keep per project')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, don\'t clean')
    parser.add_argument('--no-backup', action='store_true', help='Don\'t create backup')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)
    
    # Analyze current state
    print("Analyzing current .claude.json...")
    analysis = analyze_config(input_path)
    
    print(f"\nCurrent Status:")
    print(f"  File size: {analysis['file_size']:,} bytes ({analysis['file_size']/1024/1024:.2f} MB)")
    print(f"  Total projects: {analysis['total_projects']}")
    print(f"  Total history entries: {analysis['total_history']}")
    print(f"  pastedContents size: {analysis['pasted_size']:,} bytes ({analysis['pasted_size']/1024/1024:.2f} MB)")
    print(f"  Non-existent projects: {analysis['non_existent']}")
    print(f"  Temp/test projects: {analysis['temp_projects']}")
    
    if args.analyze_only:
        return
    
    # Create backup
    if not args.no_backup:
        backup_path = input_path.with_suffix(f'.backup.{datetime.now():%Y%m%d_%H%M%S}.json')
        print(f"\nCreating backup: {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(analysis['data'], f, indent=2)
    
    # Clean based on mode
    history_keep = {
        'light': 50,
        'moderate': args.history,
        'aggressive': 10
    }[args.mode]
    
    print(f"\nCleaning with mode: {args.mode} (keeping {history_keep} history entries)...")
    cleaned_data = clean_config(analysis['data'], mode=args.mode, keep_history=history_keep)
    
    # Determine output path
    output_path = Path(args.output) if args.output else input_path.with_suffix('.optimized.json')
    
    # Save cleaned version
    with open(output_path, 'w') as f:
        json.dump(cleaned_data, f, separators=(',', ':'))  # Compact format
    
    # Report results
    new_size = output_path.stat().st_size
    new_projects = len(cleaned_data.get('projects', {}))
    reduction = (1 - new_size/analysis['file_size']) * 100
    
    print(f"\nOptimization Complete:")
    print(f"  Output: {output_path}")
    print(f"  New size: {new_size:,} bytes ({new_size/1024/1024:.2f} MB)")
    print(f"  Projects kept: {new_projects}/{analysis['total_projects']}")
    print(f"  Size reduction: {reduction:.1f}%")
    print(f"  Estimated boot speed improvement: {min(reduction * 2, 95):.0f}%")
    
    if output_path != input_path:
        print(f"\nTo use the optimized config:")
        print(f"  cp {output_path} {input_path}")

if __name__ == '__main__':
    main()