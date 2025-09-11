"""Release command implementation."""

import click
from ..releasenote import get_release_notes_by_tag


@click.command()
@click.option('--project', '-p', required=True, help='GitLab project path or ID')
@click.option('--ref', '-r', required=True, help='Git reference (branch/tag)')
@click.option('--tag', '-t', required=True, help='Release tag name')
@click.option('--since', '-s', help='Starting commit/tag/branch for changelog range (overrides auto-detection)')
@click.option('--gitlab-host', help='GitLab host URL (overrides global setting)')
@click.option('--gitlab-token', help='GitLab API token (overrides global setting)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@click.option('--markdown-only', '-mo', is_flag=True, help='Generate only markdown, do not create tags or releases')
@click.option('--tag-only', '-to', is_flag=True, help='Create only tags, do not create releases')
@click.option('--output', '-o', help='Output markdown to file instead of stdout')
@click.pass_context
def release(ctx, project, ref, tag, since, gitlab_host, gitlab_token, dry_run, markdown_only, tag_only, output):
    """Create release with automated release notes."""
    
    # Import here to avoid circular dependency
    from .main import create_client_for_project
    
    # Validate mutually exclusive options
    if markdown_only and tag_only:
        click.echo("Error: --markdown-only and --tag-only cannot be used together", err=True)
        return 1
    
    client, config = create_client_for_project(ctx, project, gitlab_host, gitlab_token)
    logger = ctx.obj['logger']
    
    logger.info(f"Creating release for project: {project}, tag: {tag}, ref: {ref}")
    
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
            if not tag_only:  # Still allow tag creation even with no release notes
                return 0
        
        # Handle markdown-only output
        if markdown_only:
            if output:
                try:
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(f"# Release {tag}\n\n{release_notes}")
                    click.echo(f"Release notes saved to: {output}")
                except Exception as e:
                    click.echo(f"Error writing to file {output}: {e}", err=True)
                    return 1
            else:
                click.echo(f"# Release {tag}\n")
                click.echo(release_notes)
            return 0
        
        # Display release notes
        click.echo(f"Generated release notes for {tag}:")
        click.echo("=" * 50)
        click.echo(release_notes)
        click.echo("=" * 50)
        
        if dry_run:
            click.echo("(Dry run - no changes made)")
            return 0
        
        # Create tag if it doesn't exist
        if not tag_exists:
            logger.info(f"Creating tag: {tag}")
            success = client.create_tag(project, tag, ref, f"Release {tag}")
            if not success:
                click.echo(f"Error creating tag: {tag}", err=True)
                return 1
            click.echo(f"Successfully created tag: {tag}")
        
        # Handle tag-only mode
        if tag_only:
            click.echo(f"Tag-only mode: Only tag '{tag}' was created, no release notes uploaded")
            return 0
        
        # Create/update release (only if not tag-only and has release notes)
        if release_notes.strip():
            logger.info(f"Upserting release for tag: {tag}")
            success = client.upsert_release(project, tag, release_notes)
            if not success:
                click.echo(f"Error creating release for tag: {tag}", err=True)
                return 1
            click.echo(f"Successfully created release for tag: {tag}")
        else:
            click.echo(f"No release notes to upload for tag: {tag}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        click.echo(f"Error: {e}", err=True)
        return 1