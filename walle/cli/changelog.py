"""Changelog command implementation."""

import click
from ..releasenote import get_release_notes_by_tag


@click.command()
@click.option('--project', '-p', required=True, help='GitLab project path or ID')
@click.option('--ref', '-r', required=True, help='Git reference (branch/tag)')
@click.option('--tag', '-t', required=True, help='Release tag name')
@click.option('--since', '-s', help='Starting commit/tag/branch for changelog range (overrides auto-detection)')
@click.option('--file', '-f', default='CHANGELOG.md', help='Changelog file path')
@click.option('--gitlab-host', help='GitLab host URL (overrides global setting)')
@click.option('--gitlab-token', help='GitLab API token (overrides global setting)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--markdown-only', '-mo', is_flag=True, help='Generate only markdown, do not update changelog or create MR')
@click.option('--output', '-o', help='Output markdown to file instead of stdout (when using --markdown-only)')
@click.pass_context
def changelog(ctx, project, ref, tag, since, file, gitlab_host, gitlab_token, dry_run, markdown_only, output):
    """Update changelog with release notes."""
    
    # Import here to avoid circular dependency
    from .main import create_client_for_project
    
    client, config = create_client_for_project(ctx, project, gitlab_host, gitlab_token)
    logger = ctx.obj['logger']
    
    logger.info(f"Updating changelog for project: {project}, tag: {tag}, ref: {ref}")
    
    try:
        # Get release notes
        tag_exists, release_notes, error = get_release_notes_by_tag(
            client, project, tag, ref, since
        )
        
        if error:
            click.echo(f"Error generating release notes: {error}", err=True)
            return 1
        
        if not release_notes.strip():
            click.echo("No release notes generated (no merge requests found or all excluded)")
            return 0
        
        # Prepare changelog entry
        changelog_entry = f"## {tag}\n\n{release_notes}\n\n"
        
        # Handle markdown-only mode
        if markdown_only:
            if output:
                try:
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(changelog_entry)
                    click.echo(f"Changelog entry saved to: {output}")
                except Exception as e:
                    click.echo(f"Error writing to file {output}: {e}", err=True)
                    return 1
            else:
                click.echo(changelog_entry)
            return 0
        
        # Get current changelog content
        current_content = client.get_file(project, file, ref) or ""
        
        # Insert at the top of the file (after any title)
        lines = current_content.split('\n')
        if lines and lines[0].startswith('#'):
            # Keep the title, insert after it
            new_content = lines[0] + '\n\n' + changelog_entry + '\n'.join(lines[1:])
        else:
            # Insert at the very beginning
            new_content = changelog_entry + current_content
        
        click.echo(f"Changelog entry for {tag}:")
        click.echo("=" * 50)
        click.echo(changelog_entry)
        click.echo("=" * 50)
        
        if dry_run:
            click.echo("(Dry run - no changes made)")
            return 0
        
        # Create a new branch for the changelog update
        branch_name = f"changelog-{tag}"
        logger.info(f"Creating branch: {branch_name}")
        
        success = client.create_branch(project, branch_name, ref)
        if not success:
            click.echo(f"Error creating branch: {branch_name}", err=True)
            return 1
        
        # Update the changelog file
        logger.info(f"Updating {file}")
        success = client.update_file(
            project, 
            file, 
            new_content, 
            f"Update {file} for {tag}",
            branch_name
        )
        if not success:
            click.echo(f"Error updating {file}", err=True)
            return 1
        
        # Create merge request
        logger.info("Creating merge request for changelog update")
        mr_data = client.create_merge_request(
            project,
            branch_name,
            ref,
            f"Update {file} for {tag}",
            f"Automated changelog update for release {tag}"
        )
        
        if mr_data:
            click.echo(f"Successfully created merge request: {mr_data['web_url']}")
        else:
            click.echo(f"Error creating merge request, but changelog was updated in branch: {branch_name}", err=True)
            return 1
        
        click.echo(f"Successfully updated changelog for tag: {tag}")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        click.echo(f"Error: {e}", err=True)
        return 1