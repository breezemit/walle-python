"""Batch processing command implementation."""

import click
import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..releasenote import get_release_notes_by_tag


def parse_release_notes(release_notes: str, project_name: str):
    """Parse release notes and categorize them by type.
    
    Args:
        release_notes: Raw release notes markdown
        project_name: Name of the project
        
    Returns:
        Dictionary with categorized release notes
    """
    categories = {
        '**Bug Fix:**': 'bug_fixes',
        '_New Features:_': 'new_features', 
        '_Changes:_': 'changes',
        'Documentation:': 'documentation',
        'Other:': 'other'
    }
    
    result = defaultdict(list)
    current_category = None
    
    for line in release_notes.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check if line is a category header
        found_category = None
        for category_header, category_key in categories.items():
            if line.startswith(category_header):
                found_category = category_key
                current_category = category_key
                break
        
        if found_category:
            continue
        
        # If it's a list item and we have a current category
        if line.startswith('-') and current_category:
            # Add project prefix to the item
            item = line[1:].strip()  # Remove the '-' and leading spaces
            result[current_category].append(f"**{project_name}**: {item}")
    
    return result


def merge_categorized_notes(all_project_notes, product_name=None):
    """Merge categorized notes from multiple projects.
    
    Args:
        all_project_notes: List of (project_name, categorized_notes) tuples
        product_name: Name of the product (optional)
        
    Returns:
        Merged markdown string
    """
    merged = defaultdict(list)
    
    # Merge all categories from all projects
    for project_name, notes in all_project_notes:
        for category, items in notes.items():
            merged[category].extend(items)
    
    # Generate markdown
    category_headers = {
        'bug_fixes': '**Bug Fixes:**',
        'new_features': '_New Features:_',
        'changes': '_Changes:_', 
        'documentation': 'Documentation:',
        'other': 'Other:'
    }
    
    category_order = ['bug_fixes', 'new_features', 'changes', 'documentation', 'other']
    
    sections = []
    if product_name:
        sections.append(f"# {product_name} Release Notes\n")
    
    for category in category_order:
        if category in merged and merged[category]:
            sections.append(f"{category_headers[category]}")
            for item in merged[category]:
                sections.append(f"- {item}")
            sections.append("")  # Empty line after each category
    
    return '\n'.join(sections)


