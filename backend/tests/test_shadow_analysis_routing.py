"""
Shadow Analysis & Routing Engine Tests
========================================
Tests for:
- GET /api/admin/sentiment-ml/shadow/analysis - Full shadow analysis for First Read
- POST /api/admin/sentiment-ml/shadow/routing/seed - Initialize default routing rules
- GET /api/admin/sentiment-ml/shadow/routing/rules - Get all routing rules
- POST /api/admin/sentiment-ml/shadow/routing/match - Test context against routing rules
- PUT /api/admin/sentiment-ml/shadow/routing/rules/:name - Update a routing rule
- GET /api/admin/sentiment-ml/shadow/label-distribution - Label distribution check
- GET /api/admin/sentiment-ml/shadow/stats - Stats with contextCoverage
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShadowAnalysisEndpoint:
    """Tests for GET /api/admin/sentiment-ml/shadow/analysis"""
    
    def test_analysis_endpoint_returns_required_fields(self):
        """Analysis should return scenario, recommendation, global, slices, crossSlice, confidenceCalibration, dataReady, nextMilestone"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        
        # Required top-level fields
        required_fields = ['scenario', 'recommendation', 'global', 'slices', 'crossSlice', 'confidenceCalibration', 'dataReady', 'nextMilestone']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: Analysis endpoint returns all required fields: {required_fields}")
        print(f"  scenario: {data['scenario']}")
        print(f"  recommendation: {data['recommendation']}")
        print(f"  dataReady: {data['dataReady']}")
        print(f"  nextMilestone: {data['nextMilestone']}")
    
    def test_analysis_global_fields(self):
        """Global should include delta, mlAccuracy, ruleAccuracy, deltaRaw, disagreements, mlWinsOnDisagreement, ruleWinsOnDisagreement, promotionReady, blockers"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200
        
        data = response.json()
        global_data = data.get('global', {})
        
        required_global_fields = [
            'total', 'evaluated', 'pending', 'mlAccuracy', 'ruleAccuracy', 
            'delta', 'deltaRaw', 'agreementRate', 'disagreements', 
            'mlWinsOnDisagreement', 'ruleWinsOnDisagreement', 
            'promotionReady', 'blockers'
        ]
        
        for field in required_global_fields:
            assert field in global_data, f"Missing global field: {field}"
        
        print(f"PASS: Global section contains all required fields")
        print(f"  evaluated: {global_data['evaluated']}")
        print(f"  delta: {global_data['delta']}")
        print(f"  deltaRaw: {global_data['deltaRaw']}")
        print(f"  promotionReady: {global_data['promotionReady']}")
        print(f"  blockers: {global_data['blockers']}")
    
    def test_analysis_slices_structure(self):
        """Slices should include byImportance, byEventType, byRecency, byAssetClass, byVolatility"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200
        
        data = response.json()
        slices = data.get('slices', {})
        
        required_slice_dimensions = ['byImportance', 'byEventType', 'byRecency', 'byAssetClass', 'byVolatility']
        
        for dim in required_slice_dimensions:
            assert dim in slices, f"Missing slice dimension: {dim}"
            assert isinstance(slices[dim], list), f"Slice {dim} should be a list"
        
        print(f"PASS: Slices section contains all required dimensions: {required_slice_dimensions}")
    
    def test_analysis_cross_slice_structure(self):
        """CrossSlice should include topWinning, topLosing, allSlices"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200
        
        data = response.json()
        cross_slice = data.get('crossSlice', {})
        
        required_cross_fields = ['topWinning', 'topLosing', 'allSlices']
        
        for field in required_cross_fields:
            assert field in cross_slice, f"Missing crossSlice field: {field}"
            assert isinstance(cross_slice[field], list), f"CrossSlice {field} should be a list"
        
        print(f"PASS: CrossSlice section contains all required fields: {required_cross_fields}")
    
    def test_analysis_confidence_calibration_structure(self):
        """ConfidenceCalibration should be array with range, samples, mlAccuracy, calibrated"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200
        
        data = response.json()
        calibration = data.get('confidenceCalibration', [])
        
        assert isinstance(calibration, list), "confidenceCalibration should be a list"
        
        # If there are calibration buckets, verify structure
        if len(calibration) > 0:
            bucket = calibration[0]
            required_bucket_fields = ['range', 'samples', 'mlAccuracy', 'calibrated']
            for field in required_bucket_fields:
                assert field in bucket, f"Missing calibration bucket field: {field}"
            print(f"PASS: ConfidenceCalibration buckets have correct structure")
        else:
            print(f"PASS: ConfidenceCalibration is empty (no evaluated data yet)")
    
    def test_analysis_insufficient_data_scenario(self):
        """With 0 evaluated decisions, scenario should be INSUFFICIENT_DATA and recommendation in Russian"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/analysis")
        assert response.status_code == 200
        
        data = response.json()
        evaluated = data.get('global', {}).get('evaluated', 0)
        
        if evaluated == 0:
            assert data['scenario'] == 'INSUFFICIENT_DATA', f"Expected INSUFFICIENT_DATA scenario, got {data['scenario']}"
            # Check recommendation is in Russian (contains Cyrillic characters)
            recommendation = data.get('recommendation', '')
            has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in recommendation)
            assert has_cyrillic, f"Recommendation should be in Russian, got: {recommendation}"
            print(f"PASS: With 0 evaluated, scenario=INSUFFICIENT_DATA, recommendation in Russian")
            print(f"  recommendation: {recommendation}")
        else:
            print(f"SKIP: evaluated={evaluated} > 0, cannot test INSUFFICIENT_DATA scenario")


class TestRoutingEngineEndpoints:
    """Tests for routing engine endpoints"""
    
    def test_routing_seed_creates_default_rules(self):
        """POST /routing/seed should create 3 default rules (high_priority_fresh, high_importance_any, default)"""
        response = requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        
        # Should have seeded or existing counts
        seeded = data.get('seeded', 0)
        existing = data.get('existing', 0)
        total = seeded + existing
        
        assert total == 3, f"Expected 3 total rules (seeded + existing), got {total}"
        
        print(f"PASS: Routing seed endpoint works")
        print(f"  seeded: {seeded}, existing: {existing}, total: {total}")
    
    def test_routing_rules_returns_correct_structure(self):
        """GET /routing/rules should return rules with name, conditions, action, priority, enabled, minSampleSize, minDelta, evidence, validation"""
        # First seed to ensure rules exist
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True
        
        rules = data.get('rules', [])
        assert len(rules) >= 3, f"Expected at least 3 rules, got {len(rules)}"
        
        # Check structure of each rule
        required_rule_fields = ['name', 'conditions', 'action', 'priority', 'enabled', 'minSampleSize', 'minDelta', 'validation']
        
        for rule in rules:
            for field in required_rule_fields:
                assert field in rule, f"Rule {rule.get('name')} missing field: {field}"
            
            # Validation should have valid and blockers
            validation = rule.get('validation', {})
            assert 'valid' in validation, f"Rule {rule.get('name')} validation missing 'valid'"
            assert 'blockers' in validation, f"Rule {rule.get('name')} validation missing 'blockers'"
        
        print(f"PASS: Routing rules have correct structure")
        for rule in rules:
            print(f"  - {rule['name']}: action={rule['action']}, enabled={rule['enabled']}, priority={rule['priority']}")
    
    def test_ml_routing_rules_disabled_by_default(self):
        """All ML routing rules should be DISABLED by default (only 'default' with action=RULE is enabled)"""
        # First seed to ensure rules exist
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules")
        assert response.status_code == 200
        
        data = response.json()
        rules = data.get('rules', [])
        
        # Find specific rules
        high_priority_fresh = next((r for r in rules if r['name'] == 'high_priority_fresh'), None)
        high_importance_any = next((r for r in rules if r['name'] == 'high_importance_any'), None)
        default_rule = next((r for r in rules if r['name'] == 'default'), None)
        
        assert high_priority_fresh is not None, "high_priority_fresh rule not found"
        assert high_importance_any is not None, "high_importance_any rule not found"
        assert default_rule is not None, "default rule not found"
        
        # ML rules should be disabled
        assert high_priority_fresh['enabled'] == False, f"high_priority_fresh should be disabled, got enabled={high_priority_fresh['enabled']}"
        assert high_priority_fresh['action'] == 'ML', f"high_priority_fresh should have action=ML"
        
        assert high_importance_any['enabled'] == False, f"high_importance_any should be disabled, got enabled={high_importance_any['enabled']}"
        assert high_importance_any['action'] == 'ML', f"high_importance_any should have action=ML"
        
        # Default rule should be enabled with action=RULE
        assert default_rule['enabled'] == True, f"default should be enabled, got enabled={default_rule['enabled']}"
        assert default_rule['action'] == 'RULE', f"default should have action=RULE"
        
        print(f"PASS: ML routing rules are DISABLED by default")
        print(f"  high_priority_fresh: enabled={high_priority_fresh['enabled']}, action={high_priority_fresh['action']}")
        print(f"  high_importance_any: enabled={high_importance_any['enabled']}, action={high_importance_any['action']}")
        print(f"  default: enabled={default_rule['enabled']}, action={default_rule['action']}")
    
    def test_routing_match_returns_rule_when_ml_disabled(self):
        """POST /routing/match with context should return action=RULE matchedRule=default (since ML rules are disabled)"""
        # First seed to ensure rules exist
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        # Test with context that would match high_priority_fresh if it were enabled
        context = {
            'importance': 'high',
            'recency': '<1h',
            'eventType': 'regulation'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/match",
            json=context
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True
        
        # Since ML rules are disabled, should match default rule
        assert data.get('action') == 'RULE', f"Expected action=RULE, got {data.get('action')}"
        assert data.get('matchedRule') == 'default', f"Expected matchedRule=default, got {data.get('matchedRule')}"
        
        print(f"PASS: Routing match returns RULE action when ML rules disabled")
        print(f"  context: {context}")
        print(f"  result: action={data['action']}, matchedRule={data['matchedRule']}")
    
    def test_routing_rule_update(self):
        """PUT /routing/rules/:name should update the rule and return validation with blockers"""
        # First seed to ensure rules exist
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        # Update high_priority_fresh to enabled=true
        update_payload = {'enabled': True}
        
        response = requests.put(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules/high_priority_fresh",
            json=update_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True
        
        # Should return updated rule
        rule = data.get('rule', {})
        assert rule.get('name') == 'high_priority_fresh', f"Expected rule name high_priority_fresh"
        assert rule.get('enabled') == True, f"Expected enabled=true after update"
        
        # Should return validation with blockers
        validation = data.get('validation', {})
        assert 'valid' in validation, "Validation should have 'valid' field"
        assert 'blockers' in validation, "Validation should have 'blockers' field"
        
        # Since no evidence, should have blockers
        assert validation['valid'] == False, "Validation should be invalid without evidence"
        assert len(validation['blockers']) > 0, "Should have blockers without evidence"
        
        print(f"PASS: Routing rule update works and returns validation")
        print(f"  updated rule: {rule.get('name')}, enabled={rule.get('enabled')}")
        print(f"  validation: valid={validation['valid']}, blockers={validation['blockers']}")
        
        # Revert the change - disable the rule again
        requests.put(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules/high_priority_fresh",
            json={'enabled': False}
        )


class TestExistingEndpoints:
    """Tests for existing endpoints that should still work"""
    
    def test_label_distribution_endpoint(self):
        """GET /label-distribution should still work"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/label-distribution")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True
        
        # Should have required fields
        required_fields = ['totalEvaluated', 'distribution', 'percentages', 'quality']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: Label distribution endpoint works")
        print(f"  totalEvaluated: {data['totalEvaluated']}")
        print(f"  distribution: {data['distribution']}")
        print(f"  quality: {data['quality']}")
    
    def test_stats_endpoint_with_context_coverage(self):
        """GET /stats should still show contextCoverage"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True
        
        # Should have contextCoverage in formatted
        formatted = data.get('formatted', {})
        assert 'contextCoverage' in formatted, f"Missing contextCoverage in formatted, got: {formatted}"
        
        print(f"PASS: Stats endpoint shows contextCoverage")
        print(f"  contextCoverage: {formatted.get('contextCoverage')}")


class TestRoutingRulesPriority:
    """Tests for routing rules priority and conditions"""
    
    def test_rules_sorted_by_priority(self):
        """Rules should be sorted by priority (highest first)"""
        # First seed to ensure rules exist
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules")
        assert response.status_code == 200
        
        data = response.json()
        rules = data.get('rules', [])
        
        # Check priority order
        priorities = [r['priority'] for r in rules]
        assert priorities == sorted(priorities, reverse=True), f"Rules not sorted by priority desc: {priorities}"
        
        print(f"PASS: Rules sorted by priority (highest first)")
        for rule in rules:
            print(f"  - {rule['name']}: priority={rule['priority']}")
    
    def test_high_priority_fresh_conditions(self):
        """high_priority_fresh should have correct conditions"""
        requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/seed")
        
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/routing/rules")
        data = response.json()
        rules = data.get('rules', [])
        
        rule = next((r for r in rules if r['name'] == 'high_priority_fresh'), None)
        assert rule is not None
        
        conditions = rule.get('conditions', {})
        
        # Should have importance=['high'], recency=['<1h', '1-3h'], eventType=['regulation', 'macro']
        assert 'high' in conditions.get('importance', []), "Should have importance=['high']"
        assert '<1h' in conditions.get('recency', []) or '1-3h' in conditions.get('recency', []), "Should have recency with <1h or 1-3h"
        assert 'regulation' in conditions.get('eventType', []) or 'macro' in conditions.get('eventType', []), "Should have eventType with regulation or macro"
        
        print(f"PASS: high_priority_fresh has correct conditions")
        print(f"  conditions: {conditions}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
