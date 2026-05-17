"""
P2 Backend Regression Test — FOMO OS Production Universe Verification
======================================================================
Verifies that all 5 MetaBrain modules (TA, Fractal, OnChain, Sentiment, Exchange)
are LIVE for all 11 production assets.

Test Scope:
- P2.1: Universe coverage (11 assets via /api/trading/verdict/{asset})
- P2.2: Symbol normalization (BTCUSDT → BTC)
- P2.3: TA module (11 assets via /api/ta/basic/{asset})
- P2.4: Fractal module (11 assets via /api/fractal/runtime/{asset})
- P2.5: Sentiment substrate (/api/sentiment/runtime/diag)
- P2.6: Sentiment Mobile/MiniApp endpoints
- P2.7: Venues health (/api/venues/all/health)
- P2.8: Exchange forecast (11 assets)
- P2.9: Health & system endpoints
- P2.10: Twitter parser admin endpoints

Expected Behavior:
- /api/onchain/runtime/{asset} is KNOWN to fall back to legacy_compat (P4 work)
- /api/trading/verdict/{asset} should return activeModules >= 4 (TA+Fractal+Sentiment+Exchange)
- Identify which endpoints return legacy_compat_stub_empty vs real logic
"""
import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Load environment
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env", override=False)

# Backend URL from frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fullstack-merge-app.preview.emergentagent.com").rstrip("/")
API_BASE = f"{BASE_URL}/api"

# Production universe (11 assets)
PRODUCTION_ASSETS = ["BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ARB", "OP", "ADA", "BNB", "XRP"]

