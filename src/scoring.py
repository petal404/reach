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
            return True, "Organization account"

        # Check for high follower count
        if user_data.get('followers', 0) > self.negative_signals.get('max_followers', 100):
            return True, "Follower count exceeds threshold"

        # Check for high following count
        if user_data.get('following', 0) > self.negative_signals.get('max_following', 500):
            return True, "Following count exceeds threshold"

        # Check for inactivity
        max_inactivity_days = self.negative_signals.get('max_inactivity_days', 180)
        if user_data.get('updated_at') and (datetime.now(timezone.utc) - datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00'))).days > max_inactivity_days:
            return True, "Account inactive for extended period"

        # Check for seniority keywords in bio
        bio_content = user_data.get('bio', '')
        if bio_content:
            bio_content_lower = bio_content.lower()
            seniority_keywords = [k.lower() for k in self.negative_signals.get('seniority_keywords', [])]
            for keyword in seniority_keywords:
                if keyword in bio_content_lower:
                    return True, "Seniority keyword detected in bio"
        
        # Check for existing portfolio (blog URL)
        blog_url = user_data.get('blog', '')
        if blog_url and not any(domain in blog_url for domain in ['github.com', 'linkedin.com', 'twitter.com', 'medium.com', 'youtube.com', 'instagram.com', 'facebook.com', 'tiktok.com', 'gmail.com', 'orcid.org', 'x.com' ]):
            return True, "Established external portfolio link found"

        # Check for explicit exclusion keywords
        exclude_keywords = [k.lower() for k in self.negative_signals.get('exclude_keywords', [])]
        if exclude_keywords and bio_content:
            bio_content_lower = bio_content.lower()
            for keyword in exclude_keywords:
                if keyword in bio_content_lower:
                    return True, "Excluded keyword found in bio"
                    
        # Check for explicit exclusion users
        exclude_users = [u.lower() for u in self.negative_signals.get('exclude_users', [])]
        username = user_data.get('login', '').lower()
        if username and username in exclude_users:
            return True, "User is in explicit exclusion list"

        return False, None
