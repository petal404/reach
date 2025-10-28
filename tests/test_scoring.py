import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.scoring import ScoreCalculator

# Mock criteria_config for testing
MOCK_CRITERIA = {
    "weights": {
        "primary": 10,
        "secondary": 7,
        "tertiary": 3,
        "keyword_in_name": 1.5, # Multiplier for keywords found in repo name
        "keyword_in_description": 1.2, # Multiplier for keywords found in repo description
        "keyword_in_topic": 1.3, # Multiplier for keywords found in repo topics
        "keyword_in_bio": 1.0, # Multiplier for keywords found in user bio
        "keyword_in_commit": 0.8 # Multiplier for keywords found in commit messages
    },
    "negative_signals": {
        "max_followers": 250,
        "max_following": 1000,
        "max_total_contributions": 2000,
        "max_inactivity_days": 180,
        "seniority_keywords": ["senior", "lead", "staff", "principal", "architect", "google", "meta", "faang"]
    },
    "tier1_signals": {
        "abandoned_portfolio_repo": {
            "commit_count_threshold": 10,
            "last_commit_days_ago": 14,
            "repo_keywords": ["portfolio", "personal-website"]
        },
        "multiple_recent_portfolio_forks": {
            "fork_count_threshold": 2,
            "days_ago": 90,
            "repo_keywords": ["portfolio", "template"]
        },
        "starred_portfolio_no_website": {
            "star_count_threshold": 2,
            "days_ago": 90,
            "repo_keywords": ["portfolio", "template"]
        },
        "opened_portfolio_issues_low_commits": {
            "issue_pr_count_threshold": 1,
            "days_ago": 90,
            "commit_count_threshold": 10,
            "repo_keywords": ["portfolio", "personal-website"]
        },
        "career_switcher_bootcamp": {
            "account_age_months": 12,
            "high_activity_commits": 50,
            "bootcamp_orgs": ["generalassemb.ly"]
        },
        "returning_professional": {
            "inactive_days": 270,
            "recent_commits": 5,
            "profile_updated_days": 60
        },
        "active_job_seeker": {
            "profile_updated_days": 60
        }
    },
    "score_thresholds": {
        "perfect_target": 10.0,
        "urgent_high_value": 9.0,
        "strong_target": 8.0,
        "good_target": 7.0,
        "moderate_target": 6.0,
        "low_priority": 3.0,
        "insufficient_match": 0.0,
        "disqualified": -1.0
    },
    "metrics": {
        "junior_developer_activity": {
            "weight": 9,
            "type": "primary",
            "logic": "10–500 total commits, account age 1–3 years, recent frequent commits last 3 months."
        },
        "few_followers": {
            "weight": 6,
            "type": "secondary",
            "logic": "<50 followers."
        },
        "incomplete_profile_no_website": {
            "weight": 6,
            "type": "secondary",
            "logic": "No website URL + bio present or absent."
        },
        "portfolio_keywords_in_bio": {
            "weight": 3,
            "type": "tertiary",
            "logic": "Contains `portfolio`, `developer`, `web` in bio."
        }
    }
}

@pytest.fixture
def score_calculator():
    return ScoreCalculator(MOCK_CRITERIA)

# --- Test Disqualifiers ---
def test_disqualify_organization(score_calculator):
    user_data = {'type': 'Organization'}
    is_disqualified, reason, audit_log = score_calculator._evaluate_disqualifiers(user_data, [], [])
    assert is_disqualified is True
    assert reason == "Is an Organization"

def test_disqualify_high_followers(score_calculator):
    user_data = {'type': 'User', 'followers_count': 300}
    is_disqualified, reason, audit_log = score_calculator._evaluate_disqualifiers(user_data, [], [])
    assert is_disqualified is True
    assert reason == "High Follower Count"

def test_disqualify_seniority_keyword(score_calculator):
    user_data = {'type': 'User', 'bio': 'I am a Senior Architect at Google.'}
    is_disqualified, reason, audit_log = score_calculator._evaluate_disqualifiers(user_data, [], [])
    assert is_disqualified is True
    assert reason == "Seniority Keyword in Bio"

