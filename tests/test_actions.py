import pytest
import random
from unittest.mock import patch, MagicMock
from src.actions import follow_users, unfollow_users
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
@patch('src.actions.get_users_by_status_and_score')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
async def test_follow_users_dry_run(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests the follow action in dry-run mode."""
    mock_load_config.return_value = ({'limits': {'max_follow': 50}, 'delays': {}}, {})
    mock_get_users.return_value = [{'username': 'testuser1'}]

    await follow_users(dry_run=True)

    # In dry-run, it should mark the user as 'skipped' without calling the API
    mock_github_api.return_value.__aenter__.return_value.follow_user.assert_not_called()
    mock_update_status.assert_called_with('testuser1', 'skipped')

@pytest.mark.asyncio
@patch('src.actions.get_all_usernames_in_db')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
async def test_unfollow_users_dry_run(mock_load_config, mock_github_api, mock_update_status, mock_get_all_usernames):
    """Tests the unfollow action in dry-run mode."""
    mock_load_config.return_value = ({'limits': {'max_unfollow': 50}}, {})
    
    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.get_authenticated_user.return_value = 'botuser'
    
    # Bot follows these
    mock_api_instance.get_following.return_value = ['user1', 'user2', 'user3', 'user_in_db', 'follower_user']
    # These follow bot
    mock_api_instance.get_my_followers.return_value = ['follower_user']
    # These are in DB
    mock_get_all_usernames.return_value = {'user_in_db'}

    await unfollow_users(dry_run=True)

    # Candidates should be ['user1', 'user2', 'user3']
    # In dry-run, it should not call the unfollow API
    mock_api_instance.unfollow_user.assert_not_called()

@pytest.mark.asyncio
@patch('src.actions.get_all_usernames_in_db')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
async def test_unfollow_user_filters_correctly(mock_load_config, mock_github_api, mock_update_status, mock_get_all_usernames):
    """Tests that users are filtered correctly for unfollowing."""
    mock_load_config.return_value = ({'limits': {'max_unfollow': 10}}, {})
    
    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.get_authenticated_user.return_value = 'botuser'
    
    # user1: following, not follower, not in db -> CANDIDATE
    # user2: following, follower, not in db -> EXCLUDED (follower)
    # user3: following, not follower, in db -> EXCLUDED (in db)
    mock_api_instance.get_following.return_value = ['user1', 'user2', 'user3']
    mock_api_instance.get_my_followers.return_value = ['user2']
    mock_get_all_usernames.return_value = {'user3'}
    
    mock_api_instance.unfollow_user.return_value = True

    await unfollow_users(dry_run=False)

    # Should only unfollow user1
    mock_api_instance.unfollow_user.assert_called_once_with('user1')
    mock_update_status.assert_called_once_with('user1', 'unfollowed')
