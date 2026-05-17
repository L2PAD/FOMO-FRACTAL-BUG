#!/usr/bin/env python3
"""Quick API test for signals/vfinal"""
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

print(f"Testing: {BASE_URL}/api/signals/vfinal")

try:
    resp = requests.get(f"{BASE_URL}/api/signals/vfinal?asset=BTCUSDT&tf=1h", timeout=60)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        
        print("\n=== Backend API Test Results ===")
        print(f"1. ok: {data.get('ok')}")
        
        exec_data = data.get('execution', {})
        print(f"2. activityLevel: {exec_data.get('activityLevel')} (type: {type(exec_data.get('activityLevel')).__name__})")
        print(f"3. executionMode: {exec_data.get('executionMode')}")
        
        alignment = data.get('coreAlignment', {})
        print(f"4. coreAlignment: status={alignment.get('status')}, detail='{alignment.get('detail')}'")
        
        events = data.get('events', [])
        print(f"5. Events ({len(events)}):")
        for ev in events:
            print(f"   - {ev.get('type')}: source={ev.get('source')}")
        
        weights = exec_data.get('weights', {})
        print(f"6. weights: {weights}")
        
        contributors = exec_data.get('contributors', {})
        print(f"7. contributors: {contributors}")
        
        # Verify activity mode thresholds
        activity = exec_data.get('activityLevel', 0)
        mode = exec_data.get('executionMode', '')
        if activity < 0.35:
            expected = 'LOW_ACTIVITY'
        elif activity > 0.65:
            expected = 'HIGH_ACTIVITY'
        else:
            expected = 'MODERATE_ACTIVITY'
        
        print(f"\n8. Threshold check: activityLevel={activity:.4f} -> expected {expected}, got {mode}")
        print(f"   Result: {'PASS' if mode == expected else 'FAIL'}")
        
        # Verify source field mapping
        macro_types = ['EXTREME_FEAR', 'EXTREME_GREED', 'ACTIONS_BLOCKED', 'CAPITAL_EXIT_REGIME', 'RISKOFF_SPIKE']
        structural_types = ['HIGH_RISK', 'REGIME_INSTABILITY', 'BTC_DOMINANCE_SHIFT']
        all_sources_ok = True
        for ev in events:
            etype = ev.get('type')
            source = ev.get('source')
            if etype in macro_types and source != 'macro':
                print(f"   FAIL: {etype} should be macro, got {source}")
                all_sources_ok = False
            elif etype in structural_types and source != 'structural':
                print(f"   FAIL: {etype} should be structural, got {source}")
                all_sources_ok = False
        print(f"9. Event source mapping: {'PASS' if all_sources_ok else 'FAIL'}")
        
        print("\n=== Full Response ===")
        print(json.dumps(data, indent=2)[:3000])
        
except Exception as e:
    print(f"Error: {e}")