# --- Test Tier-1 Signals ---
def test_tier1_abandoned_portfolio_repo(score_calculator):
    two_weeks_ago = datetime.now() - timedelta(days=15)
    user_data = {'type': 'User'}
    repos_data = [
        {'name': 'my-portfolio', 'commits_count': 5, 'pushed_at': two_weeks_ago, 'fork': False}
    ]
    score, details = score_calculator._evaluate_tier1_signals(user_calculator, user_data, repos_data, [], [])
    assert score == 10.0
    assert details[0]['signal'] == "Abandoned Portfolio Repo"

def test_tier1_multiple_recent_portfolio_forks(score_calculator):
    one_month_ago = datetime.now() - timedelta(days=30)
    user_data = {'type': 'User'}
    repos_data = [
        {'name': 'template-portfolio-fork1', 'fork': True, 'pushed_at': one_month_ago},
        {'name': 'template-portfolio-fork2', 'fork': True, 'pushed_at': one_month_ago}
    ]
    score, details = score_calculator._evaluate_tier1_signals(user_calculator, user_data, repos_data, [], [])
    assert score == 10.0
    assert details[0]['signal'] == "Multiple Recent Portfolio Forks"

# --- Test Subscore Calculations (Examples) ---
def test_subscore_junior_developer_activity(score_calculator):
    user_data = {
        'type': 'User',
        'total_contributions': 250,
        'created_at': datetime.now() - timedelta(days=365 * 2), # 2 years old
        'last_activity_at': datetime.now() - timedelta(days=10) # 10 days ago
    }
    subscore, details = score_calculator._calculate_subscore("junior_developer_activity", user_data, [], [], [], [], None)
    # Expected: 0.4 + (250-10)/(500-10) * 0.6 = 0.4 + 240/490 * 0.6 = 0.4 + 0.48979 * 0.6 = 0.4 + 0.2938 = 0.6938
    # Rounded to 1 decimal place for comparison in final score, but subscore is float
    assert subscore == pytest.approx(0.6938, rel=1e-2)

def test_subscore_few_followers(score_calculator):
    user_data = {'type': 'User', 'followers_count': 30}
    subscore, details = score_calculator._calculate_subscore("few_followers", user_data, [], [], [], [], None)
    assert subscore == 1.0

def test_subscore_portfolio_keywords_in_bio(score_calculator):
    user_data = {'type': 'User', 'bio': 'I am a web developer with a portfolio.'}
    subscore, details = score_calculator._calculate_subscore("portfolio_keywords_in_bio", user_data, [], [], [], [], None)
    assert subscore == 1.0

# --- Test Final Score Calculation ---
def test_final_score_disqualified(score_calculator):
    user_data = {'type': 'Organization'}
    final_score, status, audit_log = score_calculator.calculate_final_score(user_data, [], [], [], [], None)
    assert final_score == -1.0
    assert status == "Disqualified"

def test_final_score_tier1_perfect_target(score_calculator):
    two_weeks_ago = datetime.now() - timedelta(days=15)
    user_data = {'type': 'User'}
    repos_data = [
        {'name': 'my-portfolio', 'commits_count': 5, 'pushed_at': two_weeks_ago, 'fork': False}
    ]
    final_score, status, audit_log = score_calculator.calculate_final_score(user_data, repos_data, [], [], [], None)
    assert final_score == 10.0
    assert status == "Perfect Target"

def test_final_score_composite_case(score_calculator):
    user_data = {
        'type': 'User',
        'total_contributions': 250, # Junior dev
        'created_at': datetime.now() - timedelta(days=365 * 2), # 2 years old
        'last_activity_at': datetime.now() - timedelta(days=10), # 10 days ago
        'followers_count': 40, # Few followers
        'bio': 'I am a web developer.', # Portfolio keywords in bio
        'blog': None # Incomplete profile
    }
    repos_data = []
    starred_repos_data = [
        {'name': 'some-portfolio-template', 'pushed_at': datetime.now() - timedelta(days=60)} # Starred 1 portfolio repo
    ]
    
    final_score, status, audit_log = score_calculator.calculate_final_score(user_data, repos_data, starred_repos_data, [], [], None)
    # This test needs to be refined as _calculate_subscore is not fully implemented yet.
    # For now, just check if it doesn't crash and returns a valid score/status.
    assert isinstance(final_score, float)
    assert status in ["Perfect Target", "Urgent High Value", "Strong Target", "Good Target", "Moderate Target", "Low Priority", "Insufficient Match", "Disqualified"]
