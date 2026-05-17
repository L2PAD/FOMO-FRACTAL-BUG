"""
FOMO OS — 5-Module Backend Test Suite
======================================
Tests all 5 MetaBrain modules (M1-M5) + MiniApp endpoints.

Modules:
  M1: Tech Analysis (TA)
  M2: Fractal
  M3: OnChain (per-asset)
  M4: Exchange (CEX intelligence)
  M5: Sentiment (News + Deep + Backers + Surface)

Usage:
  python backend_test_fomo_modules.py
"""
import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List

# Use public endpoint from frontend/.env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API_URL = f"{BASE_URL}/api"

class FOMOModuleTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "base_url": base_url,
            "modules": {},
        }

    def test(self, name: str, method: str, endpoint: str, expected_status: int = 200, 
             params: Dict = None, data: Dict = None, check_keys: List[str] = None) -> Dict[str, Any]:
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        self.tests_run += 1
        
        print(f"\n🔍 [{self.tests_run}] Testing {name}...")
        print(f"   {method} {endpoint}")
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "success": success,
                "response_time_ms": int(response.elapsed.total_seconds() * 1000),
            }
            
            if success:
                self.tests_passed += 1
                print(f"   ✅ PASS - Status: {response.status_code} ({result['response_time_ms']}ms)")
                
                try:
                    json_data = response.json()
                    result["response_data"] = json_data
                    
                    # Check for required keys
                    if check_keys:
                        missing_keys = [k for k in check_keys if k not in json_data]
                        if missing_keys:
                            result["success"] = False
                            result["error"] = f"Missing keys: {missing_keys}"
                            print(f"   ⚠️  Missing keys: {missing_keys}")
                        else:
                            print(f"   ✓  All required keys present: {check_keys}")
                    
                    # Print key metrics
                    if "ok" in json_data:
                        print(f"   ✓  ok={json_data['ok']}")
                    if "count" in json_data:
                        print(f"   ✓  count={json_data['count']}")
                    if "symbol" in json_data:
                        print(f"   ✓  symbol={json_data['symbol']}")
                        
                except Exception as e:
                    result["parse_error"] = str(e)
                    print(f"   ⚠️  JSON parse error: {e}")
            else:
                print(f"   ❌ FAIL - Expected {expected_status}, got {response.status_code}")
                try:
                    result["response_data"] = response.json()
                except:
                    result["response_text"] = response.text[:200]
            
            return result
            
        except Exception as e:
            print(f"   ❌ FAIL - Error: {str(e)}")
            return {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "success": False,
                "error": str(e),
            }

    def test_m1_tech_analysis(self):
        """M1: Tech Analysis Module"""
        print("\n" + "="*80)
        print("MODULE 1: TECH ANALYSIS")
        print("="*80)
        
        results = []
        
        # 1.1 Basic TA endpoint
        results.append(self.test(
            "M1.1 Tech Analysis BTC",
            "GET", "/api/tech-analysis/BTC",
            check_keys=["ok", "symbol", "action", "trend", "momentum", "indicators"]
        ))
        
        # 1.2 Multi-timeframe TA Engine (KEY endpoint for Analysis tab)
        results.append(self.test(
            "M1.2 TA Engine MTF BTC",
            "GET", "/api/ta-engine/mtf/BTC",
            params={"timeframes": "4H,1D,7D,30D"},
            check_keys=["ok", "symbol", "tf_map", "consensus"]
        ))
        
        # 1.3 Market candles
        results.append(self.test(
            "M1.3 Market Candles BTC",
            "GET", "/api/market/candles",
            params={"symbol": "BTC", "timeframe": "1D", "limit": 100},
            check_keys=["ok", "candles", "count"]
        ))
        
        # 1.4 Market regime
        results.append(self.test(
            "M1.4 Market Regime BTC",
            "GET", "/api/market/regime",
            params={"symbol": "BTC"},
            check_keys=["ok", "regime"]
        ))
        
        self.results["modules"]["M1_TechAnalysis"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_m2_fractal(self):
        """M2: Fractal Module"""
        print("\n" + "="*80)
        print("MODULE 2: FRACTAL")
        print("="*80)
        
        results = []
        
        # 2.1 Fractal runtime (native engine)
        results.append(self.test(
            "M2.1 Fractal Runtime BTC",
            "GET", "/api/fractal/runtime/BTC",
            check_keys=["ok", "symbol", "direction", "confidence"]
        ))
        
        # 2.2 Fractal intelligence dashboard
        results.append(self.test(
            "M2.2 Fractal Intelligence",
            "GET", "/api/fractal/intelligence",
            check_keys=["ok", "service"]
        ))
        
        # 2.3 Fractal heatmap
        results.append(self.test(
            "M2.3 Fractal Heatmap",
            "GET", "/api/fractal/heatmap",
            params={"limit": 10},
            check_keys=["ok", "rows", "count"]
        ))
        
        # 2.4 Fractal forecast
        results.append(self.test(
            "M2.4 Fractal Forecast BTC",
            "GET", "/api/fractal/forecast/BTC",
            params={"timeframe": "1D"},
            check_keys=["ok", "symbol", "consensus", "forecastPath"]
        ))
        
        # 2.5 Fractal similar patterns
        results.append(self.test(
            "M2.5 Fractal Similar BTC",
            "GET", "/api/fractal/similar/BTC",
            params={"timeframe": "1D"},
            check_keys=["ok", "symbol", "consensus", "matches"]
        ))
        
        self.results["modules"]["M2_Fractal"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_m3_onchain(self):
        """M3: OnChain Module (per-asset)"""
        print("\n" + "="*80)
        print("MODULE 3: ONCHAIN (PER-ASSET)")
        print("="*80)
        
        results = []
        
        # 3.1 OnChain runtime BTC
        results.append(self.test(
            "M3.1 OnChain Runtime BTC",
            "GET", "/api/onchain/runtime/BTC",
            check_keys=["symbol", "direction", "confidence"]
        ))
        
        # 3.2 OnChain runtime ETH
        results.append(self.test(
            "M3.2 OnChain Runtime ETH",
            "GET", "/api/onchain/runtime/ETH",
            check_keys=["symbol", "direction"]
        ))
        
        # 3.3 OnChain runtime SOL
        results.append(self.test(
            "M3.3 OnChain Runtime SOL",
            "GET", "/api/onchain/runtime/SOL",
            check_keys=["symbol", "direction"]
        ))
        
        self.results["modules"]["M3_OnChain"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_m4_exchange(self):
        """M4: Exchange (CEX Intelligence) Module"""
        print("\n" + "="*80)
        print("MODULE 4: EXCHANGE (CEX INTELLIGENCE)")
        print("="*80)
        
        results = []
        
        # 4.1 Exchange overview (multi-symbol dashboard)
        results.append(self.test(
            "M4.1 Exchange Overview",
            "GET", "/api/exchange/overview",
            check_keys=["ok", "items", "marketBias"]
        ))
        
        # 4.2 Exchange orderbook
        results.append(self.test(
            "M4.2 Exchange Orderbook BTC",
            "GET", "/api/exchange/orderbook/BTC",
            check_keys=["ok", "symbol", "asks", "bids", "imbalance"]
        ))
        
        # 4.3 Exchange funding rate
        results.append(self.test(
            "M4.3 Exchange Funding BTC",
            "GET", "/api/exchange/funding/BTC",
            check_keys=["ok", "symbol", "fundingRate", "bias"]
        ))
        
        # 4.4 Exchange open interest
        results.append(self.test(
            "M4.4 Exchange Open Interest BTC",
            "GET", "/api/exchange/open-interest/BTC",
            check_keys=["ok", "symbol", "oi"]
        ))
        
        # 4.5 Exchange tickers
        results.append(self.test(
            "M4.5 Exchange Tickers",
            "GET", "/api/exchange/tickers",
            params={"limit": 20},
            check_keys=["ok", "items", "count"]
        ))
        
        # 4.6 Venues health
        results.append(self.test(
            "M4.6 Exchange Venues Health",
            "GET", "/api/exchange/venues",
            check_keys=["ok", "venues", "primary"]
        ))
        
        self.results["modules"]["M4_Exchange"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_m5_sentiment(self):
        """M5: Sentiment Module (News + Deep + Backers + Surface)"""
        print("\n" + "="*80)
        print("MODULE 5: SENTIMENT")
        print("="*80)
        
        results = []
        
        # 5.1 News feed (RSS pipeline)
        results.append(self.test(
            "M5.1 News Feed",
            "GET", "/api/news/feed",
            params={"limit": 10},
            check_keys=["ok", "data", "count"]
        ))
        
        # 5.2 News digest
        results.append(self.test(
            "M5.2 News Digest",
            "GET", "/api/news/digest",
            check_keys=["ok", "total", "bullish", "bearish", "neutral"]
        ))
        
        # 5.3 News velocity
        results.append(self.test(
            "M5.3 News Velocity",
            "GET", "/api/news/velocity",
            params={"hours": 24},
            check_keys=["ok", "total", "series"]
        ))
        
        # 5.4 Deep stats
        results.append(self.test(
            "M5.4 Deep Stats",
            "GET", "/api/deep/stats",
            check_keys=["ok", "counts"]
        ))
        
        # 5.5 Deep funds
        results.append(self.test(
            "M5.5 Deep Funds",
            "GET", "/api/deep/funds",
            params={"limit": 10},
            check_keys=["ok", "funds", "count"]
        ))
        
        # 5.6 Deep persons
        results.append(self.test(
            "M5.6 Deep Persons",
            "GET", "/api/deep/persons",
            params={"limit": 10},
            check_keys=["ok", "persons", "count"]
        ))
        
        # 5.7 Deep unlocks
        results.append(self.test(
            "M5.7 Deep Unlocks",
            "GET", "/api/deep/unlocks",
            params={"limit": 10},
            check_keys=["ok", "unlocks", "count"]
        ))
        
        # 5.8 Deep projects list
        results.append(self.test(
            "M5.8 Deep Projects",
            "GET", "/api/deep/projects",
            params={"limit": 10},
            check_keys=["ok", "projects", "count"]
        ))
        
        # 5.9 Backers (VC funds)
        results.append(self.test(
            "M5.9 Backers",
            "GET", "/api/backers",
            params={"limit": 5},
            check_keys=["ok", "bakers", "count"]
        ))
        
        # 5.10 Backers active (funding flow)
        results.append(self.test(
            "M5.10 Backers Active",
            "GET", "/api/backers/active",
            params={"limit": 5},
            check_keys=["ok", "flows", "count"]
        ))
        
        # 5.11 Sentiment surface: clusters intelligence
        results.append(self.test(
            "M5.11 Clusters Intelligence",
            "GET", "/api/connections/clusters/intelligence",
            params={"limit": 10},
            check_keys=["ok", "data", "count"]
        ))
        
        # 5.12 Narrative flow
        results.append(self.test(
            "M5.12 Narrative Flow",
            "GET", "/api/narrative-flow",
            check_keys=["ok", "narratives", "tokens"]
        ))
        
        self.results["modules"]["M5_Sentiment"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_miniapp_endpoints(self):
        """MiniApp Endpoints (Telegram)"""
        print("\n" + "="*80)
        print("MINIAPP ENDPOINTS (TELEGRAM)")
        print("="*80)
        
        results = []
        
        # MiniApp Tech Analysis
        results.append(self.test(
            "MiniApp Tech Analysis",
            "GET", "/api/miniapp/tech-analysis",
            params={"asset": "BTC", "timeframe": "4H"},
            check_keys=["ok", "asset", "action"]
        ))
        
        # MiniApp Fractal
        results.append(self.test(
            "MiniApp Fractal",
            "GET", "/api/miniapp/fractal",
            params={"asset": "BTC"},
            check_keys=["ok", "asset", "phase"]
        ))
        
        # MiniApp Exchange
        results.append(self.test(
            "MiniApp Exchange",
            "GET", "/api/miniapp/exchange",
            params={"asset": "BTC"},
            check_keys=["ok", "symbol", "bias"]
        ))
        
        self.results["modules"]["MiniApp"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def test_health_endpoints(self):
        """Health & Status Endpoints"""
        print("\n" + "="*80)
        print("HEALTH & STATUS ENDPOINTS")
        print("="*80)
        
        results = []
        
        # Backend health
        results.append(self.test(
            "Backend Health",
            "GET", "/api/",
            check_keys=["status"]
        ))
        
        self.results["modules"]["Health"] = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("success")),
            "tests": results
        }

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total_tests = self.tests_run
        total_passed = self.tests_passed
        total_failed = total_tests - total_passed
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n📊 Overall Results:")
        print(f"   Total Tests:  {total_tests}")
        print(f"   Passed:       {total_passed} ✅")
        print(f"   Failed:       {total_failed} ❌")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        print(f"\n📦 Module Breakdown:")
        for module_name, module_data in self.results["modules"].items():
            total = module_data["total"]
            passed = module_data["passed"]
            failed = total - passed
            rate = (passed / total * 100) if total > 0 else 0
            status = "✅" if failed == 0 else "⚠️" if failed <= 2 else "❌"
            print(f"   {status} {module_name:20s} {passed}/{total} ({rate:.0f}%)")
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "success_rate": round(success_rate, 2),
        }
        
        # Save results to file
        output_file = "/app/backend_test_fomo_modules_result.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {output_file}")
        
        return total_failed == 0

    def run_all_tests(self):
        """Run all module tests"""
        print(f"\n🚀 Starting FOMO OS 5-Module Backend Test Suite")
        print(f"   Base URL: {self.base_url}")
        print(f"   Timestamp: {self.results['timestamp']}")
        
        start_time = time.time()
        
        # Test health first
        self.test_health_endpoints()
        
        # Test all 5 modules
        self.test_m1_tech_analysis()
        self.test_m2_fractal()
        self.test_m3_onchain()
        self.test_m4_exchange()
        self.test_m5_sentiment()
        
        # Test MiniApp endpoints
        self.test_miniapp_endpoints()
        
        duration = time.time() - start_time
        self.results["duration_seconds"] = round(duration, 2)
        
        # Print summary
        success = self.print_summary()
        
        print(f"\n⏱️  Total Duration: {duration:.1f}s")
        print(f"\n{'='*80}")
        if success:
            print("✅ ALL TESTS PASSED - FOMO OS 5 MODULES ARE LIVE")
        else:
            print("❌ SOME TESTS FAILED - SEE DETAILS ABOVE")
        print(f"{'='*80}\n")
        
        return 0 if success else 1


def main():
    """Main entry point"""
    tester = FOMOModuleTester(API_URL)
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
