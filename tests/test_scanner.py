
import pytest
from unittest.mock import patch, MagicMock
from src.scanner import scan_for_users, build_dynamic_query

@patch('src.scanner.GithubAPI')
@patch('src.scanner.add_or_update_user')
@patch('src.scanner.load_config')
def test_scan_for_users_dry_run(mock_load_config, mock_add_user, mock_github_api):
    """Tests the scanner in dry-run mode to ensure no database writes occur."""
    # Setup mock config
    mock_settings = {'language': 'python', 'limits': {'max_scan': 50}, 'delays': {}}
    mock_criteria = {
        'negative_signals': {
            'max_followers': 100,
            'min_public_repos': 5,
            'max_public_repos': 20,
            'max_account_age_days': 365
        }
    }
    mock_load_config.return_value = (mock_settings, mock_criteria)

    # Setup mock user
    mock_user = MagicMock()
    mock_user.login = "testuser"

    # Setup mock API response
    mock_api_instance = mock_github_api.return_value.__aenter__.return_value
    mock_api_instance.search_users.return_value = [mock_user]
    mock_api_instance.get_comprehensive_user_data.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

    # Mock the ScoreCalculator
    with patch('src.scanner.ScoreCalculator') as mock_score_calculator:
        mock_score_instance = mock_score_calculator.return_value
        mock_score_instance.calculate_final_score.return_value = (5.0, 'Good Target', {})

        scan_for_users(dry_run=True)

    # Assertions
    mock_api_instance.search_users.assert_called_once()
    # Ensure user was NOT added to the database in dry-run
    mock_add_user.assert_not_called()

def test_build_dynamic_query():
    """Tests the dynamic query builder."""
    settings = {
        'language': 'python'
    }
    criteria = {
        'negative_signals': {
            'max_followers': 100,
            'min_public_repos': 5,
            'max_public_repos': 20,
            'max_account_age_days': 365
        }
    }

    query = build_dynamic_query(settings, criteria)

    assert 'language:python' in query
    assert 'followers:0..100' in query
    assert 'repos:5..20' in query
    assert 'created:>=' in query
