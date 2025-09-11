"""GitLab client wrapper using python-gitlab library."""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import gitlab
from gitlab.v4.objects import Project, ProjectMergeRequest, ProjectTag, ProjectCommit

from ..config import Config


class GitLabClient:
    """Wrapper for GitLab API using python-gitlab library."""
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """Initialize GitLab client.
        
        Args:
            config: Configuration object containing GitLab settings
            logger: Logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize python-gitlab client
        self.gl = gitlab.Gitlab(
            url=config.gitlab_host,
            private_token=config.gitlab_token,
            timeout=300
        )
        
        # Cache for project instance
        self._project_cache: Dict[str, Project] = {}
    
    def _get_project(self, project_name: str) -> Project:
        """Get project instance with caching."""
        if project_name not in self._project_cache:
            self._project_cache[project_name] = self.gl.projects.get(project_name)
        return self._project_cache[project_name]
    
    def get_merge_request(self, project: str, iid: int) -> Optional[Dict[str, Any]]:
        """Get merge request by IID.
        
        Args:
            project: Project name or ID
            iid: Merge request internal ID
            
        Returns:
            Merge request data as dictionary or None if not found
        """
        try:
            proj = self._get_project(project)
            mr = proj.mergerequests.get(iid)
            
            # Convert to dictionary format similar to Go struct
            return {
                'iid': mr.iid,
                'title': mr.title,
                'description': mr.description or '',
                'web_url': mr.web_url,
                'labels': mr.labels,
                'author': {
                    'username': mr.author.get('username', ''),
                    'name': mr.author.get('name', ''),
                },
                'merged_at': datetime.fromisoformat(mr.merged_at.replace('Z', '+00:00')) if mr.merged_at else None,
                'updated_at': datetime.fromisoformat(mr.updated_at.replace('Z', '+00:00')) if mr.updated_at else None,
                'state': mr.state,
            }
        except Exception as e:
            self.logger.warning(f"Error getting merge request {iid}: {e}")
            return None
    
    def create_merge_request(self, project: str, source_branch: str, target_branch: str,
                           title: str, description: str = "") -> Optional[Dict[str, Any]]:
        """Create a new merge request.
        
        Args:
            project: Project name or ID  
            source_branch: Source branch name
            target_branch: Target branch name
            title: MR title
            description: MR description
            
        Returns:
            Created merge request data or None if failed
        """
        try:
            proj = self._get_project(project)
            mr = proj.mergerequests.create({
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': title,
                'description': description,
            })
            
            return {
                'iid': mr.iid,
                'title': mr.title,
                'description': mr.description or '',
                'web_url': mr.web_url,
                'labels': mr.labels,
                'author': {
                    'username': mr.author.get('username', ''),
                    'name': mr.author.get('name', ''),
                },
                'state': mr.state,
            }
        except Exception as e:
            self.logger.error(f"Error creating merge request: {e}")
            return None
    
    def list_merge_requests(self, project: str, merged_after: Optional[datetime] = None,
                           state: str = "merged") -> List[Dict[str, Any]]:
        """List merge requests with optional filters.
        
        Args:
            project: Project name or ID
            merged_after: Only include MRs merged after this date
            state: MR state filter
            
        Returns:
            List of merge request data
        """
        try:
            proj = self._get_project(project)
            
            # Build filter parameters
            params = {
                'state': state,
                'all': True,  # Get all pages
                'per_page': 100,
            }
            
            if merged_after:
                params['updated_after'] = merged_after.isoformat()
            
            mrs = proj.mergerequests.list(**params)
            
            result = []
            for mr in mrs:
                if merged_after and mr.merged_at:
                    mr_merged_at = datetime.fromisoformat(mr.merged_at.replace('Z', '+00:00'))
                    if mr_merged_at < merged_after:
                        continue
                
                result.append({
                    'iid': mr.iid,
                    'title': mr.title,
                    'description': mr.description or '',
                    'web_url': mr.web_url,
                    'labels': mr.labels,
                    'author': {
                        'username': mr.author.get('username', ''),
                        'name': mr.author.get('name', ''),
                    },
                    'merged_at': datetime.fromisoformat(mr.merged_at.replace('Z', '+00:00')) if mr.merged_at else None,
                    'updated_at': datetime.fromisoformat(mr.updated_at.replace('Z', '+00:00')) if mr.updated_at else None,
                    'state': mr.state,
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error listing merge requests: {e}")
            return []
    
    def get_tag(self, project: str, tag_name: str) -> Optional[Dict[str, Any]]:
        """Get tag by name.
        
        Args:
            project: Project name or ID
            tag_name: Tag name
            
        Returns:
            Tag data or None if not found
        """
        try:
            proj = self._get_project(project)
            tag = proj.tags.get(tag_name)
            
            return {
                'name': tag.name,
                'message': tag.message or '',
                'release': {
                    'description': tag.release['description'] if tag.release else '',
                } if tag.release else None,
                'commit': {
                    'id': tag.commit['id'],
                    'created_at': datetime.fromisoformat(tag.commit['created_at'].replace('Z', '+00:00')),
                },
            }
        except Exception as e:
            self.logger.warning(f"Error getting tag {tag_name}: {e}")
            return None
    
    def list_tags(self, project: str) -> List[Dict[str, Any]]:
        """List all tags for a project.
        
        Args:
            project: Project name or ID
            
        Returns:
            List of tag data
        """
        try:
            proj = self._get_project(project)
            tags = proj.tags.list(all=True, per_page=100)
            
            result = []
            for tag in tags:
                result.append({
                    'name': tag.name,
                    'message': tag.message or '',
                    'release': {
                        'description': tag.release['description'] if tag.release else '',
                    } if tag.release else None,
                    'commit': {
                        'id': tag.commit['id'],
                        'created_at': datetime.fromisoformat(tag.commit['created_at'].replace('Z', '+00:00')),
                    },
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error listing tags: {e}")
            return []
    
    def create_tag(self, project: str, tag_name: str, ref: str, 
                   message: str = "", release_description: str = "") -> bool:
        """Create a new tag.
        
        Args:
            project: Project name or ID
            tag_name: Tag name
            ref: Git reference (branch/commit)
            message: Tag message
            release_description: Release description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            proj = self._get_project(project)
            
            # Create tag
            tag_data = {
                'tag_name': tag_name,
                'ref': ref,
            }
            if message:
                tag_data['message'] = message
            if release_description:
                tag_data['release_description'] = release_description
            
            proj.tags.create(tag_data)
            return True
        except Exception as e:
            self.logger.error(f"Error creating tag {tag_name}: {e}")
            return False
    
    def upsert_release(self, project: str, tag_name: str, description: str) -> bool:
        """Create or update release notes for a tag.
        
        Args:
            project: Project name or ID
            tag_name: Tag name
            description: Release description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            proj = self._get_project(project)
            
            # Check if tag exists and has release
            try:
                tag = proj.tags.get(tag_name)
                if tag.release:
                    # Update existing release - use POST as suggested for size limits
                    proj.http_post(
                        f"/projects/{proj.encoded_id}/repository/tags/{quote(tag_name)}/release",
                        post_data={'description': description},
                        content_type='application/json'
                    )
                else:
                    # Create new release
                    proj.http_post(
                        f"/projects/{proj.encoded_id}/repository/tags/{quote(tag_name)}/release",
                        post_data={'description': description},
                        content_type='application/json'
                    )
            except gitlab.GitlabGetError:
                self.logger.error(f"Tag {tag_name} not found")
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Error upserting release for tag {tag_name}: {e}")
            return False
    
    def get_file(self, project: str, file_path: str, ref: str) -> Optional[str]:
        """Get file content from repository.
        
        Args:
            project: Project name or ID
            file_path: Path to file
            ref: Git reference (branch/commit)
            
        Returns:
            File content as string or None if not found
        """
        try:
            proj = self._get_project(project)
            file_obj = proj.files.get(file_path, ref=ref)
            return file_obj.decode().decode('utf-8')
        except Exception as e:
            self.logger.warning(f"Error getting file {file_path}: {e}")
            return None
    
    def update_file(self, project: str, file_path: str, content: str, 
                    commit_message: str, branch: str) -> bool:
        """Update file in repository.
        
        Args:
            project: Project name or ID
            file_path: Path to file
            content: New file content
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            True if successful, False otherwise
        """
        try:
            proj = self._get_project(project)
            
            # Check if file exists
            try:
                file_obj = proj.files.get(file_path, ref=branch)
                # Update existing file
                file_obj.content = content
                file_obj.save(branch=branch, commit_message=commit_message)
            except gitlab.GitlabGetError:
                # Create new file
                proj.files.create({
                    'file_path': file_path,
                    'content': content,
                    'commit_message': commit_message,
                    'branch': branch,
                })
            
            return True
        except Exception as e:
            self.logger.error(f"Error updating file {file_path}: {e}")
            return False
    
    def create_branch(self, project: str, branch_name: str, ref: str) -> bool:
        """Create a new branch.
        
        Args:
            project: Project name or ID
            branch_name: New branch name
            ref: Source reference
            
        Returns:
            True if successful, False otherwise
        """
        try:
            proj = self._get_project(project)
            proj.branches.create({
                'branch': branch_name,
                'ref': ref,
            })
            return True
        except Exception as e:
            self.logger.error(f"Error creating branch {branch_name}: {e}")
            return False
    
    def list_commits(self, project: str, ref_name: str = "", 
                     since: Optional[datetime] = None,
                     until: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """List commits for a project.
        
        Args:
            project: Project name or ID
            ref_name: Reference name (branch/tag)
            since: Only commits after this date
            until: Only commits before this date
            
        Returns:
            List of commit data
        """
        try:
            proj = self._get_project(project)
            
            params = {
                'all': True,
                'per_page': 100,
            }
            
            if ref_name:
                params['ref_name'] = ref_name
            if since:
                params['since'] = since.isoformat()
            if until:
                params['until'] = until.isoformat()
            
            commits = proj.commits.list(**params)
            
            result = []
            for commit in commits:
                result.append({
                    'id': commit.id,
                    'short_id': commit.short_id,
                    'title': commit.title,
                    'message': commit.message,
                    'created_at': datetime.fromisoformat(commit.created_at.replace('Z', '+00:00')),
                    'author_name': commit.author_name,
                    'author_email': commit.author_email,
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error listing commits: {e}")
            return []
    
    def get_commit(self, project: str, commit_id: str) -> Optional[Dict[str, Any]]:
        """Get commit by ID.
        
        Args:
            project: Project name or ID
            commit_id: Commit ID/hash/tag/branch
            
        Returns:
            Commit data or None if not found
        """
        try:
            proj = self._get_project(project)
            commit = proj.commits.get(commit_id)
            
            return {
                'id': commit.id,
                'short_id': commit.short_id,
                'title': commit.title,
                'message': commit.message,
                'created_at': datetime.fromisoformat(commit.created_at.replace('Z', '+00:00')),
                'author_name': commit.author_name,
                'author_email': commit.author_email,
            }
        except Exception as e:
            self.logger.warning(f"Error getting commit {commit_id}: {e}")
            return None
    
    def get_project(self, project: str) -> Optional[Dict[str, Any]]:
        """Get project information.
        
        Args:
            project: Project name or ID
            
        Returns:
            Project data or None if not found
        """
        try:
            proj = self._get_project(project)
            return {
                'id': proj.id,
                'name': proj.name,
                'path': proj.path,
                'path_with_namespace': proj.path_with_namespace,
                'web_url': proj.web_url,
            }
        except Exception as e:
            self.logger.error(f"Error getting project {project}: {e}")
            return None