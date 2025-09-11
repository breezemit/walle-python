"""Release note generation logic."""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import is_in_array


# Constants
TITLE_CHANGES = "_Changes:_"
TITLE_BUG_FIX = "**Bug Fix:**"
TITLE_NEW_FEATURE = "_New Features:_"
TITLE_DOCUMENTATION = "Documentation:"
TITLE_OTHER = "Other:"

LABEL_RELEASE_NOTE_NONE = "release-note-none"
DEFAULT_WORKER_COUNT = 4

# Mapping of conventional commit types to release note sections
KINDS = {
    "feat": TITLE_NEW_FEATURE,
    "fix": TITLE_BUG_FIX,
    "refactor": TITLE_CHANGES,
    "docs": TITLE_DOCUMENTATION,
}

DEFAULT_KIND = TITLE_OTHER

SORTED_KINDS = [
    TITLE_BUG_FIX,
    TITLE_NEW_FEATURE,
    TITLE_CHANGES,
    TITLE_DOCUMENTATION,
    TITLE_OTHER,
]

# Regex patterns for filtering out release notes
NOTE_EXCLUSION_FILTERS = [
    # 'none','n/a','na' case insensitive with optional trailing
    # whitespace, wrapped in ``` with/without release-note identifier
    re.compile(r"(?i)```release-note[s]?\s*('|\")?(none|n/a|na)?('|\")?\s*```"),
    
    # simple '/release-note-none' tag
    re.compile(r"/release-note-none"),
]

# Regex for parsing conventional commit format
TAG_MATCHER_RE = re.compile(r'^([^( ]+)\((.*)\)$')


def matches_exclude_filter(msg: str) -> bool:
    """Check if message matches any exclusion filter.
    
    Args:
        msg: Message to check
        
    Returns:
        True if message should be excluded from release notes
    """
    for filter_re in NOTE_EXCLUSION_FILTERS:
        if filter_re.search(msg):
            return True
    return False


def join_notes(items: List[str]) -> str:
    """Group and format release notes by category.
    
    Args:
        items: List of release note items
        
    Returns:
        Formatted release notes string
    """
    releases: Dict[str, List[str]] = {}
    
    for item in items:
        # Split on first colon to separate type from summary
        parts = item.split(':', 1)
        if len(parts) != 2:
            parts = ['', item]
        
        tag, summary = parts[0].strip(), parts[1].strip()
        
        # Parse conventional commit format like "feat(scope): description"
        if '(' in tag:
            match = TAG_MATCHER_RE.match(tag)
            if match:
                tag = match.group(1)
                scope = match.group(2)
                if scope and scope != '*':
                    summary = f"{scope}: {summary}"
        
        # Map tag to release note category
        kind = KINDS.get(tag, DEFAULT_KIND)
        
        # Handle items without recognized conventional commit format
        if tag and ' ' in tag:
            # If tag contains spaces, treat entire item as summary
            summary = item
        
        if kind not in releases:
            releases[kind] = []
        releases[kind].append(summary)
    
    # Format output by category
    sections = []
    for kind in SORTED_KINDS:
        if kind in releases:
            items_list = releases[kind]
            section = f"{kind}\n- {chr(10).join(['- ' + item for item in items_list])}\n"
            sections.append(section)
    
    return '\n'.join(sections)


def generate_release_notes(mrs: List[Dict[str, Any]], 
                          condition: Optional[Callable[[Dict[str, Any]], bool]] = None) -> str:
    """Generate formatted release notes from merge requests.
    
    Args:
        mrs: List of merge request data dictionaries
        condition: Optional filter function for MRs
        
    Returns:
        Formatted release notes string
    """
    if condition is None:
        condition = lambda mr: True
    
    titles = []
    for mr in mrs:
        if not condition(mr):
            continue
        
        title = f"{mr['title']} ([!{mr['iid']}]({mr['web_url']})) @{mr['author']['username']}"
        titles.append(title)
    
    return join_notes(titles)


