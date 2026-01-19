"""
Simple IP-based rate limiter
"""

from datetime import datetime, timedelta
from collections import defaultdict

# In-memory storage (for MVP)
query_log = defaultdict(list)

def check_rate_limit(ip_address, limit=10):
    """Check if IP has exceeded daily limit"""
    
    # Clean old entries (older than 24 hours)
    cutoff = datetime.now() - timedelta(days=1)
    query_log[ip_address] = [
        timestamp for timestamp in query_log[ip_address]
        if timestamp > cutoff
    ]
    
    # Check limit
    queries_today = len(query_log[ip_address])
    
    if queries_today >= limit:
        return {
            "allowed": False,
            "queries_remaining": 0,
            "queries_today": queries_today
        }
    
    # Log this query
    query_log[ip_address].append(datetime.now())
    
    return {
        "allowed": True,
        "queries_remaining": limit - queries_today - 1,
        "queries_today": queries_today + 1
    }
