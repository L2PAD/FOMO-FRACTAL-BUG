"""
Article Validation Layer
========================

Validates parsed articles to detect parser drift and data quality issues.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Validation configuration."""
    min_title_length: int = 10
    max_title_length: int = 500
    min_content_length: int = 100
    max_content_length: int = 50000
    max_future_date_hours: int = 24
    max_past_date_days: int = 30


@dataclass
class ValidationResult:
    """Result of article validation."""
    is_valid: bool
    confidence: float
    issues: List[str]
    warnings: List[str]


# Spam/Ad patterns
SPAM_PATTERNS = [
    r'subscribe to newsletter',
    r'cookie policy',
    r'privacy policy',
    r'terms of service',
    r'advertisement',
    r'sponsored content',
    r'click here to',
    r'sign up for free',
    r'promotional offer',
    r'limited time only',
    r'act now',
    r'don\'t miss out',
]

SPAM_REGEX = re.compile('|'.join(SPAM_PATTERNS), re.IGNORECASE)


class ArticleValidator:
    """Validates articles for quality and parser drift detection."""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.source_stats: Dict[str, Dict] = {}
    
    def validate(self, article: Dict[str, Any]) -> ValidationResult:
        """
        Validate article data quality.
        
        Returns ValidationResult with:
        - is_valid: bool
        - confidence: 0.0-1.0
        - issues: list of blocking issues
        - warnings: list of non-blocking warnings
        """
        issues = []
        warnings = []
        scores = []
        
        # 1. Validate title
        title_score, title_issues, title_warnings = self._validate_title(article)
        scores.append(title_score)
        issues.extend(title_issues)
        warnings.extend(title_warnings)
        
        # 2. Validate content
        content_score, content_issues, content_warnings = self._validate_content(article)
        scores.append(content_score)
        issues.extend(content_issues)
        warnings.extend(content_warnings)
        
        # 3. Validate date
        date_score, date_issues, date_warnings = self._validate_date(article)
        scores.append(date_score)
        issues.extend(date_issues)
        warnings.extend(date_warnings)
        
        # 4. Validate URL
        url_score, url_issues, url_warnings = self._validate_url(article)
        scores.append(url_score)
        issues.extend(url_issues)
        warnings.extend(url_warnings)
        
        # 5. Check for spam/ad content
        spam_score, spam_issues, spam_warnings = self._check_spam(article)
        scores.append(spam_score)
        issues.extend(spam_issues)
        warnings.extend(spam_warnings)
        
        # Calculate overall confidence
        confidence = sum(scores) / len(scores) if scores else 0.0
        
        # Article is valid if no blocking issues and confidence above threshold
        is_valid = len(issues) == 0 and confidence >= 0.5
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=round(confidence, 3),
            issues=issues,
            warnings=warnings
        )
    
    def _validate_title(self, article: Dict) -> Tuple[float, List[str], List[str]]:
        """Validate article title."""
        issues = []
        warnings = []
        
        title = article.get("title_raw") or article.get("title", "")
        
        if not title:
            return 0.0, ["Missing title"], []
        
        title_len = len(title.strip())
        
        if title_len < self.config.min_title_length:
            return 0.2, [f"Title too short ({title_len} chars)"], []
        
        if title_len > self.config.max_title_length:
            warnings.append(f"Title very long ({title_len} chars)")
            return 0.8, [], warnings
        
        # Check for suspicious patterns
        if title.isupper():
            warnings.append("Title is all uppercase")
        
        if title.count('!') > 2:
            warnings.append("Title has excessive punctuation")
        
        score = 1.0
        if warnings:
            score = 0.9
        
        return score, issues, warnings
    
    def _validate_content(self, article: Dict) -> Tuple[float, List[str], List[str]]:
        """Validate article content."""
        issues = []
        warnings = []
        
        content = article.get("content_raw") or article.get("content", "")
        
        if not content:
            return 0.3, [], ["Missing content (only title available)"]
        
        content_len = len(content.strip())
        
        if content_len < self.config.min_content_length:
            return 0.5, [], [f"Content short ({content_len} chars)"]
        
        if content_len > self.config.max_content_length:
            warnings.append(f"Content very long ({content_len} chars)")
        
        # Check content diversity (not just repeated text)
        words = content.lower().split()
        unique_words = set(words)
        
        if len(words) > 50 and len(unique_words) / len(words) < 0.3:
            warnings.append("Low word diversity (possible duplicate content)")
            return 0.7, [], warnings
        
        return 1.0, issues, warnings
    
    def _validate_date(self, article: Dict) -> Tuple[float, List[str], List[str]]:
        """Validate article date."""
        issues = []
        warnings = []
        
        date_raw = article.get("published_at_raw") or article.get("published_at")
        
        if not date_raw:
            return 0.7, [], ["Missing publication date"]
        
        try:
            # Try to parse date
            if isinstance(date_raw, str):
                # Handle various formats
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S %Z",
                ]:
                    try:
                        dt = datetime.strptime(date_raw, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Could not parse
                    return 0.6, [], ["Could not parse date format"]
            elif isinstance(date_raw, datetime):
                dt = date_raw
            else:
                return 0.5, [], ["Invalid date type"]
            
            # Make timezone aware if needed
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            
            # Check future date
            max_future = now + timedelta(hours=self.config.max_future_date_hours)
            if dt > max_future:
                return 0.3, [f"Date is in future: {dt}"], []
            
            # Check very old date
            max_past = now - timedelta(days=self.config.max_past_date_days)
            if dt < max_past:
                warnings.append(f"Article is old ({(now - dt).days} days)")
                return 0.8, [], warnings
            
            return 1.0, issues, warnings
            
        except Exception as e:
            return 0.5, [], [f"Date validation error: {str(e)}"]
    
    def _validate_url(self, article: Dict) -> Tuple[float, List[str], List[str]]:
        """Validate article URL."""
        url = article.get("url") or article.get("canonical_url", "")
        
        if not url:
            return 0.3, ["Missing URL"], []
        
        if not url.startswith(("http://", "https://")):
            return 0.5, ["Invalid URL format"], []
        
        # Check for tracking parameters (not blocking, just warning)
        warnings = []
        if "utm_" in url or "ref=" in url:
            warnings.append("URL contains tracking parameters")
        
        return 1.0, [], warnings
    
    def _check_spam(self, article: Dict) -> Tuple[float, List[str], List[str]]:
        """Check for spam/advertisement content."""
        title = article.get("title_raw") or article.get("title", "")
        content = article.get("content_raw") or article.get("content", "")
        
        full_text = f"{title} {content}".lower()
        
        spam_matches = SPAM_REGEX.findall(full_text)
        
        if len(spam_matches) > 3:
            return 0.3, ["High spam/ad content detected"], []
        elif len(spam_matches) > 0:
            return 0.8, [], [f"Some spam patterns detected: {spam_matches[:2]}"]
        
        return 1.0, [], []
    
    def update_source_stats(self, source_id: str, validation_result: ValidationResult):
        """Track validation statistics per source."""
        if source_id not in self.source_stats:
            self.source_stats[source_id] = {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "avg_confidence": 0.0,
                "common_issues": {}
            }
        
        stats = self.source_stats[source_id]
        stats["total"] += 1
        
        if validation_result.is_valid:
            stats["valid"] += 1
        else:
            stats["invalid"] += 1
        
        # Update average confidence (rolling)
        n = stats["total"]
        stats["avg_confidence"] = (
            (stats["avg_confidence"] * (n - 1) + validation_result.confidence) / n
        )
        
        # Track common issues
        for issue in validation_result.issues:
            if issue not in stats["common_issues"]:
                stats["common_issues"][issue] = 0
            stats["common_issues"][issue] += 1
    
    def get_source_validation_health(self, source_id: str) -> Dict[str, Any]:
        """Get validation health for source."""
        if source_id not in self.source_stats:
            return {"source_id": source_id, "status": "no_data"}
        
        stats = self.source_stats[source_id]
        valid_rate = stats["valid"] / stats["total"] if stats["total"] > 0 else 0
        
        status = "healthy"
        if valid_rate < 0.5:
            status = "critical"
        elif valid_rate < 0.7:
            status = "unhealthy"
        elif valid_rate < 0.9:
            status = "degraded"
        
        return {
            "source_id": source_id,
            "valid_rate": round(valid_rate, 3),
            "avg_confidence": round(stats["avg_confidence"], 3),
            "total_articles": stats["total"],
            "valid_articles": stats["valid"],
            "invalid_articles": stats["invalid"],
            "common_issues": dict(sorted(
                stats["common_issues"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]),
            "status": status
        }
    
    def detect_parser_drift(self, source_id: str) -> bool:
        """
        Detect if parser might be drifting (returning bad data).
        
        Returns True if drift detected.
        """
        if source_id not in self.source_stats:
            return False
        
        stats = self.source_stats[source_id]
        
        # Need enough samples
        if stats["total"] < 10:
            return False
        
        # Check recent validation rate
        valid_rate = stats["valid"] / stats["total"]
        
        # Parser drift if validation rate drops below threshold
        if valid_rate < 0.5:
            logger.warning(f"[Validator] Parser drift detected for {source_id}: valid_rate={valid_rate:.2%}")
            return True
        
        # Check if confidence is consistently low
        if stats["avg_confidence"] < 0.6:
            logger.warning(f"[Validator] Low confidence for {source_id}: avg={stats['avg_confidence']:.2%}")
            return True
        
        return False


# Global validator instance
_validator: Optional[ArticleValidator] = None


def get_validator() -> ArticleValidator:
    """Get global validator instance."""
    global _validator
    if _validator is None:
        _validator = ArticleValidator()
    return _validator
