"""
AI Interaction Logging Service.

Provides audit trail for all AI-related interactions including:
- Search queries
- Decision reads
- AI-assisted creation
- Summarization requests
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from models import db, AIInteractionLog, AIChannel, AIAction, User, Tenant


class AIInteractionLogger:
    """Service for logging AI interactions."""

    @staticmethod
    def log_interaction(
        channel: AIChannel,
        action: AIAction,
        tenant_id: int,
        user_id: Optional[int] = None,
        query_text: Optional[str] = None,
        decision_ids: Optional[List[int]] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> AIInteractionLog:
        """
        Log an AI interaction.

        Args:
            channel: The channel (slack, mcp, api, web)
            action: The action type (search, read, create, etc.)
            tenant_id: The tenant context
            user_id: The user performing the action (if known)
            query_text: The query text (should be anonymized if required)
            decision_ids: IDs of decisions accessed
            llm_provider: The LLM provider used (if any)
            llm_model: The specific model used
            tokens_input: Input tokens consumed
            tokens_output: Output tokens generated
            duration_ms: Duration of the operation in milliseconds

        Returns:
            The created log entry
        """
        log_entry = AIInteractionLog(
            channel=channel,
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=query_text,
            decision_ids=decision_ids or [],
            llm_provider=llm_provider,
            llm_model=llm_model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms
        )

        db.session.add(log_entry)
        db.session.commit()

        return log_entry

    @staticmethod
    def log_search(
        channel: AIChannel,
        tenant_id: int,
        query_text: str,
        decision_ids: List[int],
        user_id: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> AIInteractionLog:
        """Convenience method to log a search interaction."""
        return AIInteractionLogger.log_interaction(
            channel=channel,
            action=AIAction.SEARCH,
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=query_text,
            decision_ids=decision_ids,
            duration_ms=duration_ms
        )

    @staticmethod
    def log_read(
        channel: AIChannel,
        tenant_id: int,
        decision_id: int,
        user_id: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> AIInteractionLog:
        """Convenience method to log a read interaction."""
        return AIInteractionLogger.log_interaction(
            channel=channel,
            action=AIAction.READ,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_ids=[decision_id],
            duration_ms=duration_ms
        )

    @staticmethod
    def log_create(
        channel: AIChannel,
        tenant_id: int,
        decision_id: int,
        user_id: Optional[int] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> AIInteractionLog:
        """Convenience method to log a create interaction."""
        return AIInteractionLogger.log_interaction(
            channel=channel,
            action=AIAction.CREATE,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_ids=[decision_id],
            llm_provider=llm_provider,
            llm_model=llm_model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms
        )

    @staticmethod
    def log_summarize(
        channel: AIChannel,
        tenant_id: int,
        decision_id: int,
        user_id: Optional[int] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> AIInteractionLog:
        """Convenience method to log a summarize interaction."""
        return AIInteractionLogger.log_interaction(
            channel=channel,
            action=AIAction.SUMMARIZE,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_ids=[decision_id],
            llm_provider=llm_provider,
            llm_model=llm_model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    @staticmethod
    def get_tenant_logs(
        tenant_id: int,
        limit: int = 100,
        offset: int = 0,
        channel: Optional[AIChannel] = None,
        action: Optional[AIAction] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AIInteractionLog]:
        """
        Get AI interaction logs for a tenant.

        Args:
            tenant_id: The tenant to query
            limit: Maximum number of results
            offset: Number of results to skip
            channel: Filter by channel
            action: Filter by action type
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of log entries
        """
        query = AIInteractionLog.query.filter_by(tenant_id=tenant_id)

        if channel:
            query = query.filter(AIInteractionLog.channel == channel)
        if action:
            query = query.filter(AIInteractionLog.action == action)
        if start_date:
            query = query.filter(AIInteractionLog.created_at >= start_date)
        if end_date:
            query = query.filter(AIInteractionLog.created_at <= end_date)

        return query.order_by(AIInteractionLog.created_at.desc()) \
                    .offset(offset).limit(limit).all()

    @staticmethod
    def get_user_logs(
        user_id: int,
        tenant_id: int,
        limit: int = 100
    ) -> List[AIInteractionLog]:
        """Get AI interaction logs for a specific user."""
        return AIInteractionLog.query.filter_by(
            user_id=user_id,
            tenant_id=tenant_id
        ).order_by(AIInteractionLog.created_at.desc()).limit(limit).all()

    # =========================================================================
    # Analytics Methods
    # =========================================================================

    @staticmethod
    def get_tenant_stats(
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get AI usage statistics for a tenant.

        Args:
            tenant_id: The tenant to query
            start_date: Start of period (default: 30 days ago)
            end_date: End of period (default: now)

        Returns:
            Dictionary with usage statistics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        logs = AIInteractionLog.query.filter(
            AIInteractionLog.tenant_id == tenant_id,
            AIInteractionLog.created_at >= start_date,
            AIInteractionLog.created_at <= end_date
        ).all()

        # Calculate stats
        total_interactions = len(logs)
        by_channel = {}
        by_action = {}
        total_tokens_input = 0
        total_tokens_output = 0
        unique_users = set()

        for log in logs:
            # Count by channel
            channel_key = log.channel.value if log.channel else 'unknown'
            by_channel[channel_key] = by_channel.get(channel_key, 0) + 1

            # Count by action
            action_key = log.action.value if log.action else 'unknown'
            by_action[action_key] = by_action.get(action_key, 0) + 1

            # Sum tokens
            if log.tokens_input:
                total_tokens_input += log.tokens_input
            if log.tokens_output:
                total_tokens_output += log.tokens_output

            # Track unique users
            if log.user_id:
                unique_users.add(log.user_id)

        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'total_interactions': total_interactions,
            'unique_users': len(unique_users),
            'by_channel': by_channel,
            'by_action': by_action,
            'total_tokens_input': total_tokens_input,
            'total_tokens_output': total_tokens_output,
            'total_tokens': total_tokens_input + total_tokens_output,
        }

    @staticmethod
    def serialize_log(log: AIInteractionLog) -> Dict[str, Any]:
        """Serialize a log entry for API response."""
        return {
            'id': str(log.id),
            'channel': log.channel.value if log.channel else None,
            'action': log.action.value if log.action else None,
            'user_id': log.user_id,
            'query_text': log.query_text,
            'decision_ids': log.decision_ids,
            'llm_provider': log.llm_provider,
            'llm_model': log.llm_model,
            'tokens_input': log.tokens_input,
            'tokens_output': log.tokens_output,
            'duration_ms': log.duration_ms,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        }

    # =========================================================================
    # Cleanup Methods
    # =========================================================================

    @staticmethod
    def cleanup_old_logs(days: int = 90) -> int:
        """
        Delete logs older than the specified number of days.

        Args:
            days: Number of days to retain

        Returns:
            Number of logs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = AIInteractionLog.query.filter(
            AIInteractionLog.created_at < cutoff
        ).delete()
        db.session.commit()
        return result
