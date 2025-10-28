import logging
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)
DB_FILE = "reach.db"

# Define the database engine
engine = create_engine(f"sqlite:///{DB_FILE}")
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    github_id = Column(Integer, unique=True, nullable=False)
    profile_url = Column(String)
    score = Column(Float, default=0.0)
    status = Column(String, default='targeted') # targeted, followed, unfollowed, skipped, disqualified
    last_scanned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    followed_at = Column(DateTime)
    unfollowed_at = Column(DateTime)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    public_repos_count = Column(Integer, default=0)
    total_contributions = Column(Integer, default=0)
    account_created_at = Column(DateTime)
    profile_updated_at = Column(DateTime)
    last_activity_at = Column(DateTime)
    is_organization = Column(Boolean, default=False)
    bio_content = Column(Text)
    blog_url = Column(String)
    score_audit_log = Column(Text) # Storing JSON string of audit log

    def to_dict(self):
        """Returns a dictionary representation of the User object."""
        return {
            'id': self.id,
            'username': self.username,
            'github_id': self.github_id,
            'profile_url': self.profile_url,
            'score': self.score,
            'status': self.status,
            'last_scanned_at': self.last_scanned_at.isoformat() if self.last_scanned_at else None,
            'followed_at': self.followed_at.isoformat() if self.followed_at else None,
            'unfollowed_at': self.unfollowed_at.isoformat() if self.unfollowed_at else None,
            'followers_count': self.followers_count,
            'following_count': self.following_count,
            'public_repos_count': self.public_repos_count,
            'total_contributions': self.total_contributions,
            'account_created_at': self.account_created_at.isoformat() if self.account_created_at else None,
            'profile_updated_at': self.profile_updated_at.isoformat() if self.profile_updated_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'is_organization': self.is_organization,
            'bio_content': self.bio_content,
            'blog_url': self.blog_url,
            'score_audit_log': self.score_audit_log
        }

    def __repr__(self):
        return f"<User(username='{self.username}', score={self.score}, status='{self.status}')>"

