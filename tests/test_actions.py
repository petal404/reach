import pytest
from unittest.mock import patch, MagicMock
from src.actions import follow_users, unfollow_users
from datetime import datetime, timedelta, timezone

@patch('src.actions.get_users_to_follow')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
def test_follow_users_dry_run(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests the follow action in dry-run mode."""
    mock_load_config.return_value = ({'limits': {'max_follow': 50}, 'delays': {}}, {})
    mock_get_users.return_value = [{'username': 'testuser1'}]
    
    follow_users(dry_run=True)

    # In dry-run, it should mark the user as 'skipped' without calling the API
    mock_github_api.return_value.__aenter__.return_value.follow_user.assert_not_called()
    mock_update_status.assert_called_with('testuser1', 'skipped')

@patch('src.actions.get_followed_users')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
def test_unfollow_users_dry_run(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests the unfollow action in dry-run mode."""
    mock_load_config.return_value = ({'limits': {'max_unfollow': 50}, 'unfollow': {'inactive_days': 10}}, {})
    mock_get_users.return_value = [{'username': 'testuser2', 'followed_at': datetime.now() - timedelta(days=15)}]
    
    # Mock that the user is not following back
    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.check_is_follower.return_value = False
    mock_api_instance.get_user_details.return_value = None

    unfollow_users(dry_run=True)

    # In dry-run, it should not call the unfollow API
    mock_api_instance.unfollow_user.assert_not_called()
    

@patch('src.actions.get_followed_users')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
def test_unfollow_user_after_inactive_period(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests that a user is unfollowed if they haven't followed back within the inactive period."""
    inactive_days = 30
    mock_load_config.return_value = ({'limits': {'max_unfollow': 50}, 'unfollow': {'inactive_days': inactive_days}}, {})
    mock_get_users.return_value = [{'username': 'testuser3', 'followed_at': datetime.now() - timedelta(days=inactive_days + 1)}]

    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.check_is_follower.return_value = False
    mock_api_instance.get_user_details.return_value = None
    mock_api_instance.unfollow_user.return_value = True

    unfollow_users(dry_run=False)

    mock_api_instance.unfollow_user.assert_called_once_with('testuser3')
    mock_update_status.assert_called_once_with('testuser3', 'unfollowed')