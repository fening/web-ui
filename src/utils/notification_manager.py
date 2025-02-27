import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import uuid
import os

logger = logging.getLogger(__name__)

class NotificationLevel(Enum):
    """Notification importance level"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class Notification:
    """Represents a single notification message"""
    
    def __init__(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        title: str = None,
        details: str = None,
        action_url: str = None,
        expires_in: int = 30,  # seconds
        id: str = None
    ):
        self.id = id or str(uuid.uuid4())
        self.message = message
        self.level = level
        self.title = title or self._default_title(level)
        self.details = details
        self.action_url = action_url
        self.timestamp = datetime.now()
        self.expires_at = None if expires_in is None else (
            self.timestamp.timestamp() + expires_in
        )
        self.read = False
        
    def _default_title(self, level: NotificationLevel) -> str:
        """Generate a default title based on notification level"""
        if level == NotificationLevel.INFO:
            return "Information"
        elif level == NotificationLevel.SUCCESS:
            return "Success"
        elif level == NotificationLevel.WARNING:
            return "Warning"
        elif level == NotificationLevel.ERROR:
            return "Error"
        return "Notification"
    
    def is_expired(self) -> bool:
        """Check if notification has expired"""
        if self.expires_at is None:
            return False
        return datetime.now().timestamp() > self.expires_at
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.read = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/UI"""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "details": self.details,
            "action_url": self.action_url,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at,
            "read": self.read
        }

class NotificationManager:
    """Manages application notifications"""
    
    def __init__(self, max_history: int = 100):
        self.notifications: List[Notification] = []
        self.max_history = max_history
        self.listeners: List[Callable] = []
        self.audio_enabled = True
        
    def add(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        title: str = None,
        details: str = None,
        action_url: str = None,
        expires_in: int = 30,
        notify_ui: bool = True,
        play_sound: bool = True
    ) -> Notification:
        """Add a new notification"""
        notification = Notification(
            message=message,
            level=level,
            title=title,
            details=details,
            action_url=action_url,
            expires_in=expires_in
        )
        
        # Add to list, maintaining max history
        self.notifications.append(notification)
        if len(self.notifications) > self.max_history:
            self.notifications.pop(0)
            
        # Log notification
        log_msg = f"{notification.title}: {notification.message}"
        if notification.level == NotificationLevel.ERROR:
            logger.error(log_msg)
        elif notification.level == NotificationLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # Notify UI listeners
        if notify_ui:
            self._notify_listeners(notification)
            
        # Play sound if enabled
        if play_sound and self.audio_enabled:
            self._play_notification_sound(notification.level)
            
        return notification
    
    def info(self, message: str, **kwargs) -> Notification:
        """Add an info notification"""
        return self.add(message, NotificationLevel.INFO, **kwargs)
    
    def success(self, message: str, **kwargs) -> Notification:
        """Add a success notification"""
        return self.add(message, NotificationLevel.SUCCESS, **kwargs)
        
    def warning(self, message: str, **kwargs) -> Notification:
        """Add a warning notification"""
        return self.add(message, NotificationLevel.WARNING, **kwargs)
        
    def error(self, message: str, **kwargs) -> Notification:
        """Add an error notification"""
        return self.add(message, NotificationLevel.ERROR, **kwargs)
    
    def get_unread(self) -> List[Notification]:
        """Get all unread notifications"""
        return [n for n in self.notifications if not n.read]
    
    def get_recent(self, count: int = 5) -> List[Notification]:
        """Get most recent notifications"""
        return self.notifications[-count:]
    
    def mark_all_read(self) -> int:
        """Mark all notifications as read"""
        unread_count = 0
        for notification in self.notifications:
            if not notification.read:
                notification.mark_as_read()
                unread_count += 1
        return unread_count
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark a specific notification as read"""
        for notification in self.notifications:
            if notification.id == notification_id:
                notification.mark_as_read()
                return True
        return False
    
    def clear_expired(self) -> int:
        """Remove expired notifications"""
        original_count = len(self.notifications)
        self.notifications = [n for n in self.notifications if not n.is_expired()]
        return original_count - len(self.notifications)
    
    def add_listener(self, callback: Callable[[Notification], None]):
        """Add a notification listener"""
        if callback not in self.listeners:
            self.listeners.append(callback)
    
    def remove_listener(self, callback: Callable):
        """Remove a notification listener"""
        if callback in self.listeners:
            self.listeners.remove(callback)
    
    def _notify_listeners(self, notification: Notification):
        """Notify all listeners of a new notification"""
        for listener in self.listeners:
            try:
                listener(notification)
            except Exception as e:
                logger.error(f"Error in notification listener: {str(e)}")
    
    def _play_notification_sound(self, level: NotificationLevel):
        """Play a sound for the notification - implemented in UI layer"""
        pass
    
    def enable_audio(self, enabled: bool = True):
        """Enable or disable notification sounds"""
        self.audio_enabled = enabled

# Global notification manager instance
notification_manager = NotificationManager()