@click.command()
@click.option('--config', '-c', required=True, help='JSON config file with projects and tags')
@click.option('--gitlab-host', help='GitLab host URL (overrides global setting)')
@click.option('--gitlab-token', help='GitLab API token (overrides global setting)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--markdown-only', '-mo', is_flag=True, help='Generate only markdown, do not create tags or releases')
@click.option('--tag-only', '-to', is_flag=True, help='Create only tags, do not create releases')
@click.option('--output-dir', '-o', help='Output directory for markdown files (when using --markdown-only)')
@click.option('--merge-markdown', '-mm', is_flag=True, help='Merge all projects into a single product-level markdown')
@click.option('--product-name', help='Product name for merged markdown (default: auto-generated)')
@click.option('--workers', default=4, help='Number of concurrent workers')
@click.pass_context
def batch(ctx, config, gitlab_host, gitlab_token, dry_run, markdown_only, tag_only, output_dir, merge_markdown, product_name, workers):
    """Process multiple projects in batch mode.
    
    Config file format:
    {
        "product_name": "My Product",
        "projects": [
            {
                "project": "group/project1",
                "ref": "master",
                "tag": "v1.0.0"
            },
            {
                "project": "group/project2", 
                "ref": "main",
                "tag": "v2.0.0",
                "gitlab_host": "https://custom.gitlab.com",
                "gitlab_token": "custom-token"
            }
        ]
    }
    """
    
    # Import here to avoid circular dependency
    from .main import create_client_for_project
    
    logger = ctx.obj['logger']
    
    # Validate mutually exclusive options
    if markdown_only and tag_only:
        click.echo("Error: --markdown-only and --tag-only cannot be used together", err=True)
        return 1
    
    # Load batch configuration
    try:
        with open(config, 'r', encoding='utf-8') as f:
            batch_config = json.load(f)
    except Exception as e:
        click.echo(f"Error loading batch config {config}: {e}", err=True)
        return 1
    
    projects = batch_config.get('projects', [])
    if not projects:
        click.echo("No projects found in batch config", err=True)
        return 1
    
    # Get product name from config or parameter
    if not product_name:
        product_name = batch_config.get('product_name', f"Release-{projects[0].get('tag', 'Unknown')}")
    
    click.echo(f"Processing {len(projects)} projects with {workers} workers")
    
    def process_project(project_config):
        """Process a single project."""
        try:
            project = project_config['project']
            ref = project_config['ref']
            tag = project_config['tag']
            since = project_config.get('since')  # Optional starting position
            
            # Override settings per project
            project_gitlab_host = project_config.get('gitlab_host', gitlab_host)
            project_gitlab_token = project_config.get('gitlab_token', gitlab_token)
            
            client, config = create_client_for_project(
                ctx, project, project_gitlab_host, project_gitlab_token
            )
            
            logger.info(f"Processing project: {project}, tag: {tag}")
            
            # Get release notes
            tag_exists, release_notes, error = get_release_notes_by_tag(
                client, project, tag, ref, since
            )
            
            if error:
                return {'project': project, 'status': 'error', 'message': str(error)}
            
            if not release_notes.strip():
                return {'project': project, 'status': 'empty', 'message': 'No release notes generated'}
            
            # Parse release notes for merging
            project_display_name = project.split('/')[-1]  # Use project name without group
            categorized_notes = parse_release_notes(release_notes, project_display_name)
            
            # Handle markdown-only mode
            if markdown_only or merge_markdown:
                return {
                    'project': project,
                    'status': 'success',
                    'message': 'Release notes generated',
                    'markdown': release_notes,
                    'categorized': categorized_notes,
                    'project_name': project_display_name
                }
            
            if dry_run:
                return {
                    'project': project,
                    'status': 'dry-run',
                    'message': f'Would create/update {"tag" if tag_only else "release"} for tag {tag}',
                    'markdown': release_notes,
                    'categorized': categorized_notes,
                    'project_name': project_display_name
                }
            
            # Create tag if it doesn't exist
            if not tag_exists:
                success = client.create_tag(project, tag, ref, f"Release {tag}")
                if not success:
                    return {'project': project, 'status': 'error', 'message': f'Failed to create tag {tag}'}
            
            # Handle tag-only mode
            if tag_only:
                return {
                    'project': project,
                    'status': 'success',
                    'message': f'Successfully created tag {tag}',
                    'categorized': categorized_notes,
                    'project_name': project_display_name
                }
            
            # Create/update release
            success = client.upsert_release(project, tag, release_notes)
            if not success:
                return {'project': project, 'status': 'error', 'message': f'Failed to create release for tag {tag}'}
            
            return {
                'project': project,
                'status': 'success', 
                'message': f'Successfully created release for tag {tag}',
                'categorized': categorized_notes,
                'project_name': project_display_name
            }
            
        except Exception as e:
            return {'project': project_config.get('project', 'unknown'), 'status': 'error', 'message': str(e)}
    
    # Process projects concurrently
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_project = {
            executor.submit(process_project, project_config): project_config
            for project_config in projects
        }
        
        for future in as_completed(future_to_project):
            result = future.result()
            results.append(result)
            
            # Display progress
            status = result['status']
            project = result['project']
            
            if status == 'success':
                click.echo(f"✓ {project}: {result['message']}")
            elif status == 'error':
                click.echo(f"✗ {project}: {result['message']}", err=True)
            elif status == 'empty':
                click.echo(f"- {project}: {result['message']}")
            elif status == 'dry-run':
                click.echo(f"? {project}: {result['message']}")
    
    # Handle markdown output
    successful_results = [r for r in results if r['status'] in ['success', 'dry-run'] and 'categorized' in r]
    
    if merge_markdown and successful_results:
        # Generate merged markdown
        project_notes = [(r['project_name'], r['categorized']) for r in successful_results]
        merged_markdown = merge_categorized_notes(project_notes, product_name)
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{product_name.replace(' ', '_')}_Release_Notes.md")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(merged_markdown)
            
            click.echo(f"\nMerged release notes saved to: {output_file}")
        else:
            click.echo(f"\n{merged_markdown}")
    
    elif (markdown_only or dry_run) and output_dir and not merge_markdown:
        # Save individual markdown files
        os.makedirs(output_dir, exist_ok=True)
        
        for result in successful_results:
            if 'markdown' in result:
                safe_project = result['project'].replace('/', '_')
                tag = projects[results.index(result)].get('tag', 'unknown')
                output_file = os.path.join(output_dir, f"{safe_project}_{tag}.md")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Release {tag}\n\n{result['markdown']}")
        
        click.echo(f"\nIndividual release notes saved to: {output_dir}")
    
    elif (markdown_only or dry_run) and not output_dir and not merge_markdown:
        # Display individual markdown to console
        for result in successful_results:
            if 'markdown' in result:
                tag = projects[results.index(result)].get('tag', 'unknown')
                click.echo(f"\n--- {result['project']} {tag} ---")
                click.echo(result['markdown'])
                click.echo("--- End ---\n")
    
    # Summary
    success_count = sum(1 for r in results if r['status'] in ['success', 'dry-run'])
    error_count = sum(1 for r in results if r['status'] == 'error')
    empty_count = sum(1 for r in results if r['status'] == 'empty')
    
    click.echo(f"\nSummary: {success_count} succeeded, {error_count} failed, {empty_count} empty")
    
    return 0 if error_count == 0 else 1