class Log(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Log(level='{self.level}', message='{self.message[:50]}...')>"

class DisqualifiedUser(Base):
    __tablename__ = 'disqualified_users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    disqualified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<DisqualifiedUser(username='{self.username}', disqualified_at='{self.disqualified_at}')>"


class BotStatus(Base):
    __tablename__ = 'bot_status'

    id = Column(Integer, primary_key=True, default=1) # Only one row expected
    current_phase = Column(String, default='Idle')
    last_update = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def initialize_database():
    """Creates the necessary database tables if they don't exist."""
    Base.metadata.create_all(engine)
    session = Session()
    try:
        # Ensure there's always a status entry
        if not session.query(BotStatus).first():
            session.add(BotStatus(current_phase='Idle'))
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error initializing BotStatus: {e}")
    finally:
        session.close()
    logger.info("Database initialized successfully with SQLAlchemy.")

def add_disqualified_user(username):
    """Adds a user to the disqualified list."""
    session = Session()
    try:
        existing_user = session.query(DisqualifiedUser).filter_by(username=username).first()
        if not existing_user:
            new_disqualified_user = DisqualifiedUser(username=username)
            session.add(new_disqualified_user)
            session.commit()
            logger.info(f"User '{username}' added to the disqualified list.")
        else:
            logger.info(f"User '{username}' is already in the disqualified list.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding user '{username}' to disqualified list: {e}")
    finally:
        session.close()

def is_user_disqualified(username):
    """Checks if a user is in the disqualified list and if 3 months have passed."""
    session = Session()
    try:
        user = session.query(DisqualifiedUser).filter_by(username=username).first()
        if user:
            three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
            if user.disqualified_at > three_months_ago:
                return True  # User is disqualified and within the 3-month period
            else:
                # User's disqualification period has expired, so remove them from the list
                session.delete(user)
                session.commit()
                logger.info(f"User '{username}' has been removed from the disqualified list after 3 months.")
                return False
        return False  # User is not in the disqualified list
    finally:
        session.close()


def add_or_update_user(user_data, status):
    """Adds a new user or updates their score and scan time if they already exist."""
    if status == 'Disqualified':
        add_disqualified_user(user_data['login'])

    session = Session()
    try:
        user = session.query(User).filter_by(username=user_data['login']).first()
        if user:
            user.status = status
            user.last_scanned_at = datetime.now(timezone.utc)
            logger.info(f"Updated user '{user_data['login']}' with status '{status}'.")
        else:
            new_user = User(
                username=user_data['login'],
                github_id=user_data['id'],
                profile_url=user_data['html_url'],
                status=status,
                followers_count=user_data.get('followers', 0),
                following_count=user_data.get('following', 0),
                public_repos_count=user_data.get('public_repos', 0),
                account_created_at=datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00')),
                profile_updated_at=datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00')),
                last_activity_at=datetime.fromisoformat(user_data['updated_at'].replace('Z', '+00:00')),
                is_organization=user_data.get('type', 'User') == "Organization",
                bio_content=user_data.get('bio'),
                blog_url=user_data.get('blog')
            )
            session.add(new_user)
            logger.info(f"Added new user '{user_data['login']}' with status '{status}'.")
        session.commit()
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Integrity error adding/updating user {user_data['login']}: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding/updating user {user_data['login']}: {e}")
    finally:
        session.close()

def get_user_data_from_db(username):
    """Retrieves all stored data for a user from the database."""
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user:
            return user.to_dict()
        return None
    finally:
        session.close()

def get_followed_users():
    """Retrieves all users with 'followed' status."""
    session = Session()
    try:
        users = session.query(User).filter_by(status='followed').all()
        return [{
            'username': user.username,
            'followed_at': user.followed_at # Only need this for unfollow logic
        } for user in users]
    finally:
        session.close()

def get_users_to_follow(limit):
    """Retrieves a list of the highest-scoring users with 'targeted' status."""
    session = Session()
    try:
        users = session.query(User).filter_by(status='targeted').order_by(User.score.desc()).limit(limit).all()
        return [user.to_dict() for user in users]
    finally:
        session.close()

def update_user_status(username, status):
    """Updates the status for a user, or deletes them if unfollowed."""
    session = Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user:
            if status == 'unfollowed':
                session.delete(user)
                logger.info(f"User '{username}' has been unfollowed and removed from the database.")
            else:
                user.status = status
                if status == 'followed':
                    user.followed_at = datetime.now(timezone.utc)
                logger.info(f"Updated status for user '{username}' to '{status}'.")
            session.commit()
        else:
            logger.warning(f"User '{username}' not found for status update.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating status for user {username}: {e}")
    finally:
        session.close()

def get_users_by_status_and_score(status, min_score, limit, max_score=None):
    """Retrieves users by status and within a score range, ordered by score."""
    session = Session()
    try:
        query = session.query(User).filter(User.status == status, User.score >= min_score)
        if max_score is not None:
            query = query.filter(User.score <= max_score)
        users = query.order_by(User.score.desc()).limit(limit).all()
        return [user.to_dict() for user in users]
    finally:
        session.close()

def get_target_stats():
    """Calculates statistics about the current targets in the database."""
    session = Session()
    try:
        scheduled_statuses = ['Perfect Target', 'Urgent High Value', 'Strong Target', 'Good Target', 'Moderate Target', 'Low Priority']
        high_priority_statuses = ['Perfect Target', 'Urgent High Value']

        total_scheduled = session.query(User).filter(User.status.in_(scheduled_statuses)).count()
        high_priority_scheduled = session.query(User).filter(User.status.in_(high_priority_statuses)).count()

        return {
            'total_scheduled': total_scheduled,
            'high_priority_scheduled': high_priority_scheduled
        }
    finally:
        session.close()

def update_bot_status(phase: str):
    """Updates the bot's current operational phase in the database."""
    session = Session()
    try:
        status_entry = session.query(BotStatus).first()
        if status_entry:
            status_entry.current_phase = phase
            status_entry.last_update = datetime.now(timezone.utc)
        else:
            session.add(BotStatus(current_phase=phase))
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating bot status to {phase}: {e}")
    finally:
        session.close()

def get_dashboard_data():
    """Fetches all data required for the dashboard."""
    session = Session()
    try:
        # Overall Stats
        total_users = session.query(User).count()
        followed_count = session.query(User).filter_by(status='followed').count()
        unfollowed_count = session.query(User).filter_by(status='unfollowed').count()
        disqualified_count = session.query(User).filter_by(status='Disqualified').count()
        targeted_count = session.query(User).filter(User.status.in_(['Perfect Target', 'Urgent High Value', 'Strong Target', 'Good Target', 'Moderate Target', 'Low Priority'])).count()

        # Bot Status
        bot_status_entry = session.query(BotStatus).first()
        current_bot_phase = bot_status_entry.current_phase if bot_status_entry else 'Unknown'

        # Top Targeted Users
        top_targeted_users = session.query(User).filter(User.status.in_(['Perfect Target', 'Urgent High Value', 'Strong Target', 'Good Target', 'Moderate Target', 'Low Priority'])) \
                                            .order_by(User.score.desc()).limit(20).all()
        top_targeted_users_data = [user.to_dict() for user in top_targeted_users]

        # Recent Logs
        recent_logs = session.query(Log).order_by(Log.timestamp.desc()).limit(20).all()
        log_data = [{
            'timestamp': log.timestamp.isoformat(),
            'level': log.level,
            'message': log.message
        } for log in recent_logs]

        return {
            'total_users': total_users,
            'followed_count': followed_count,
            'unfollowed_count': unfollowed_count,
            'disqualified_count': disqualified_count,
            'targeted_count': targeted_count,
            'current_bot_phase': current_bot_phase,
            'top_targeted_users': top_targeted_users_data,
            'recent_logs': log_data
        }
    finally:
        session.close()

def get_user_stats():
    """Calculates statistics about the users in the database."""
    session = Session()
    try:
        stats = {
            'total_users': session.query(User).count(),
            'followed': session.query(User).filter_by(status='followed').count(),
            'unfollowed': session.query(User).filter_by(status='unfollowed').count(),
            'disqualified': session.query(User).filter_by(status='Disqualified').count(),
            'targeted': session.query(User).filter(User.status.like('%Target%')).count(),
        }
        return stats
    finally:
        session.close()

if __name__ == '__main__':
    initialize_database()
