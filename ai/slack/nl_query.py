"""
Natural Language Query Processing for Slack AI Bot.

Handles parsing of natural language queries into structured search parameters.
"""

import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class QueryIntent:
    """Represents the intent of a natural language query."""
    SEARCH = 'search'
    SUMMARIZE = 'summarize'
    EXPLAIN = 'explain'
    LIST = 'list'
    GET = 'get'


class NLQueryParser:
    """
    Parse natural language queries into structured search parameters.

    This parser uses pattern matching and keyword extraction to understand
    user intent without requiring an LLM (keeping it fast and privacy-friendly).
    """

    # Intent detection patterns
    INTENT_PATTERNS = {
        QueryIntent.SUMMARIZE: [
            r'\bsummariz[e|es|ing]\b',
            r'\bsummary\b',
            r'\btl;?dr\b',
            r'\bbrief\b',
            r'\bquick overview\b',
        ],
        QueryIntent.EXPLAIN: [
            r'\bexplain\b',
            r'\bwhy did we\b',
            r'\breason for\b',
            r'\bconsequences? of\b',
            r'\bimpact of\b',
        ],
        QueryIntent.LIST: [
            r'\blist\b',
            r'\bshow (me |all )?decisions?\b',
            r'\bwhat decisions?\b',
            r'\brecent decisions?\b',
        ],
        QueryIntent.GET: [
            r'\bget\b',
            r'\bshow\s+(adr-?\d+|decision\s*#?\d+)\b',
            r'\bview\b',
        ],
    }

    # Status keywords
    STATUS_KEYWORDS = {
        'proposed': ['proposed', 'pending', 'draft', 'under review', 'considering'],
        'accepted': ['accepted', 'approved', 'active', 'current', 'in effect'],
        'archived': ['archived', 'old', 'deprecated', 'retired', 'inactive'],
        'superseded': ['superseded', 'replaced', 'outdated', 'obsolete'],
    }

    # Time range patterns
    TIME_PATTERNS = [
        (r'\blast\s+(\d+)\s+days?\b', lambda m: timedelta(days=int(m.group(1)))),
        (r'\blast\s+(\d+)\s+weeks?\b', lambda m: timedelta(weeks=int(m.group(1)))),
        (r'\blast\s+(\d+)\s+months?\b', lambda m: timedelta(days=int(m.group(1)) * 30)),
        (r'\brecent\b', lambda m: timedelta(days=30)),
        (r'\btoday\b', lambda m: timedelta(days=1)),
        (r'\bthis week\b', lambda m: timedelta(days=7)),
        (r'\bthis month\b', lambda m: timedelta(days=30)),
    ]

    # Decision ID patterns
    DECISION_ID_PATTERNS = [
        r'\b(adr-?\d+)\b',
        r'\bdecision\s*#?(\d+)\b',
        r'\b#(\d+)\b',
    ]

    @classmethod
    def parse(cls, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured parameters.

        Args:
            query: The natural language query string

        Returns:
            Dictionary with:
            - intent: The detected intent (search, summarize, explain, list, get)
            - keywords: List of extracted keywords for search
            - status: Status filter (if detected)
            - time_range: Tuple of (start_date, end_date) if time filter detected
            - decision_id: Specific decision ID if referenced
            - original_query: The original query string
        """
        query_lower = query.lower().strip()

        result = {
            'intent': QueryIntent.SEARCH,  # Default intent
            'keywords': [],
            'status': None,
            'time_range': None,
            'decision_id': None,
            'original_query': query,
        }

        # Detect intent
        result['intent'] = cls._detect_intent(query_lower)

        # Extract decision ID
        result['decision_id'] = cls._extract_decision_id(query_lower)

        # If we found a decision ID, likely a get/summarize/explain intent
        if result['decision_id'] and result['intent'] == QueryIntent.SEARCH:
            result['intent'] = QueryIntent.GET

        # Extract status filter
        result['status'] = cls._extract_status(query_lower)

        # Extract time range
        result['time_range'] = cls._extract_time_range(query_lower)

        # Extract keywords (remove noise words and detected patterns)
        result['keywords'] = cls._extract_keywords(query_lower)

        return result

    @classmethod
    def _detect_intent(cls, query: str) -> str:
        """Detect the intent of the query."""
        for intent, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return intent
        return QueryIntent.SEARCH

    @classmethod
    def _extract_decision_id(cls, query: str) -> Optional[str]:
        """Extract a decision ID from the query."""
        for pattern in cls.DECISION_ID_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Normalize to ADR-XXX format
                id_part = match.group(1)
                if id_part.lower().startswith('adr'):
                    # Already has ADR prefix
                    num = re.search(r'\d+', id_part).group()
                    return f'ADR-{num}'
                else:
                    return f'ADR-{id_part}'
        return None

    @classmethod
    def _extract_status(cls, query: str) -> Optional[str]:
        """Extract status filter from the query."""
        for status, keywords in cls.STATUS_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return status
        return None

    @classmethod
    def _extract_time_range(cls, query: str) -> Optional[tuple]:
        """Extract time range from the query."""
        now = datetime.utcnow()

        for pattern, delta_fn in cls.TIME_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                delta = delta_fn(match)
                start_date = now - delta
                return (start_date, now)

        return None

    @classmethod
    def _extract_keywords(cls, query: str) -> List[str]:
        """Extract meaningful keywords from the query."""
        # Remove common patterns we've already processed
        cleaned = query

        # Remove decision IDs
        for pattern in cls.DECISION_ID_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove time patterns
        for pattern, _ in cls.TIME_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove intent trigger words
        for patterns in cls.INTENT_PATTERNS.values():
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove status keywords
        for keywords in cls.STATUS_KEYWORDS.values():
            for keyword in keywords:
                cleaned = re.sub(r'\b' + re.escape(keyword) + r'\b', '', cleaned, flags=re.IGNORECASE)

        # Remove noise words
        noise_words = [
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'under', 'again', 'further', 'then',
            'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
            'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'just', 'but', 'and', 'or', 'if', 'because', 'as', 'until', 'while',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it',
            'they', 'them', 'his', 'her', 'its', 'their', 'decisions', 'decision',
            'made', 'make', 'find', 'show', 'me', 'please', 'about', 'regarding',
        ]

        # Split into words and filter
        words = cleaned.split()
        keywords = [
            word.strip('.,?!:;()[]{}"\'-')
            for word in words
            if len(word) > 2 and word.lower() not in noise_words
        ]

        return keywords


def format_search_query(parsed: Dict[str, Any]) -> str:
    """
    Format parsed query back into a simple search string for existing search.

    Args:
        parsed: The parsed query dictionary

    Returns:
        A search string combining the meaningful keywords
    """
    return ' '.join(parsed.get('keywords', []))


def build_search_filters(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build database query filters from parsed query.

    Args:
        parsed: The parsed query dictionary

    Returns:
        Dictionary of filter parameters
    """
    filters = {}

    if parsed.get('status'):
        filters['status'] = parsed['status']

    if parsed.get('time_range'):
        start, end = parsed['time_range']
        filters['created_after'] = start
        filters['created_before'] = end

    return filters
