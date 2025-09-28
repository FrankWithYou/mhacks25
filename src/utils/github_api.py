"""
GitHub API integration for the marketplace.
Handles creating issues and verification endpoints.
"""

import httpx
from typing import Dict, Any, Optional, Tuple
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors"""
    pass


class GitHubAPI:
    """GitHub API client for creating and verifying issues"""
    
    def __init__(self, token: str, repo: str):
        """
        Initialize GitHub API client
        
        Args:
            token: GitHub personal access token
            repo: Repository in format "owner/repo"
        """
        self.token = token
        self.repo = repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "trust-minimized-marketplace/1.0"
        }
    
    async def create_issue(self, title: str, body: str = "", labels: Optional[list] = None) -> Tuple[str, str]:
        """
        Create a GitHub issue
        
        Args:
            title: Issue title
            body: Issue body/description
            labels: List of label names
            
        Returns:
            Tuple of (issue_url, issue_api_url) for verification
            
        Raises:
            GitHubAPIError: If issue creation fails
        """
        url = f"{self.base_url}/repos/{self.repo}/issues"
        
        payload = {
            "title": title,
            "body": body or f"Created by marketplace agent at {datetime.utcnow().isoformat()}"
        }
        
        if labels:
            payload["labels"] = labels
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers)
                
                if response.status_code == 201:
                    issue_data = response.json()
                    issue_url = issue_data["html_url"]
                    api_url = issue_data["url"]
                    
                    logger.info(f"Created GitHub issue: {issue_url}")
                    return issue_url, api_url
                else:
                    error_msg = f"Failed to create issue. Status: {response.status_code}, Response: {response.text}"
                    logger.error(error_msg)
                    raise GitHubAPIError(error_msg)
                    
        except httpx.RequestError as e:
            error_msg = f"HTTP request error: {str(e)}"
            logger.error(error_msg)
            raise GitHubAPIError(error_msg)
    
    async def verify_issue(self, issue_url: str, expected_title: str, expected_creator: str = None) -> Dict[str, Any]:
        """
        Verify that an issue exists and matches expected parameters
        
        Args:
            issue_url: GitHub issue URL (either html_url or api_url)
            expected_title: Expected issue title
            expected_creator: Expected creator username (optional)
            
        Returns:
            Dict with verification result and details
        """
        try:
            logger.info(f"Original issue_url: {issue_url}")
            # Check if it's already an API URL first
            if "api.github.com/repos/" in issue_url:
                # It's already an API URL, use as-is
                api_url = issue_url
                logger.info(f"Using API URL as-is: {api_url}")
            elif "github.com" in issue_url and "/issues/" in issue_url and "api.github.com" not in issue_url:
                # Convert HTML URL to API URL
                parts = issue_url.replace("https://github.com/", "").split("/")
                logger.info(f"URL parts: {parts}")
                if len(parts) >= 4:
                    owner, repo, _, issue_num = parts[:4]
                    api_url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_num}"
                    logger.info(f"Converted to API URL: {api_url}")
                else:
                    return {"verified": False, "details": "Invalid issue URL format"}
            else:
                logger.error(f"Invalid URL format: {issue_url}")
                return {"verified": False, "details": "Invalid issue URL format"}
            
            async with httpx.AsyncClient() as client:
                logger.info(f"Making verification request to: {api_url}")
                logger.info(f"Headers: {self.headers}")
                response = await client.get(api_url, headers=self.headers)
                logger.info(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    issue_data = response.json()
                    
                    # Check title
                    actual_title = issue_data.get("title", "")
                    title_match = actual_title == expected_title
                    
                    # Check creator if specified
                    creator_match = True
                    if expected_creator:
                        actual_creator = issue_data.get("user", {}).get("login", "")
                        creator_match = actual_creator == expected_creator
                    
                    # Check if issue is in the expected repo
                    repo_url = issue_data.get("repository_url", "")
                    expected_repo_url = f"{self.base_url}/repos/{self.repo}"
                    repo_match = repo_url == expected_repo_url
                    
                    verified = title_match and creator_match and repo_match
                    
                    details = {
                        "title_match": title_match,
                        "expected_title": expected_title,
                        "actual_title": actual_title,
                        "creator_match": creator_match,
                        "repo_match": repo_match,
                        "issue_number": issue_data.get("number"),
                        "issue_state": issue_data.get("state"),
                        "created_at": issue_data.get("created_at"),
                        "html_url": issue_data.get("html_url")
                    }
                    
                    if expected_creator:
                        details["expected_creator"] = expected_creator
                        details["actual_creator"] = issue_data.get("user", {}).get("login", "")
                    
                    return {
                        "verified": verified,
                        "details": f"Issue verification {'passed' if verified else 'failed'}: {details}",
                        "raw_details": details
                    }
                    
                elif response.status_code == 404:
                    return {
                        "verified": False,
                        "details": "Issue not found (404)",
                        "raw_details": {"status_code": 404}
                    }
                else:
                    return {
                        "verified": False,
                        "details": f"GitHub API error: {response.status_code}",
                        "raw_details": {"status_code": response.status_code, "response": response.text}
                    }
                    
        except httpx.RequestError as e:
            return {
                "verified": False,
                "details": f"HTTP request error during verification: {str(e)}",
                "raw_details": {"error": str(e)}
            }
        except Exception as e:
            return {
                "verified": False,
                "details": f"Unexpected error during verification: {str(e)}",
                "raw_details": {"error": str(e)}
            }
    
    @classmethod
    def from_env(cls) -> 'GitHubAPI':
        """Create GitHub API client from environment variables"""
        token = os.getenv("GITHUB_TOKEN")
        repo = os.getenv("GITHUB_REPO")
        
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        if not repo:
            raise ValueError("GITHUB_REPO environment variable is required")
            
        return cls(token, repo)