def get_release_notes_by_tag(client, project: str, tag_name: str, ref: str, since: Optional[str] = None) -> Tuple[bool, str, Optional[Exception]]:
    """Get release notes for a specific tag.
    
    Args:
        client: GitLab client instance
        project: Project name or ID
        tag_name: Tag name to generate release notes for
        ref: Git reference (branch/commit)
        since: Optional starting commit/tag/branch for range (overrides auto-detection)
        
    Returns:
        Tuple of (tag_exists, release_notes, error)
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get all tags
        tags = client.list_tags(project)
        if not tags:
            return False, "", Exception("No tags found in project")
        
        # Determine date range for commits
        tag_exists = False
        since_at = None
        until_at = None
        
        if since:
            # Use external starting position when provided
            logger.info(f"Using external starting position: {since}")
            
            # First check if target tag exists and get its date
            for tag in tags:
                if tag['name'] == tag_name:
                    tag_exists = True
                    until_at = tag['commit']['created_at']
                    break
            
            # Try to get the date for the since reference
            # First try as a tag
            since_found = False
            for tag in tags:
                if tag['name'] == since:
                    since_at = tag['commit']['created_at']
                    since_found = True
                    logger.info(f"Found since tag '{since}' with date: {since_at}")
                    break
            
            # If not found as tag, try to get commit info directly
            if not since_found:
                try:
                    commit_info = client.get_commit(project, since)
                    if commit_info:
                        since_at = commit_info['created_at']
                        logger.info(f"Found since commit '{since}' with date: {since_at}")
                    else:
                        logger.warning(f"Could not find commit/tag/branch '{since}', falling back to auto-detection")
                except Exception as e:
                    logger.warning(f"Error retrieving since reference '{since}': {e}, falling back to auto-detection")
        
        # Fall back to original logic if since is not provided or not found
        if not since_at:
            logger.info("Using auto-detection for starting position")
            for i, tag in enumerate(tags):
                if tag['name'] == tag_name:
                    tag_exists = True
                    until_at = tag['commit']['created_at']
                    continue
                
                # Get the previous tag's date as since_at
                since_at = tag['commit']['created_at']
                break
        
        # Get commits in the range
        commits = client.list_commits(project, ref, since_at, until_at)
        if not commits:
            return tag_exists, "", None
        
        # Skip the first commit if it exists (belongs to previous tag)
        if commits and since_at:
            commits = commits[1:]
        
        # Extract MRs from commits
        mrs = mr_from_commits(commits, client, project)
        
        # Filter MRs for release notes
        def condition(mr):
            # Exclude MRs with release-note-none label or description markers
            exclude = (
                matches_exclude_filter(mr.get('description', '')) or
                is_in_array(LABEL_RELEASE_NOTE_NONE, mr.get('labels', []))
            )
            return not exclude
        
        release_notes = generate_release_notes(mrs, condition)
        return tag_exists, release_notes, None
        
    except Exception as e:
        logger.error(f"Error generating release notes: {e}")
        return False, "", e


def mr_from_commits(commits: List[Dict[str, Any]], client, project: str) -> List[Dict[str, Any]]:
    """Extract merge requests from commit messages using concurrent workers.
    
    Args:
        commits: List of commit data dictionaries
        client: GitLab client instance
        project: Project name or ID
        
    Returns:
        List of merge request data dictionaries
    """
    logger = logging.getLogger(__name__)
    
    if not commits:
        return []
    
    # Extract MR IIDs from commit messages
    mr_iids = []
    for commit in commits:
        iid = mr_num_for_commit_from_message(commit.get('message', ''))
        if iid > 0:
            mr_iids.append(iid)
    
    if not mr_iids:
        return []
    
    # Fetch MRs concurrently
    mrs = []
    max_workers = min(DEFAULT_WORKER_COUNT, len(mr_iids))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_iid = {
            executor.submit(client.get_merge_request, project, iid): iid
            for iid in mr_iids
        }
        
        # Collect results
        for future in as_completed(future_to_iid):
            iid = future_to_iid[future]
            try:
                mr = future.result()
                if mr:
                    mrs.append(mr)
                else:
                    logger.warning(f"Could not fetch MR {iid}")
            except Exception as e:
                logger.warning(f"Error fetching MR {iid}: {e}")
    
    return mrs


def mr_num_for_commit_from_message(commit_message: str) -> int:
    """Extract merge request IID from commit message.
    
    Args:
        commit_message: Git commit message
        
    Returns:
        MR IID or 0 if not found
    """
    # GitLab automatically adds "See merge request ..." to merge commits
    pattern = re.compile(r'\n\nSee merge request .+!(\d+)$')
    match = pattern.search(commit_message)
    
    if not match:
        return 0
    
    try:
        return int(match.group(1))
    except (ValueError, IndexError):
        return 0