"""
EDGE SERVICE - Production Ready
================================

Edge = топ opportunities по impact от Meta Brain influence
НЕ статичные данные!
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timezone
from pymongo import MongoClient
import os
import logging

logger = logging.getLogger(__name__)

# MongoDB connection for subscription expiry check
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")
mongo_client = MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]

META_BRAIN_URL = "http://localhost:8003/api/meta-brain-v2"


def check_and_expire_subscription(user: dict) -> dict:
    """
    Check if user's PRO subscription has expired and revert to FREE if needed.
    
    Args:
        user: User document from MongoDB
    
    Returns:
        Updated user dict with current plan status
    """
    if not user:
        return user
    
    # Only check if user has PRO plan
    if user.get("plan") != "PRO":
        return user
    
    # Check if expiresAt exists and is in the past
    expires_at = user.get("expiresAt")
    if expires_at:
        now = datetime.now(timezone.utc)
        
        # Handle both aware and naive datetimes
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < now:
            # Subscription expired - revert to FREE
            logger.info(f"Subscription expired for user {user.get('_id')}. Reverting to FREE plan.")
            
            db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "plan": "FREE",
                    "planStatus": "EXPIRED",
                    "expiresAt": None
                }}
            )
            
            # Update local user object
            user["plan"] = "FREE"
            user["planStatus"] = "EXPIRED"
            user["expiresAt"] = None
    
    return user


def get_edge(asset: str, user: dict = None) -> List[Dict[str, Any]] | Dict[str, Any]:
    """
    🔥 EDGE = influence от Meta Brain
    
    🔒 PAYWALL: Полностью платная функция
    FREE пользователи видят только preview
    
    Сортируем модули по impact - это и есть opportunities
    """
    # ✅ CRITICAL: Check subscription expiry before evaluating plan
    if user:
        user = check_and_expire_subscription(user)
    
    # 🔒 CHECK PRO ACCESS
    is_pro = False
    if user:
        is_pro = user.get("plan") == "PRO" or user.get("subscription", {}).get("plan") == "PRO"
    
    if not is_pro:
        # Return locked state for FREE users
        return {
            "locked": True,
            "preview": "Unlock Market Intelligence",
            "description": "See what's driving the market. Upgrade to PRO to access real-time module influence and hidden opportunities.",
            "plan": user.get("plan", "FREE") if user else "FREE"
        }
    
    # PRO users get full data
    try:
        res = requests.get(
            f"{META_BRAIN_URL}/influence",
            params={"asset": asset},
            timeout=3
        )
        res.raise_for_status()
        
        data = res.json()
        modules = data.get("contributors", [])
        
        # Сортируем по impact (самые сильные = edge opportunities)
        sorted_modules = sorted(
            modules,
            key=lambda x: abs(x.get("impact", 0)),
            reverse=True
        )
        
        # Конвертируем в edge format для mobile
        edges = []
        for mod in sorted_modules[:10]:  # Top 10
            edges.append({
                "module": mod.get("module"),
                "signal": mod.get("signal"),
                "weight": mod.get("weight"),
                "impact": mod.get("impact"),
                "pctImpact": mod.get("pctImpact"),
                "confidence": data.get("confidence", 0.5),
                "direction": "LONG" if mod.get("signal", 0) > 0 else "SHORT",
            })
        
        print(f"[Edge] {asset}: {len(edges)} opportunities (PRO access)")
        return edges
        
    except Exception as e:
        print(f"[Edge] Error for {asset}: {e}")
        return []


def get_edge_detailed(asset: str) -> Dict[str, Any]:
    """
    Edge + regime + performance для детального view
    """
    try:
        influence_res = requests.get(
            f"{META_BRAIN_URL}/influence",
            params={"asset": asset},
            timeout=3
        )
        
        performance_res = requests.get(
            f"{META_BRAIN_URL}/performance",
            timeout=3
        )
        
        return {
            "opportunities": get_edge(asset),
            "regime": influence_res.json().get("regime", "UNKNOWN") if influence_res.ok else "UNKNOWN",
            "performance": performance_res.json() if performance_res.ok else {},
        }
        
    except Exception as e:
        print(f"[Edge Detailed] Error: {e}")
        return {
            "opportunities": [],
            "regime": "UNKNOWN",
            "performance": {},
        }
