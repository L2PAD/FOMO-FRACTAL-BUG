"""
Raw Layer — Collection schemas and constants
=============================================
All raw collections in one place. Single source of truth.
"""

RAW_COLLECTIONS = {
    "funding": "raw_funding",
    "projects": "raw_projects",
    "ico": "raw_ico",
    "activities": "raw_activities",
    "unlocks": "raw_unlocks",
    "news": "raw_news",
    "market_data": "raw_market_data",
}

CANONICAL_COLLECTIONS = {
    "projects": "canonical_projects",
    "funds": "canonical_funds",
    "persons": "canonical_persons",
    "tokens": "canonical_tokens",
    "events": "canonical_events",
}

REQUIRED_RAW_FIELDS = {
    "raw_funding": ["source", "name", "symbol", "fetched_at"],
    "raw_projects": ["source", "name", "fetched_at"],
    "raw_ico": ["source", "project_name", "fetched_at"],
    "raw_activities": ["source", "project_name", "fetched_at"],
    "raw_unlocks": ["source", "project_name", "fetched_at"],
    "raw_news": ["source", "title", "fetched_at"],
    "raw_market_data": ["source", "name", "symbol", "fetched_at"],
}
