"""
Crypto Intelligence Operating System — Core Enums
"""
from enum import Enum


class SourceTier(str, Enum):
    CORE = "CORE"
    EXTENSION = "EXTENSION"
    AUX = "AUX"


class SourceDomain(str, Enum):
    FUNDING = "FUNDING"
    PROJECTS = "PROJECTS"
    ICO = "ICO"
    ACTIVITIES = "ACTIVITIES"
    UNLOCKS = "UNLOCKS"
    NEWS = "NEWS"


class SourceMethod(str, Enum):
    API = "API"
    XHR = "XHR"
    HTML = "HTML"
    BROWSER = "BROWSER"
    RSS = "RSS"


class EntityType(str, Enum):
    PROJECT = "project"
    FUND = "fund"
    INVESTOR = "investor"
    PERSON = "person"
    TOKEN = "token"
    EVENT = "event"


class EventType(str, Enum):
    FUNDING_ROUND = "funding_round"
    UNLOCK = "unlock"
    ACTIVITY = "activity"
    ICO = "ico"
    NEWS = "news_event"


class CanonicalStatus(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"
    DEPRECATED = "deprecated"
