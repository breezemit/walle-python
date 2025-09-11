"""Main CLI entry point for Walle."""

import logging
import sys
from datetime import datetime

import click

from ..config import get_config, create_sample_config, Config
from ..gitlab import GitLabClient
from .release import release
from .changelog import changelog
from .batch import batch


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--gitlab-host', help='GitLab host URL (can also be set per command)')
@click.option('--gitlab-token', help='GitLab API token (can also be set per command)')
@click.option('--config-file', '-c', help='Path to JSON configuration file')
@click.version_option(version="1.0.0", prog_name="walle")
@click.pass_context
def cli(ctx, debug, gitlab_host, gitlab_token, config_file):
    """Walle - GitLab-based release automation tool."""
    
    # Setup logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load base config
    base_config = get_config(config_file)
    
    # Store global options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['base_config'] = base_config
    ctx.obj['global_gitlab_host'] = gitlab_host
    ctx.obj['global_gitlab_token'] = gitlab_token
    ctx.obj['logger'] = logging.getLogger('walle')


def create_client_for_project(ctx, project, gitlab_host=None, gitlab_token=None):
    """Create GitLab client for a specific project with configuration precedence."""
    base_config = ctx.obj['base_config']
    logger = ctx.obj['logger']
    
    # Create a copy of base config
    config = Config(
        gitlab_host=gitlab_host or ctx.obj['global_gitlab_host'] or base_config.gitlab_host,
        gitlab_token=gitlab_token or ctx.obj['global_gitlab_token'] or base_config.gitlab_token,
        project=project or base_config.project
    )
    
    # Validate required settings
    if not config.gitlab_token:
        click.echo("Error: GitLab token is required. Set WALLE_GITLAB_TOKEN, use --gitlab-token, or config file", err=True)
        sys.exit(1)
    
    if not config.project:
        click.echo("Error: Project is required. Use --project or config file", err=True)
        sys.exit(1)
    
    return GitLabClient(config, logger), config


@cli.command()
@click.option('--path', '-p', default='walle.json', help='Path for the config file')
def init_config(path):
    """Create a sample configuration file."""
    try:
        create_sample_config(path)
    except Exception as e:
        click.echo(f"Error creating config file: {e}", err=True)


@cli.command()
@click.pass_context
def version(ctx):
    """Show version information."""
    build_date = datetime.now().strftime('%Y-%m-%d')
    click.echo(f"Walle version 1.0.0 (built {build_date})")


# Add subcommands
cli.add_command(release)
cli.add_command(changelog)
cli.add_command(batch)


def main():
    """Main entry point for console script."""
    cli()


if __name__ == '__main__':
    main()