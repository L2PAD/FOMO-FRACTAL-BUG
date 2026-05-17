"""
Twitter Ingestion Stack — L0/L1/L2/L3 unified pipeline.
Re-exports legacy functions for backwards compatibility.
"""
from twitter_ingestion_legacy import (
    check_parser_health,
    search_tweets,
    ingest_actor_tweets,
    ingest_search,
    mass_ingest_actors,
    get_ingestion_status,
)
