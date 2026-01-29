import hashlib
from typing import Any, Dict, Optional
from src.core.feedback.schema import FeedbackItem, FeedbackRequest, FeedbackType
from src.core.feedback.store import FeedbackStore
from src.core.telemetry.metrics import MetricsCollector


class FeedbackService:
    def __init__(
        self,
        store: Optional[FeedbackStore] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        self.store = store or FeedbackStore()
        self.metrics = metrics_collector or MetricsCollector()

    def compute_signature(self, check_id: str, metadata: Dict[str, Any]) -> str:
        """
        Generates a deterministic signature for a finding.
        """
        key_parts = [str(check_id)]

        # Standardize metadata keys for signature
        # We prioritize: source, sink, file_path, line, context_hash

        if "source" in metadata:
            key_parts.append(f"source:{metadata['source']}")
        if "sink" in metadata:
            key_parts.append(f"sink:{metadata['sink']}")

        # If file_path is available, use it (relative to project root if possible)
        # Assuming metadata might have absolute paths, we might want to sanitize,
        # but for now rely on what's passed.
        if "file_path" in metadata:
            key_parts.append(f"file:{metadata['file_path']}")

        # Add line number if available for precision
        if "line" in metadata:
            key_parts.append(f"line:{metadata['line']}")

        raw_key = "|".join(key_parts)
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def add_feedback(self, request: FeedbackRequest) -> FeedbackItem:
        signature = self.compute_signature(request.check_id, request.metadata)
        item = FeedbackItem(
            id=signature,
            feedback_type=request.feedback_type,
            comment=request.comment,
            adjusted_score=request.adjusted_score,
        )
        self.store.set(item)

        # Track metrics if feedback is classification-related
        if request.feedback_type in [
            FeedbackType.TRUE_POSITIVE,
            FeedbackType.FALSE_POSITIVE,
        ]:
            self.metrics.track_feedback(request.feedback_type.value)

        return item

    def get_feedback(
        self, check_id: str, metadata: Dict[str, Any]
    ) -> Optional[FeedbackItem]:
        signature = self.compute_signature(check_id, metadata)
        return self.store.get(signature)
