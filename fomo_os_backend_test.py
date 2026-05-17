"""
FOMO OS Backend Test Suite
===========================
Tests all backend endpoints for the FOMO OS Web platform.
Preview URL: https://fomo-module-deploy.preview.emergentagent.com
"""
import requests
import sys
from datetime import datetime

BASE_URL = "https://fomo-module-deploy.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

class FOMOOSBackendTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def test(self, name, method, endpoint, expected_status=200, params=None, check_fn=None):
        """Run a single API test"""
        url = f"{API_URL}/{endpoint}"
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=params or {}, timeout=30)
            else:
                print(f"❌ Unsupported method: {method}")
                self.failed_tests.append({"name": name, "error": f"Unsupported method {method}"})
                return False

            print(f"   Status: {response.status_code}")
            
            if response.status_code != expected_status:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                self.failed_tests.append({
                    "name": name,
                    "endpoint": endpoint,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:200]
                })
                return False

            # Check response body if check_fn provided
            if check_fn:
                try:
                    data = response.json()
                    check_result = check_fn(data)
                    if not check_result:
                        print(f"❌ Failed - Response validation failed")
                        self.failed_tests.append({
                            "name": name,
                            "endpoint": endpoint,
                            "error": "Response validation failed",
                            "response": str(data)[:200]
                        })
                        return False
                except Exception as e:
                    print(f"❌ Failed - Check function error: {e}")
                    self.failed_tests.append({
                        "name": name,
                        "endpoint": endpoint,
                        "error": f"Check function error: {e}"
                    })
                    return False

            self.tests_passed += 1
            print(f"✅ Passed")
            return True

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (30s)")
            self.failed_tests.append({"name": name, "endpoint": endpoint, "error": "Timeout"})
            return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({"name": name, "endpoint": endpoint, "error": str(e)})
            return False

    def run_all_tests(self):
        """Run all FOMO OS backend tests"""
        print("=" * 80)
        print("FOMO OS Backend Test Suite")
        print(f"Base URL: {BASE_URL}")
        print(f"Started: {datetime.now().isoformat()}")
        print("=" * 80)

        # Test 1: UI Overview endpoint (KEY endpoint for OverviewPage)
        self.test(
            "UI Overview - BTC 90D",
            "GET",
            "ui/overview",
            params={"asset": "btc", "horizon": 90},
            check_fn=lambda d: (
                d.get("ok") == True and
                "verdict" in d and
                "reasons" in d and
                "risks" in d and
                "indicators" in d and
                "pipeline" in d and
                "horizons" in d and
                "meta" in d and
                "candles" in d and
                "charts" in d and
                "actual" in d.get("charts", {}) and
                "predicted" in d.get("charts", {})
            )
        )

        # Test 2: News Feed (must return clusters)
        self.test(
            "News Feed",
            "GET",
            "news/feed",
            params={"limit": 10},
            check_fn=lambda d: (
                d.get("ok") == True and
                "data" in d and
                "clusters" in d.get("data", {}) and
                len(d.get("data", {}).get("clusters", [])) > 0
            )
        )

        # Test 3: Deep Stats
        self.test(
            "Deep Stats",
            "GET",
            "deep/stats",
            check_fn=lambda d: (
                d.get("ok") == True and
                "counts" in d and
                d.get("counts", {}).get("deep_projects", 0) > 0
            )
        )

        # Test 4: Tech Analysis - BTC
        self.test(
            "Tech Analysis - BTC",
            "GET",
            "tech-analysis/BTC",
            check_fn=lambda d: (
                d.get("ok") == True and
                "action" in d and
                "trend" in d and
                "momentum" in d and
                "price" in d
            )
        )

        # Test 5: Fractal Runtime - BTC
        self.test(
            "Fractal Runtime - BTC",
            "GET",
            "fractal/runtime/BTC",
            check_fn=lambda d: (
                d.get("ok") == True and
                "direction" in d and
                "confidence" in d
            )
        )

        # Test 6: Onchain Runtime - BTC
        self.test(
            "Onchain Runtime - BTC",
            "GET",
            "onchain/runtime/BTC",
            check_fn=lambda d: (
                d.get("ok") == True and
                "symbol" in d and
                "direction" in d and
                "confidence" in d
            )
        )

        # Test 7: Exchange Overview
        self.test(
            "Exchange Overview",
            "GET",
            "exchange/overview",
            check_fn=lambda d: (
                d.get("ok") == True and
                "items" in d and
                len(d.get("items", [])) > 0
            )
        )

        # Test 8: Fractal Match
        self.test(
            "Fractal Match",
            "GET",
            "fractal/match",
            check_fn=lambda d: d.get("ok") == True
        )

        # Test 9: Fractal Signal
        self.test(
            "Fractal Signal",
            "GET",
            "fractal/signal",
            check_fn=lambda d: d.get("ok") == True
        )

        # Test 10: Fractal SPX
        self.test(
            "Fractal SPX",
            "GET",
            "fractal/spx",
            check_fn=lambda d: (
                d.get("ok") == True and
                "asset" in d and
                d.get("asset") == "SPX"
            )
        )

        # Test 11: UI Fractal DXY Overview
        self.test(
            "UI Fractal DXY Overview",
            "GET",
            "ui/fractal/dxy/overview",
            check_fn=lambda d: (
                d.get("ok") == True and
                "asset" in d and
                d.get("asset") == "DXY"
            )
        )

        # Test 12: UI Brain Decision
        self.test(
            "UI Brain Decision",
            "GET",
            "ui/brain/decision",
            check_fn=lambda d: d.get("ok") == True
        )

        # Test 13: TA Engine Multi-Timeframe
        self.test(
            "TA Engine MTF - BTC",
            "GET",
            "ta-engine/mtf/BTC",
            params={"timeframes": "4H,1D,7D,30D"},
            check_fn=lambda d: (
                d.get("ok") == True and
                "tf_map" in d and
                len(d.get("tf_map", {})) > 0 and
                "4H" in d.get("tf_map", {}) and
                "candles" in d.get("tf_map", {}).get("4H", {})
            )
        )

        # Additional critical endpoints for Web UI

        # Test 14: Meta-Brain V2 Signals
        self.test(
            "Meta-Brain V2 Signals - BTC",
            "GET",
            "meta-brain-v2/signals",
            params={"asset": "BTC"},
            check_fn=lambda d: (
                d.get("ok") == True and
                "signals" in d and
                len(d.get("signals", [])) > 0
            )
        )

        # Test 15: Meta-Brain V2 Modules
        self.test(
            "Meta-Brain V2 Modules",
            "GET",
            "meta-brain-v2/modules",
            check_fn=lambda d: (
                d.get("ok") == True and
                "modules" in d and
                len(d.get("modules", [])) == 5  # ta, sentiment, fractal, exchange, onchain
            )
        )

        # Test 16: Fractal V2.1 Focus Pack (used by BtcFractalPage)
        self.test(
            "Fractal V2.1 Focus Pack - BTC",
            "GET",
            "fractal/v2.1/focus-pack",
            params={"symbol": "BTC", "focus": "30d"},
            check_fn=lambda d: (
                d.get("ok") == True and
                "forecasts" in d and
                "candles" in d
            )
        )

        # Test 17: UI Candles (used by charts)
        self.test(
            "UI Candles - BTC",
            "GET",
            "ui/candles",
            params={"asset": "BTC", "days": 90},
            check_fn=lambda d: (
                d.get("ok") == True and
                "candles" in d and
                len(d.get("candles", [])) > 0
            )
        )

        # Test 18: Sentiment Overview
        self.test(
            "Sentiment Overview - BTC",
            "GET",
            "sentiment/overview",
            params={"asset": "BTC"},
            check_fn=lambda d: (
                d.get("ok") == True and
                "direction" in d and
                "confidence" in d
            )
        )

        # Test 19: Market Candles (for Tech Analysis)
        self.test(
            "Market Candles - BTCUSDT",
            "GET",
            "market/candles",
            params={"symbol": "BTCUSDT", "timeframe": "4h", "limit": 200},
            check_fn=lambda d: (
                d.get("ok") == True and
                "candles" in d and
                len(d.get("candles", [])) > 0
            )
        )

        # Test 20: Market State (for Tech Analysis)
        self.test(
            "Market State - BTCUSDT",
            "GET",
            "market/state",
            params={"symbol": "BTCUSDT", "timeframe": "4h"},
            check_fn=lambda d: (
                d.get("ok") == True and
                "macro" in d and
                "indicators" in d and
                "coreInsight" in d
            )
        )

        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for i, test in enumerate(self.failed_tests, 1):
                print(f"\n{i}. {test['name']}")
                print(f"   Endpoint: {test.get('endpoint', 'N/A')}")
                print(f"   Error: {test.get('error', 'N/A')}")
                if 'expected' in test:
                    print(f"   Expected: {test['expected']}, Got: {test['actual']}")
                if 'response' in test:
                    print(f"   Response: {test['response']}")
        
        print("\n" + "=" * 80)
        return 0 if len(self.failed_tests) == 0 else 1


def main():
    tester = FOMOOSBackendTester()
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
