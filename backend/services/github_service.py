"""
GitHub Service - Fetches Pull Request data from the GitHub API.

HOW IT WORKS:
    1. User provides a PR URL like: https://github.com/owner/repo/pull/123
    2. We parse out owner, repo, and PR number
    3. We call GitHub's REST API to get PR metadata and diff
    4. We return a PRData object that our agents can analyze

AUTHENTICATION:
    - Without a token: 60 requests/hour (enough for testing)
    - With a token: 5,000 requests/hour (needed for real use)
    - Set GITHUB_TOKEN in your .env file

DIFF FORMAT:
    GitHub returns diffs in "unified diff" format:
    ```
    diff --git a/file.py b/file.py
    --- a/file.py
    +++ b/file.py
    @@ -10,6 +10,8 @@
     unchanged line
    -removed line
    +added line
    ```
    Lines starting with + are additions, - are deletions.
    Our agents focus on + lines (new code being introduced).
"""

import re
from typing import Optional

import httpx

from backend.config import settings
from backend.models.schemas import FileChange, PRData


class GitHubService:
    """
    Fetches PR data from the GitHub REST API.

    Usage:
        service = GitHubService()
        pr_data = await service.fetch_pr_from_url("https://github.com/owner/repo/pull/123")
    """

    # Regex to parse GitHub PR URLs
    # Matches: https://github.com/owner/repo/pull/123
    PR_URL_PATTERN = re.compile(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    )

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.github_token
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PR-Review-AI/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=30.0,
        )

    def parse_pr_url(self, url: str) -> tuple[str, str, int]:
        """
        Extract owner, repo, and PR number from a GitHub URL.

        "https://github.com/facebook/react/pull/12345"
        -> ("facebook", "react", 12345)
        """
        match = self.PR_URL_PATTERN.match(url.strip())
        if not match:
            raise ValueError(
                f"Invalid GitHub PR URL: {url}\n"
                "Expected format: https://github.com/owner/repo/pull/123"
            )
        return match.group(1), match.group(2), int(match.group(3))

    async def fetch_pr(self, owner: str, repo: str, pr_number: int) -> PRData:
        """
        Fetch complete PR data from GitHub API.

        Makes 2 API calls:
        1. GET /repos/{owner}/{repo}/pulls/{pr_number} -> PR metadata
        2. GET /repos/{owner}/{repo}/pulls/{pr_number}/files -> changed files with patches
        """
        # Fetch PR metadata
        pr_response = await self.client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}"
        )

        if pr_response.status_code == 404:
            raise ValueError(f"PR not found: {owner}/{repo}#{pr_number}")
        if pr_response.status_code == 403:
            raise PermissionError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN in .env for higher limits."
            )
        pr_response.raise_for_status()
        pr_data = pr_response.json()

        # Fetch changed files (includes the diff patches)
        files_response = await self.client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
        )
        files_response.raise_for_status()
        files_data = files_response.json()

        # Parse file changes
        files = []
        raw_diff_parts = []

        for file_info in files_data:
            patch = file_info.get("patch", "")
            file_change = FileChange(
                filename=file_info["filename"],
                status=file_info["status"],
                additions=file_info.get("additions", 0),
                deletions=file_info.get("deletions", 0),
                patch=patch,
            )
            files.append(file_change)

            # Build the full diff text from all file patches
            if patch:
                raw_diff_parts.append(
                    f"--- a/{file_info['filename']}\n"
                    f"+++ b/{file_info['filename']}\n"
                    f"{patch}"
                )

        raw_diff = "\n\n".join(raw_diff_parts)

        return PRData(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=pr_data.get("title", ""),
            description=pr_data.get("body", "") or "",
            author=pr_data.get("user", {}).get("login", ""),
            files=files,
            raw_diff=raw_diff,
        )

    async def fetch_pr_from_url(self, url: str) -> PRData:
        """
        Convenience method: parse URL and fetch PR data in one call.

        This is what the API route calls when a user submits a PR URL.
        """
        owner, repo, pr_number = self.parse_pr_url(url)
        return await self.fetch_pr(owner, repo, pr_number)

    async def close(self):
        await self.client.aclose()
