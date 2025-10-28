import pytest
from unittest.mock import patch, MagicMock
from src.scanner import scan_for_users

@patch('src.scanner.GithubAPI')
@patch('src.scanner.ScoreCalculator')
@patch('src.scanner.load_config')
def test_scan_for_users_prioritizes_low_follower_users(mock_load_config, mock_score_calculator, mock_github_api):
    """Tests that the scanner prioritizes users with lower follower counts."""
    # Setup mock config
    mock_settings = {'limits': {'max_scan': 50, 'max_worker_threads': 1}}
    mock_criteria = {
        'repository_keywords': ['portfolio'],
        'user_bio_keywords': [],
        'negative_signals': {'max_followers': 250}
    }
    mock_load_config.return_value = (mock_settings, mock_criteria)

    # Setup mock repository and owner
    mock_owner_high_followers = MagicMock()
    mock_owner_high_followers.type = "User"
    mock_owner_high_followers.login = "user_high_followers"
    
    mock_owner_low_followers = MagicMock()
    mock_owner_low_followers.type = "User"
    mock_owner_low_followers.login = "user_low_followers"

    mock_repo_high = MagicMock()
    mock_repo_high.owner = mock_owner_high_followers
    
    mock_repo_low = MagicMock()
    mock_repo_low.owner = mock_owner_low_followers

    # Setup mock API response
    mock_api_instance = mock_github_api.return_value
    mock_api_instance.search_repositories.return_value = [mock_repo_high, mock_repo_low]
    
    # Mock get_user_details to return different follower counts
    def get_user_details_side_effect(username):
        if username == "user_high_followers":
            return {'followers_count': 200}
        elif username == "user_low_followers":
            return {'followers_count': 10}
        return None
    mock_api_instance.get_user_details.side_effect = get_user_details_side_effect

    # Mock process_user_for_scoring to track call order
    with patch('src.scanner.process_user_for_scoring') as mock_process_user:
        scan_for_users(dry_run=True)

        # Assertions
        # Check that the users were processed in the correct order (low followers first)
        call_args_list = [call.args[0] for call in mock_process_user.call_args_list]
        assert call_args_list == ["user_low_followers", "user_high_followers"]

@patch('src.scanner.GithubAPI')
@patch('src.scanner.ScoreCalculator')
@patch('src.scanner.load_config')
def test_scan_for_users_filters_disqualified_users_early(mock_load_config, mock_score_calculator, mock_github_api):
    """Tests that the scanner filters out users who are disqualified by high follower count early."""
    # Setup mock config
    mock_settings = {'limits': {'max_scan': 50, 'max_worker_threads': 1}}
    mock_criteria = {
        'repository_keywords': ['portfolio'],
        'user_bio_keywords': [],
        'negative_signals': {'max_followers': 100} # Lower threshold for testing
    }
    mock_load_config.return_value = (mock_settings, mock_criteria)

    # Setup mock repository and owner
    mock_owner_disqualified = MagicMock()
    mock_owner_disqualified.type = "User"
    mock_owner_disqualified.login = "user_disqualified"
    
    mock_owner_qualified = MagicMock()
    mock_owner_qualified.type = "User"
    mock_owner_qualified.login = "user_qualified"

    mock_repo_disqualified = MagicMock()
    mock_repo_disqualified.owner = mock_owner_disqualified
    
    mock_repo_qualified = MagicMock()
    mock_repo_qualified.owner = mock_owner_qualified

    # Setup mock API response
    mock_api_instance = mock_github_api.return_value
    mock_api_instance.search_repositories.return_value = [mock_repo_disqualified, mock_repo_qualified]
    
    # Mock get_user_details to return different follower counts
    def get_user_details_side_effect(username):
        if username == "user_disqualified":
            return {'followers_count': 150} # Above threshold
        elif username == "user_qualified":
            return {'followers_count': 50} # Below threshold
        return None
    mock_api_instance.get_user_details.side_effect = get_user_details_side_effect

    # Mock process_user_for_scoring to track calls
    with patch('src.scanner.process_user_for_scoring') as mock_process_user:
        scan_for_users(dry_run=True)

        # Assertions
        # Check that only the qualified user was processed
        mock_process_user.assert_called_once_with("user_qualified", mock_api_instance, mock_score_calculator.return_value, True, mock_settings)