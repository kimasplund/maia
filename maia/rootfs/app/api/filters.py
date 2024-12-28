from datetime import datetime
from typing import Union

def format_datetime(value: Union[datetime, str]) -> str:
    """Format a datetime object or string into a human-readable format."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    
    if not isinstance(value, datetime):
        return str(value)
    
    now = datetime.now(value.tzinfo)
    delta = now - value
    
    if delta.days == 0:
        if delta.seconds < 60:
            return "just now"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days == 1:
        return "yesterday"
    elif delta.days < 7:
        return f"{delta.days} days ago"
    else:
        return value.strftime("%B %d, %Y at %I:%M %p") 