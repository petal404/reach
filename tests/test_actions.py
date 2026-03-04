import pytest
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
@patch('src.actions.get_followed_users')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
async def test_unfollow_users_dry_run(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests the unfollow action in dry-run mode."""
    mock_load_config.return_value = ({'limits': {'max_unfollow': 50}}, {})
    # Return 2 followed users, one oldest and one newest
    mock_get_users.return_value = [
        {'username': 'testuser2', 'followed_at': datetime.now(timezone.utc) - timedelta(days=15)},
        {'username': 'testuser_follower', 'followed_at': datetime.now(timezone.utc) - timedelta(days=10)}
    ]

    # Mock that 'testuser2' is not following back, 'testuser_follower' is
    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.get_my_followers.return_value = ['testuser_follower']
    mock_api_instance.get_user_details.return_value = None

    await unfollow_users(dry_run=True)

    # In dry-run, it should not call the unfollow API
    mock_api_instance.unfollow_user.assert_not_called()


@pytest.mark.asyncio
@patch('src.actions.get_followed_users')
@patch('src.actions.update_user_status')
@patch('src.actions.GithubAPI')
@patch('src.actions.load_config')
async def test_unfollow_user_prioritizes_non_followers(mock_load_config, mock_github_api, mock_update_status, mock_get_users):
    """Tests that non-followers are prioritized for unfollowing."""
    mock_load_config.return_value = ({'limits': {'max_unfollow': 1}}, {})
    # testuser3 is oldest non-follower, testuser4 is newer non-follower
    mock_get_users.return_value = [
        {'username': 'testuser3', 'followed_at': datetime.now(timezone.utc) - timedelta(days=20)},
        {'username': 'testuser4', 'followed_at': datetime.now(timezone.utc) - timedelta(days=10)}
    ]

    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.get_my_followers.return_value = [] # No one follows back
    mock_api_instance.unfollow_user.return_value = True

    await unfollow_users(dry_run=False)

    # Should only unfollow the oldest one (testuser3) due to limit=1
    mock_api_instance.unfollow_user.assert_called_once_with('testuser3')
    mock_update_status.assert_called_once_with('testuser3', 'unfollowed')