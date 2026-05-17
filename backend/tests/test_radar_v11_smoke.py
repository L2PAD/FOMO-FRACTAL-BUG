"""Radar V11 Smoke Tests — 10 sanity checks."""
import requests, json, os

API = os.environ.get("API_URL", "https://expo-telegram-web.preview.emergentagent.com")
errors = []
passed = 0

# === SPOT ===
resp = requests.get(f"{API}/api/v11/exchange/radar/spot?venue=main")
spot = resp.json()
print(f"Spot count: {spot['count']}")

for r in spot['rows']:
    f = r['features']
    sym = r['symbol']

    # Conv 0-100
    if not (0 <= r['conviction'] <= 100):
        errors.append(f"{sym}: conv {r['conviction']} out of 0-100")
    # NEUTRAL <= 45
    if r['verdict'] == 'neutral' and r['conviction'] > 45:
        errors.append(f"{sym}: NEUTRAL with conv {r['conviction']} > 45")
    # WATCH <= 59
    if r['verdict'] == 'watch' and r['conviction'] > 59:
        errors.append(f"{sym}: WATCH with conv {r['conviction']} > 59")
    # BUY >= 60
    if r['verdict'] == 'buy' and r['conviction'] < 60:
        errors.append(f"{sym}: BUY with conv {r['conviction']} < 60")
    # Low liq caps at 40
    if f['liquidity'] < 0.3 and r['conviction'] > 40:
        errors.append(f"{sym}: low liq {f['liquidity']} but conv {r['conviction']} > 40")
    # Reasons min 3
    if len(r['reasons']) < 3:
        errors.append(f"{sym}: only {len(r['reasons'])} reasons (need >= 3)")
    # Features 0-1
    for k, v in f.items():
        if not (0 <= v <= 1):
            errors.append(f"{sym}: feature {k}={v} not in [0,1]")
    # explain exists
    if not r.get('explain', {}).get('whyNow'):
        errors.append(f"{sym}: missing explain.whyNow")
    # direction exists
    if r['direction'] not in ('long', 'short', 'neutral'):
        errors.append(f"{sym}: invalid direction {r['direction']}")

    passed += 1

# Spot-specific tests
# Test 1: High liq + strong trend = BUY conv > 60
buys = [r for r in spot['rows'] if r['verdict'] == 'buy']
for b in buys:
    if b['features']['trendAlignment'] < 0.55:
        errors.append(f"SPOT-1: {b['symbol']} BUY but alignment {b['features']['trendAlignment']} < 0.55")
    if b['features']['risk'] > 0.45:
        errors.append(f"SPOT-1: {b['symbol']} BUY but risk {b['features']['risk']} > 0.45")

# Test 3: compression high + volumeBuild low = should be WATCH or NEUTRAL, not BUY
for r in spot['rows']:
    if r['features']['compression'] > 0.6 and r['features']['volumeBuild'] < 0.3:
        if r['verdict'] == 'buy':
            errors.append(f"SPOT-3: {r['symbol']} BUY despite low volumeBuild {r['features']['volumeBuild']}")

# Test 4: trendAlignment low = not BUY
for r in spot['rows']:
    if r['features']['trendAlignment'] < 0.35 and r['verdict'] == 'buy':
        errors.append(f"SPOT-4: {r['symbol']} BUY despite low alignment {r['features']['trendAlignment']}")

print()

# === FUTURES ===
resp2 = requests.get(f"{API}/api/v11/exchange/radar/futures?limit=50")
fut = resp2.json()
print(f"Futures count: {fut['count']}")

for r in fut['rows']:
    f = r['features']
    sym = r['symbol']

    if not (0 <= r['conviction'] <= 100):
        errors.append(f"{sym}: conv {r['conviction']} out of 0-100")
    if r['verdict'] == 'neutral' and r['conviction'] > 44:
        errors.append(f"{sym}: NEUTRAL with conv {r['conviction']} > 44")
    if r['verdict'] == 'watch' and r['conviction'] > 59:
        errors.append(f"{sym}: WATCH with conv {r['conviction']} > 59")
    if r['verdict'] == 'buy' and r['conviction'] < 60:
        errors.append(f"{sym}: BUY with conv {r['conviction']} < 60")
    if len(r['reasons']) < 3:
        errors.append(f"{sym}: only {len(r['reasons'])} reasons (need >= 3)")
    for k, v in f.items():
        if k == 'fundingSkew':
            if not (-1 <= v <= 1):
                errors.append(f"{sym}: feature {k}={v} not in [-1,1]")
        else:
            if not (0 <= v <= 1):
                errors.append(f"{sym}: feature {k}={v} not in [0,1]")
    if not r.get('explain', {}).get('whyNow'):
        errors.append(f"{sym}: missing explain.whyNow")
    # squeezeRiskScore 0-1
    if not (0 <= r['squeezeRiskScore'] <= 1):
        errors.append(f"{sym}: squeezeRiskScore {r['squeezeRiskScore']} out of 0-1")

    # Test 7: funding extreme + BUY/SELL = must have warning
    if abs(f['fundingSkew']) > 0.7 and r['verdict'] in ('buy', 'sell'):
        errors.append(f"FUT-7: {sym} {r['verdict'].upper()} with extreme funding {f['fundingSkew']}")

    # Test 8: squeezeRisk high = not strong BUY/SELL
    if r['squeezeRisk'] == 'high' and r['verdict'] in ('buy', 'sell'):
        errors.append(f"FUT-8: {sym} {r['verdict'].upper()} with high squeezeRisk")

    passed += 1

print()
print(f"=== RESULTS ===")
print(f"Rows checked: {passed}")
if errors:
    print(f"FAILURES ({len(errors)}):")
    for e in errors:
        print(f"  FAIL: {e}")
else:
    print("ALL 10 SANITY CHECKS PASSED")

# Save report
report = {
    "passed": passed,
    "failures": len(errors),
    "errors": errors,
    "spot_count": spot['count'],
    "futures_count": fut['count'],
}
with open('/app/test_reports/radar_v11_smoke.json', 'w') as fp:
    json.dump(report, fp, indent=2)
print(f"\nReport saved to /app/test_reports/radar_v11_smoke.json")
