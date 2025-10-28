import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class UserValidator:
    def __init__(self, criteria_config):
        self.criteria = criteria_config
        self.negative_signals = criteria_config.get('negative_signals', {})

    def is_disqualified(self, user_data):
        """Checks if a user meets any of the disqualification criteria."""
        # Check for organization account type
        if user_data.get('type') == "Organization":
            return True, "Is an Organization"

        # Check for high follower count
        if user_data.get('followers', 0) > self.negative_signals.get('max_followers', 100):
            return True, f"Followers ({user_data['followers']}) > Max ({self.negative_signals['max_followers']})"

        # Check for high following count
        if user_data.get('following', 0) > self.negative_signals.get('max_following', 500):
            return True, f"Following ({user_data['following']}) > Max ({self.negative_signals['max_following']})"

        # Check for inactivity
        max_inactivity_days = self.negative_signals.get('max_inactivity_days', 180)
        if user_data.get('updated_at') and (datetime.now(timezone.utc) - datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00'))).days > max_inactivity_days:
            return True, f"Last activity > {max_inactivity_days} days ago"

        # Check for seniority keywords in bio
        bio_content = user_data.get('bio', '')
        if bio_content:
            bio_content = bio_content.lower()
            seniority_keywords = [k.lower() for k in self.negative_signals.get('seniority_keywords', [])]
            for keyword in seniority_keywords:
                if keyword in bio_content:
                    return True, f"Bio contains seniority keyword: '{keyword}'"
        
        # Check for existing portfolio (blog URL)
        blog_url = user_data.get('blog', '')
        if blog_url and not any(domain in blog_url for domain in ['github.com', 'linkedin.com', 'twitter.com', 'medium.com', 'youtube.com', 'instagram.com', 'facebook.com', 'tiktok.com']):
            return True, f"Has established portfolio: {blog_url}"

        return False, None