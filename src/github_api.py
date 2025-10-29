import os
import httpx
import asyncio
import logging
import time
import time
import random
import re
from datetime import datetime, timezone
from .metrics import metrics_tracker

logger = logging.getLogger(__name__)

class GithubAPI:
    """An asynchronous wrapper for the GitHub API using httpx."""

    def __init__(self, pat=None, timeout=30.0):
        if not pat:
            pat = os.getenv("GITHUB_PAT")
        if not pat:
            raise ValueError("GitHub Personal Access Token not found. Please set GITHUB_PAT environment variable.")
        
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def _request(self, method, url, **kwargs):
        """A helper method to handle all API requests."""
        metrics_tracker.increment_api_requests()
        logger.debug(f"Request: {method} {url}", extra={'props': {"method": method, "url": url, "params": kwargs.get('params')}})
        try:
            response = await self.client.request(method, url, **kwargs)
            
            # Rate limit handling
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 100:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    time_until_reset = max(0, reset_time - time.time())
                    sleep_duration = time_until_reset + random.randint(199, 1620) # time to reset plus random bonus room after reset of 199 seconds to  27 minutes
                    logger.warning(f"Rate limit approaching ({remaining} left). Sleeping for {sleep_duration:.0f} seconds until after reset.")
                    metrics_tracker.add_sleep_time(sleep_duration)
                    await asyncio.sleep(sleep_duration)
            
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} for URL {e.request.url}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None

    async def search_repositories(self, query, limit, page=1):
        params = {"q": query, "per_page": limit, "page": page}
        data = await self._request("GET", "/search/repositories", params=params)
        return data['items'] if data and 'items' in data else []

    async def search_users(self, query, limit, sort='followers', order='asc', page=1):
        params = {"q": query, "sort": sort, "order": order, "per_page": limit, "page": page}
        data = await self._request("GET", "/search/users", params=params)
        return data['items'] if data and 'items' in data else []

    async def follow_user(self, username):
        response = await self._request("PUT", f"/user/following/{username}")
        return response is not None

    async def unfollow_user(self, username):
        response = await self._request("DELETE", f"/user/following/{username}")
        return response is not None

    async def check_is_follower(self, username):
        try:
            response = await self.client.get(f"/user/following/{username}")
            if response.status_code == 204: # 204 No Content means following
                return True
            elif response.status_code == 404: # 404 Not Found means not following
                return False
            else:
                response.raise_for_status() # Raise for other unexpected status codes
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False # Explicitly handle 404 as not following
            logger.error(f"HTTP error checking follower status for {username}: {e.response.status_code} for URL {e.request.url}")
            return False # Assume not a follower on other errors
        except Exception as e:
            logger.error(f"An error occurred checking follower status for {username}: {e}")
            return False

    async def get_user_details(self, username):
        return await self._request("GET", f"/users/{username}")

    async def get_user_repos(self, username):
        repos = await self._request("GET", f"/users/{username}/repos")
        if not repos:
            return []

        async def get_commit_count(repo):
            owner = repo['owner']['login']
            repo_name = repo['name']
            # Fetch just one commit to get totalCount efficiently from headers
            response = await self.client.head(f"/repos/{owner}/{repo_name}/commits?per_page=1")
            if 'link' in response.headers:
                link_header = response.headers['link']
                # Regex to find the last page number
                match = re.search(r'page=(\d+)[^>]*>; rel="last"', link_header)
                if match:
                    return int(match.group(1))
            # Fallback if Link header is not present or doesn't contain 'last' rel
            # This might not be accurate for very large repos, but better than nothing
            commits_data = await self._request("GET", f"/repos/{owner}/{repo_name}/commits?per_page=1")
            return len(commits_data) if commits_data else 0

        # Gather all commit count fetching tasks concurrently
        commit_counts = await asyncio.gather(*[get_commit_count(repo) for repo in repos])

        for i, repo in enumerate(repos):
            repo['commits_count'] = commit_counts[i]

        return repos

    async def get_user_starred_repos(self, username):
        return await self._request("GET", f"/users/{username}/starred")

    async def get_user_organizations(self, username):
        return await self._request("GET", f"/users/{username}/orgs")

    async def get_user_events(self, username, since_date=None):
        # Note: since_date is not directly supported by this endpoint in this manner
        return await self._request("GET", f"/users/{username}/events")

    async def get_repo_readme_content(self, owner, repo_name):
        data = await self._request("GET", f"/repos/{owner}/{repo_name}/readme")
        if data and 'content' in data:
            import base64
            return base64.b64decode(data['content']).decode('utf-8')
        return None

    async def get_public_events(self, per_page=100):
        return await self._request("GET", "/events", params={"per_page": per_page})

    async def get_authenticated_user(self):
        """Gets the username of the authenticated user."""
        data = await self._request("GET", "/user")
        return data['login'] if data and 'login' in data else None

    async def get_following(self, username):
        """Gets the full list of users a user is following, handling pagination."""
        following_list = []
        page = 1
        while True:
            params = {"per_page": 100, "page": page}
            data = await self._request("GET", f"/users/{username}/following", params=params)
            if data:
                following_list.extend([user['login'] for user in data])
                if len(data) < 100:
                    break # Last page
                page += 1
            else:
                break # No data or an error occurred
        return following_list

    async def get_comprehensive_user_data(self, username, since_date_events=None):
        user_details, repos_data, starred_repos_data, orgs_data, events_data, profile_readme_content = await asyncio.gather(
            self.get_user_details(username),
            self.get_user_repos(username),
            self.get_user_starred_repos(username),
            self.get_user_organizations(username),
            self.get_user_events(username, since_date=since_date_events),
            self.get_repo_readme_content(username, username)
        )

        if not user_details:
            return None, None, None, None, None, None

        # Calculate total contributions from repos
        if repos_data:
            total_contributions = sum(repo.get('commits_count', 0) for repo in repos_data)
            user_details['total_contributions'] = total_contributions
        else:
            user_details['total_contributions'] = 0

        return user_details, repos_data, starred_repos_data, orgs_data, events_data, profile_readme_content
