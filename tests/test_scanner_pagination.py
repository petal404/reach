import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.scanner import scan_for_users

@pytest.mark.asyncio
async def test_scan_for_users_pagination():
    """Tests that the scanner requests multiple pages of search results."""
    
    # Mock dependencies
    with patch('src.scanner.GithubAPI') as mock_github_api_cls, \
         patch('src.scanner.load_config') as mock_load_config, \
         patch('src.scanner.UserValidator') as mock_validator, \
         patch('src.scanner.process_user') as mock_process_user:

        # Setup Mock API
        mock_api = AsyncMock()
        mock_github_api_cls.return_value.__aenter__.return_value = mock_api
        
        # Mock get_authenticated_user to return None to skip following check logic or a user to test it
        mock_api.get_authenticated_user.return_value = "bot_user"
        mock_api.get_following.return_value = []
        mock_api.get_public_events.return_value = [] # Skip event scanning for this test

        # Mock search_repositories to return empty list (we just want to check calls)
        mock_api.search_repositories.return_value = []

        # Setup Mock Config
        # minimal config
        mock_settings = {}
        mock_criteria = {
            'repository_keywords': ['portfolio'],
            'negative_signals': {'max_followers': 100}
        }
        mock_load_config.return_value = (mock_settings, mock_criteria)

        # Run the scanner
        await scan_for_users(dry_run=True)

        # Verification
        # We expect search_repositories to be called 5 times (pages 1-5) for the single keyword 'portfolio'
        assert mock_api.search_repositories.call_count == 5
        
        # Check arguments for each call
        calls = mock_api.search_repositories.call_args_list
        pages_requested = [call.kwargs.get('page') for call in calls]
        assert sorted(pages_requested) == [1, 2, 3, 4, 5]
