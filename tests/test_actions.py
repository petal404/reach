import pytest
from unittest.mock import patch, MagicMock
from src.actions import follow_users, unfollow_users

@patch('src.actions.get_users_to_follow')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_settings')
def test_follow_users_dry_run(mock_load_settings, mock_github_api, mock_update_status, mock_get_users):
    """Tests the follow action in dry-run mode."""
    mock_load_settings.return_value = {'limits': {'max_follow': 50}, 'delays': {}}
    mock_get_users.return_value = [{'username': 'testuser1'}]
    
    follow_users(dry_run=True)

    # In dry-run, it should mark the user as 'skipped' without calling the API
    mock_github_api.return_value.follow_user.assert_not_called()
    mock_update_status.assert_called_once_with('testuser1', 'skipped')

@patch('src.actions.get_followed_users')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_settings')
def test_unfollow_users_dry_run(mock_load_settings, mock_github_api, mock_update_status, mock_get_users):
    """Tests the unfollow action in dry-run mode."""
    mock_load_settings.return_value = {'limits': {'max_unfollow': 50}, 'delays': {}}
    mock_get_users.return_value = [{'username': 'testuser2'}]
    
    # Mock that the user is not following back
    mock_api_instance = mock_github_api.return_value
    mock_api_instance.check_is_follower.return_value = False

    unfollow_users(dry_run=True)

    # In dry-run, it should mark the user as 'skipped' without calling the API
    mock_api_instance.unfollow_user.assert_not_called()
    mock_update_status.assert_called_once_with('testuser2', 'skipped')