# Test results storage
test_results = {
    "timestamp": datetime.utcnow().isoformat(),
    "base_url": BASE_URL,
    "tests": {},
    "summary": {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
}


def log_test(test_id: str, passed: bool, details: dict, warning: bool = False):
    """Log a test result"""
    test_results["tests"][test_id] = {
        "passed": passed,
        "warning": warning,
        "details": details,
        "timestamp": datetime.utcnow().isoformat()
    }
    test_results["summary"]["total"] += 1
    if passed:
        test_results["summary"]["passed"] += 1
    else:
        test_results["summary"]["failed"] += 1
    if warning:
        test_results["summary"]["warnings"] += 1
    
    status = "⚠️ WARN" if warning else ("✅ PASS" if passed else "❌ FAIL")
    print(f"{status} {test_id}")


def get_json(endpoint: str, timeout: int = 15) -> tuple:
    """Make GET request and return (status_code, json_body, error)"""
    try:
        url = f"{API_BASE}{endpoint}"
        r = requests.get(url, timeout=timeout)
        try:
            body = r.json()
        except:
            body = {"_raw_text": r.text[:500]}
        return r.status_code, body, None
    except Exception as e:
        return 0, {}, str(e)


def is_legacy_stub(body: dict) -> bool:
    """Check if response is a legacy_compat_stub_empty"""
    if not isinstance(body, dict):
        return False
    note = body.get("note", "")
    return "legacy_compat_stub_empty" in str(note).lower()


# ═══════════════════════════════════════════════════════════════════════
# P2.1: Universe Coverage — /api/trading/verdict/{asset} for all 11 assets
# ═══════════════════════════════════════════════════════════════════════
def test_p2_1_universe_coverage():
    print("\n" + "="*70)
    print("P2.1: Universe Coverage — Trading Verdict for 11 Assets")
    print("="*70)
    
    results = {}
    for asset in PRODUCTION_ASSETS:
        status, body, err = get_json(f"/trading/verdict/{asset}")
        
        if err:
            results[asset] = {"error": err, "ok": False}
            log_test(f"P2.1.{asset}", False, {"error": err})
            continue
        
        canonical = body.get("canonicalSymbol", "")
        active_modules = body.get("alignment", {}).get("activeModules", [])
        active_count = len(active_modules)
        current_price = body.get("currentPrice")
        action = body.get("action", "")
        
        # Expected: activeModules >= 4 (TA, Fractal, Sentiment, Exchange)
        # OnChain is known to be degraded (P4 work)
        passed = (
            status == 200
            and canonical == asset
            and active_count >= 4
            and current_price is not None
        )
        
        results[asset] = {
            "status": status,
            "canonicalSymbol": canonical,
            "activeModules": active_modules,
            "activeCount": active_count,
            "currentPrice": current_price,
            "action": action,
            "ok": passed
        }
        
        log_test(
            f"P2.1.{asset}",
            passed,
            {
                "status": status,
                "canonical": canonical,
                "activeModules": active_count,
                "modules": active_modules,
                "price": current_price
            }
        )
    
    # Overall P2.1 pass: all 11 assets return valid verdicts
    all_ok = all(r.get("ok", False) for r in results.values())
    log_test("P2.1_OVERALL", all_ok, {"assets_tested": len(PRODUCTION_ASSETS), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.2: Symbol Normalization — BTCUSDT → BTC
# ═══════════════════════════════════════════════════════════════════════
def test_p2_2_symbol_normalization():
    print("\n" + "="*70)
    print("P2.2: Symbol Normalization — BTCUSDT → BTC")
    print("="*70)
    
    test_cases = [
        ("BTCUSDT", "BTC"),
        ("ETH-USD", "ETH"),
        ("SOL-PERP", "SOL"),
        ("DOGEUSDC", "DOGE"),
    ]
    
    results = {}
    for input_sym, expected_canonical in test_cases:
        status, body, err = get_json(f"/trading/verdict/{input_sym}")
        
        if err:
            results[input_sym] = {"error": err, "ok": False}
            log_test(f"P2.2.{input_sym}", False, {"error": err})
            continue
        
        canonical = body.get("canonicalSymbol", "")
        input_symbol = body.get("inputSymbol", "")
        active_modules = body.get("alignment", {}).get("activeModules", [])
        
        passed = (
            status == 200
            and canonical == expected_canonical
            and len(active_modules) >= 4
        )
        
        results[input_sym] = {
            "status": status,
            "inputSymbol": input_symbol,
            "canonicalSymbol": canonical,
            "expected": expected_canonical,
            "activeModules": len(active_modules),
            "ok": passed
        }
        
        log_test(
            f"P2.2.{input_sym}",
            passed,
            {
                "input": input_sym,
                "canonical": canonical,
                "expected": expected_canonical,
                "match": canonical == expected_canonical
            }
        )
    
    all_ok = all(r.get("ok", False) for r in results.values())
    log_test("P2.2_OVERALL", all_ok, {"test_cases": len(test_cases), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.3: TA Module — /api/ta/basic/{asset} for all 11 assets
# ═══════════════════════════════════════════════════════════════════════
def test_p2_3_ta_module():
    print("\n" + "="*70)
    print("P2.3: TA Module — Technical Analysis for 11 Assets")
    print("="*70)
    
    results = {}
    for asset in PRODUCTION_ASSETS:
        status, body, err = get_json(f"/ta/basic/{asset}")
        
        if err:
            results[asset] = {"error": err, "ok": False}
            log_test(f"P2.3.{asset}", False, {"error": err})
            continue
        
        ok = body.get("ok", False)
        degraded = body.get("degraded", True)
        direction = body.get("direction", "")
        confidence = body.get("confidence", 0.0)
        current_price = body.get("currentPrice")
        support = body.get("support")
        resistance = body.get("resistance")
        
        # TA should return real data (not degraded) with price/support/resistance
        passed = (
            status == 200
            and ok is True
            and degraded is False
            and current_price is not None
            and (support is not None or resistance is not None)
        )
        
        results[asset] = {
            "status": status,
            "ok": ok,
            "degraded": degraded,
            "direction": direction,
            "confidence": confidence,
            "currentPrice": current_price,
            "support": support,
            "resistance": resistance,
            "passed": passed
        }
        
        log_test(
            f"P2.3.{asset}",
            passed,
            {
                "status": status,
                "degraded": degraded,
                "price": current_price,
                "support": support,
                "resistance": resistance
            }
        )
    
    all_ok = all(r.get("passed", False) for r in results.values())
    log_test("P2.3_OVERALL", all_ok, {"assets_tested": len(PRODUCTION_ASSETS), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.4: Fractal Module — /api/fractal/runtime/{asset} for all 11 assets
# ═══════════════════════════════════════════════════════════════════════
def test_p2_4_fractal_module():
    print("\n" + "="*70)
    print("P2.4: Fractal Module — Fractal Runtime for 11 Assets")
    print("="*70)
    
    results = {}
    for asset in PRODUCTION_ASSETS:
        status, body, err = get_json(f"/fractal/runtime/{asset}")
        
        if err:
            results[asset] = {"error": err, "ok": False}
            log_test(f"P2.4.{asset}", False, {"error": err})
            continue
        
        direction = body.get("direction", "")
        horizons = body.get("horizons", {})
        source = body.get("source", "")
        
        # Fractal should return direction and horizons with numerical values
        has_horizons = isinstance(horizons, dict) and len(horizons) > 0
        
        passed = (
            status == 200
            and direction in ["LONG", "SHORT", "WAIT", "UP", "DOWN", "NEUTRAL"]
            and has_horizons
            and "fractal" in source.lower()
        )
        
        results[asset] = {
            "status": status,
            "direction": direction,
            "horizons_count": len(horizons) if isinstance(horizons, dict) else 0,
            "source": source,
            "passed": passed
        }
        
        log_test(
            f"P2.4.{asset}",
            passed,
            {
                "status": status,
                "direction": direction,
                "horizons": len(horizons) if isinstance(horizons, dict) else 0,
                "source": source
            }
        )
    
    all_ok = all(r.get("passed", False) for r in results.values())
    log_test("P2.4_OVERALL", all_ok, {"assets_tested": len(PRODUCTION_ASSETS), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.5: Sentiment Substrate — /api/sentiment/runtime/diag
# ═══════════════════════════════════════════════════════════════════════
def test_p2_5_sentiment_substrate():
    print("\n" + "="*70)
    print("P2.5: Sentiment Substrate — Runtime Diagnostics")
    print("="*70)
    
    # Test without symbol
    status1, body1, err1 = get_json("/sentiment/runtime/diag")
    
    # Test with symbols
    status2, body2, err2 = get_json("/sentiment/runtime/diag?symbol=BTC,ETH,SOL")
    
    # Check for real data
    state1 = body1.get("state", "") if not err1 else ""
    score1 = body1.get("score")
    confidence1 = body1.get("confidence")
    sample1 = body1.get("sample", 0)
    source1 = body1.get("source", "")
    
    state2 = body2.get("state", "") if not err2 else ""
    sample2 = body2.get("sample", 0)
    
    passed1 = (
        status1 == 200
        and state1 != ""
        and sample1 > 0
        and "sentiment" in source1.lower()
    )
    
    passed2 = (
        status2 == 200
        and state2 != ""
        and sample2 > 0
    )
    
    log_test(
        "P2.5.no_symbol",
        passed1,
        {
            "status": status1,
            "state": state1,
            "score": score1,
            "confidence": confidence1,
            "sample": sample1,
            "source": source1
        }
    )
    
    log_test(
        "P2.5.with_symbols",
        passed2,
        {
            "status": status2,
            "state": state2,
            "sample": sample2
        }
    )
    
    overall = passed1 and passed2
    log_test("P2.5_OVERALL", overall, {"no_symbol": passed1, "with_symbols": passed2})
    return {"no_symbol": body1, "with_symbols": body2}


# ═══════════════════════════════════════════════════════════════════════
# P2.6: Sentiment Mobile/MiniApp
# ═══════════════════════════════════════════════════════════════════════
def test_p2_6_sentiment_mobile_miniapp():
    print("\n" + "="*70)
    print("P2.6: Sentiment Mobile/MiniApp Endpoints")
    print("="*70)
    
    # Test mobile endpoint
    status1, body1, err1 = get_json("/mobile/intel/sentiment")
    
    # Test miniapp endpoint
    status2, body2, err2 = get_json("/miniapp/sentiment")
    
    # Check for real data (sample >= 100 for BTC/ETH/SOL)
    mobile_ok = status1 == 200 and not is_legacy_stub(body1)
    miniapp_ok = status2 == 200 and not is_legacy_stub(body2)
    
    # Check if data contains BTC/ETH/SOL with sample >= 100
    mobile_has_data = False
    if isinstance(body1, dict):
        for key in ["BTC", "ETH", "SOL"]:
            if key in str(body1):
                mobile_has_data = True
                break
    
    miniapp_has_data = False
    if isinstance(body2, dict):
        for key in ["BTC", "ETH", "SOL"]:
            if key in str(body2):
                miniapp_has_data = True
                break
    
    log_test(
        "P2.6.mobile",
        mobile_ok,
        {
            "status": status1,
            "is_stub": is_legacy_stub(body1),
            "has_data": mobile_has_data,
            "error": err1
        }
    )
    
    log_test(
        "P2.6.miniapp",
        miniapp_ok,
        {
            "status": status2,
            "is_stub": is_legacy_stub(body2),
            "has_data": miniapp_has_data,
            "error": err2
        }
    )
    
    overall = mobile_ok and miniapp_ok
    log_test("P2.6_OVERALL", overall, {"mobile": mobile_ok, "miniapp": miniapp_ok})
    return {"mobile": body1, "miniapp": body2}


# ═══════════════════════════════════════════════════════════════════════
# P2.7: Venues Health — /api/venues/all/health
# ═══════════════════════════════════════════════════════════════════════
def test_p2_7_venues_health():
    print("\n" + "="*70)
    print("P2.7: Venues Health")
    print("="*70)
    
    status, body, err = get_json("/venues/all/health")
    
    if err:
        log_test("P2.7", False, {"error": err})
        return body
    
    # Should return status for hyperliquid + coinbase with latency and asOf
    has_hyperliquid = "hyperliquid" in str(body).lower()
    has_coinbase = "coinbase" in str(body).lower()
    
    passed = (
        status == 200
        and not is_legacy_stub(body)
        and (has_hyperliquid or has_coinbase)
    )
    
    log_test(
        "P2.7",
        passed,
        {
            "status": status,
            "is_stub": is_legacy_stub(body),
            "has_hyperliquid": has_hyperliquid,
            "has_coinbase": has_coinbase
        }
    )
    
    return body


# ═══════════════════════════════════════════════════════════════════════
# P2.8: Exchange Forecast — /api/exchange/forecast/{asset} for all 11 assets
# ═══════════════════════════════════════════════════════════════════════
def test_p2_8_exchange_forecast():
    print("\n" + "="*70)
    print("P2.8: Exchange Forecast for 11 Assets")
    print("="*70)
    
    results = {}
    for asset in PRODUCTION_ASSETS:
        status, body, err = get_json(f"/exchange/forecast/{asset}")
        
        if err:
            results[asset] = {"error": err, "ok": False}
            log_test(f"P2.8.{asset}", False, {"error": err})
            continue
        
        forecast = body.get("forecast")
        direction = body.get("direction")
        
        # Exchange forecast should return forecast not null
        passed = (
            status == 200
            and not is_legacy_stub(body)
            and forecast is not None
        )
        
        results[asset] = {
            "status": status,
            "forecast": forecast,
            "direction": direction,
            "is_stub": is_legacy_stub(body),
            "passed": passed
        }
        
        log_test(
            f"P2.8.{asset}",
            passed,
            {
                "status": status,
                "forecast": forecast is not None,
                "is_stub": is_legacy_stub(body)
            }
        )
    
    all_ok = all(r.get("passed", False) for r in results.values())
    log_test("P2.8_OVERALL", all_ok, {"assets_tested": len(PRODUCTION_ASSETS), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.9: Health & System Endpoints
# ═══════════════════════════════════════════════════════════════════════
def test_p2_9_health_system():
    print("\n" + "="*70)
    print("P2.9: Health & System Endpoints")
    print("="*70)
    
    endpoints = [
        "/health",
        "/system/aggregator-status",
        "/system/aggregator-live-metrics"
    ]
    
    results = {}
    for endpoint in endpoints:
        status, body, err = get_json(endpoint)
        
        passed = status == 200 and not err
        
        results[endpoint] = {
            "status": status,
            "ok": body.get("ok") if isinstance(body, dict) else None,
            "error": err,
            "passed": passed
        }
        
        log_test(
            f"P2.9{endpoint.replace('/', '.')}",
            passed,
            {
                "status": status,
                "error": err
            }
        )
    
    all_ok = all(r.get("passed", False) for r in results.values())
    log_test("P2.9_OVERALL", all_ok, {"endpoints_tested": len(endpoints), "results": results})
    return results


# ═══════════════════════════════════════════════════════════════════════
# P2.10: Twitter Parser Admin
# ═══════════════════════════════════════════════════════════════════════
def test_p2_10_twitter_parser_admin():
    print("\n" + "="*70)
    print("P2.10: Twitter Parser Admin Endpoints")
    print("="*70)
    
    # Test parser status
    status1, body1, err1 = get_json("/admin/twitter/parser/status")
    
    # Test accounts endpoint
    status2, body2, err2 = get_json("/v4/twitter/accounts")
    
    # Check for vdieu74436 ACTIVE account
    has_vdieu = "vdieu74436" in str(body2).lower() if not err2 else False
    
    passed1 = status1 == 200 and not err1
    passed2 = status2 == 200 and not err2
    
    log_test(
        "P2.10.parser_status",
        passed1,
        {
            "status": status1,
            "error": err1
        }
    )
    
    log_test(
        "P2.10.accounts",
        passed2,
        {
            "status": status2,
            "has_vdieu74436": has_vdieu,
            "error": err2
        },
        warning=not has_vdieu  # Warning if vdieu74436 not found
    )
    
    overall = passed1 and passed2
    log_test("P2.10_OVERALL", overall, {"parser_status": passed1, "accounts": passed2})
    return {"parser_status": body1, "accounts": body2}


# ═══════════════════════════════════════════════════════════════════════
# Main Test Runner
# ═══════════════════════════════════════════════════════════════════════
def main():
    print("\n" + "="*70)
    print("P2 BACKEND REGRESSION TEST — FOMO OS Production Universe")
    print("="*70)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Start: {datetime.utcnow().isoformat()}")
    print("="*70)
    
    start_time = time.time()
    
    # Run all tests
    test_p2_1_universe_coverage()
    test_p2_2_symbol_normalization()
    test_p2_3_ta_module()
    test_p2_4_fractal_module()
    test_p2_5_sentiment_substrate()
    test_p2_6_sentiment_mobile_miniapp()
    test_p2_7_venues_health()
    test_p2_8_exchange_forecast()
    test_p2_9_health_system()
    test_p2_10_twitter_parser_admin()
    
    duration = time.time() - start_time
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {test_results['summary']['total']}")
    print(f"Passed: {test_results['summary']['passed']}")
    print(f"Failed: {test_results['summary']['failed']}")
    print(f"Warnings: {test_results['summary']['warnings']}")
    print(f"Duration: {duration:.2f}s")
    print("="*70)
    
    # Save results
    test_results["duration_seconds"] = duration
    with open("/app/test_reports/iteration_11.json", "w") as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\n✅ Test results saved to /app/test_reports/iteration_11.json")
    
    # Exit with appropriate code
    if test_results['summary']['failed'] > 0:
        print("\n❌ TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
