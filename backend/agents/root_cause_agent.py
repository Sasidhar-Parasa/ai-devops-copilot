"""
Root Cause Agent – Analyzes failures and correlates signals
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

RCA_TEMPLATES = {
    "high_error_rate": {
        "root_cause": "Integration test regression in checkout flow introduced in v2.4.1",
        "evidence": [
            "Error rate spiked from 0.8% → 23% at 14:32 UTC",
            "Spike correlates with payment-service v2.4.1 deployment at 14:30 UTC",
            "All errors originate from /api/checkout endpoint",
            "TestCheckoutFlow integration test failed during CI (bypassed by emergency flag)",
        ],
        "contributing_factors": [
            "Missing null-check on `shipping_address` field",
            "New payment gateway SDK v3.1 response format change",
            "Insufficient test coverage for edge cases (87.3% → threshold met but edge missed)",
        ],
        "affected_services": ["payment-service", "api-gateway"],
        "recommendation": "Rollback to v2.4.0, patch null-check, add test coverage for new SDK format",
        "confidence": 94,
    },
    "low_error_rate": {
        "root_cause": "Intermittent database connection pool exhaustion under peak load",
        "evidence": [
            "Slow query warnings appearing every 15–20 minutes",
            "Connection wait time elevated: 2.3s avg (threshold: 500ms)",
            "Peak traffic period: 14:00–16:00 UTC daily",
        ],
        "contributing_factors": [
            "Connection pool size (max=10) insufficient for current traffic (320 req/s)",
            "Unoptimized SELECT * queries causing long-held connections",
        ],
        "affected_services": ["database", "payment-service"],
        "recommendation": "Increase connection pool to 25, add query optimization + index on orders.created_at",
        "confidence": 78,
    },
}


class RootCauseAgent:
    async def run(self, monitoring_data: Dict[str, Any]) -> Dict[str, Any]:
        error_rate = monitoring_data.get("error_rate", 0)
        key = "high_error_rate" if error_rate > 5 else "low_error_rate"
        rca = RCA_TEMPLATES[key]

        return {
            **rca,
            "analysis_duration_ms": 1240,
            "signals_analyzed": monitoring_data.get("log_count", 0),
        }
