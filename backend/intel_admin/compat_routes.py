"""
Admin API Keys/LLM/Sentiment routes at /api/admin/ prefix
(Mirrors intel_admin routes for frontend compatibility)
"""
from fastapi import APIRouter
from intel_admin.routes import (
    get_api_keys, get_api_key_services, get_api_keys_summary,
    add_api_key, remove_api_key, toggle_api_key, check_api_key_health, check_all_keys_health,
    get_llm_keys, get_llm_providers, get_llm_keys_summary,
    add_llm_key, remove_llm_key, toggle_llm_key, test_llm_key,
    set_llm_key_default, reset_llm_key_health,
    get_llm_analytics_overview, get_llm_analytics_by_provider, get_llm_analytics_hourly,
    get_sentiment_keys, get_sentiment_keys_summary, add_sentiment_key,
    remove_sentiment_key, toggle_sentiment_key, get_sentiment_providers,
    get_providers, get_provider_stats,
    AddApiKeyRequest, AddLlmKeyRequest, AddSentimentKeyRequest
)
from fastapi import Body

router = APIRouter(prefix="/api/admin", tags=["Admin Compat"])

# API Keys
router.add_api_route("/api-keys", get_api_keys, methods=["GET"])
router.add_api_route("/api-keys/services", get_api_key_services, methods=["GET"])
router.add_api_route("/api-keys/summary", get_api_keys_summary, methods=["GET"])
router.add_api_route("/api-keys", add_api_key, methods=["POST"])
router.add_api_route("/api-keys/{key_id}", remove_api_key, methods=["DELETE"])
router.add_api_route("/api-keys/{key_id}/toggle", toggle_api_key, methods=["POST"])
router.add_api_route("/api-keys/{key_id}/health", check_api_key_health, methods=["POST"])
router.add_api_route("/api-keys/health/all", check_all_keys_health, methods=["POST"])

# LLM Keys
router.add_api_route("/llm-keys", get_llm_keys, methods=["GET"])
router.add_api_route("/llm-keys/providers", get_llm_providers, methods=["GET"])
router.add_api_route("/llm-keys/summary", get_llm_keys_summary, methods=["GET"])
router.add_api_route("/llm-keys", add_llm_key, methods=["POST"])
router.add_api_route("/llm-keys/{key_id}", remove_llm_key, methods=["DELETE"])
router.add_api_route("/llm-keys/{key_id}/toggle", toggle_llm_key, methods=["POST"])
router.add_api_route("/llm-keys/{key_id}/test", test_llm_key, methods=["POST"])
router.add_api_route("/llm-keys/{key_id}/set-default", set_llm_key_default, methods=["POST"])
router.add_api_route("/llm-keys/{key_id}/reset-health", reset_llm_key_health, methods=["POST"])
router.add_api_route("/llm-keys/analytics/overview", get_llm_analytics_overview, methods=["GET"])
router.add_api_route("/llm-keys/analytics/by-provider", get_llm_analytics_by_provider, methods=["GET"])
router.add_api_route("/llm-keys/analytics/hourly", get_llm_analytics_hourly, methods=["GET"])

# Sentiment Keys
router.add_api_route("/sentiment-keys", get_sentiment_keys, methods=["GET"])
router.add_api_route("/sentiment-keys/summary", get_sentiment_keys_summary, methods=["GET"])
router.add_api_route("/sentiment-keys", add_sentiment_key, methods=["POST"])
router.add_api_route("/sentiment-keys/{key_id}", remove_sentiment_key, methods=["DELETE"])
router.add_api_route("/sentiment-keys/{key_id}/toggle", toggle_sentiment_key, methods=["POST"])
