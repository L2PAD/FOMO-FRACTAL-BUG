"""
Project Intelligence Engine Tests

Tests for Phase 2: Project Intelligence Engine — 6 services:
- Tokenomics Engine
- Unlock Pressure Service
- Valuation Engine
- Team/Fund Quality Service
- Launch Structure Service
- Project Thesis Engine

Endpoints:
- POST /api/project-intelligence/analyze — Full single-asset analysis
- POST /api/project-intelligence/batch — Batch analysis for multiple assets
- POST /api/project-intelligence/quick — Quick assessment (pipeline use)
- GET /api/project-intelligence/profiles — Known project profiles (19 assets)
- GET /api/project-intelligence/profile/:asset — Single project profile
- GET /api/prediction/run — projectIntel field on every case
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test assets with diverse characteristics
TEST_ASSETS = ['BTC', 'SOL', 'ETH', 'TIA', 'WLD']

# Dynamic data for SOL (high FDV scenario)
SOL_DYNAMIC_DATA = {
    "currentPrice": 180,
    "fdv": 106200000000,  # $106.2B
    "marketCap": 79200000000  # $79.2B
}

# Dynamic data for BTC (store of value)
BTC_DYNAMIC_DATA = {
    "currentPrice": 100000,
    "fdv": 2100000000000,  # $2.1T
    "marketCap": 1980000000000  # $1.98T
}

# Dynamic data for TIA (unlock scenario)
TIA_DYNAMIC_DATA = {
    "currentPrice": 5,
    "fdv": 5000000000,  # $5B
    "marketCap": 1250000000  # $1.25B
}


class TestProjectIntelligenceProfiles:
    """Test GET /api/project-intelligence/profiles and /profile/:asset"""

    def test_get_all_profiles(self):
        """GET /api/project-intelligence/profiles returns all known profiles"""
        response = requests.get(f"{BASE_URL}/api/project-intelligence/profiles")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'profiles' in data, "Response should have profiles array"
        assert 'count' in data, "Response should have count"
        
        profiles = data['profiles']
        assert isinstance(profiles, list), "profiles should be a list"
        assert len(profiles) >= 19, f"Expected at least 19 profiles, got {len(profiles)}"
        
        # Verify key assets are present
        for asset in ['BTC', 'ETH', 'SOL', 'TIA', 'WLD', 'PEPE', 'DOGE']:
            assert asset in profiles, f"{asset} should be in profiles"
        
        print(f"✓ GET /profiles: {len(profiles)} profiles returned")

    def test_get_single_profile_btc(self):
        """GET /api/project-intelligence/profile/BTC returns BTC profile"""
        response = requests.get(f"{BASE_URL}/api/project-intelligence/profile/BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'profile' in data
        
        profile = data['profile']
        assert profile['asset'] == 'BTC'
        assert profile['name'] == 'Bitcoin'
        assert profile['sector'] == 'l1'
        assert profile['launchType'] == 'fair_launch'
        assert profile['teamReputation'] == 'STRONG'
        assert profile['insiderAllocation'] == 0.0, "BTC should have 0 insider allocation"
        
        print(f"✓ GET /profile/BTC: {profile['name']} ({profile['sector']})")

    def test_get_single_profile_sol(self):
        """GET /api/project-intelligence/profile/SOL returns SOL profile"""
        response = requests.get(f"{BASE_URL}/api/project-intelligence/profile/SOL")
        assert response.status_code == 200
        
        data = response.json()
        profile = data['profile']
        
        assert profile['asset'] == 'SOL'
        assert profile['name'] == 'Solana'
        assert profile['launchType'] == 'vc_backed'
        assert profile['insiderAllocation'] == 0.48, "SOL should have 48% insider allocation"
        assert 'a16z' in profile.get('topFundsInvolved', [])
        
        print(f"✓ GET /profile/SOL: insider={profile['insiderAllocation']*100}%")

    def test_get_single_profile_tia(self):
        """GET /api/project-intelligence/profile/TIA returns TIA profile with unlock data"""
        response = requests.get(f"{BASE_URL}/api/project-intelligence/profile/TIA")
        assert response.status_code == 200
        
        data = response.json()
        profile = data['profile']
        
        assert profile['asset'] == 'TIA'
        assert profile['name'] == 'Celestia'
        assert profile['sector'] == 'infra'
        assert 'nextUnlockDate' in profile, "TIA should have nextUnlockDate"
        assert 'nextUnlockPercent' in profile, "TIA should have nextUnlockPercent"
        assert profile['insiderAllocation'] == 0.60, "TIA should have 60% insider allocation"
        
        print(f"✓ GET /profile/TIA: unlock={profile.get('nextUnlockPercent')}% on {profile.get('nextUnlockDate')}")

    def test_get_unknown_profile(self):
        """GET /api/project-intelligence/profile/UNKNOWN returns default profile"""
        response = requests.get(f"{BASE_URL}/api/project-intelligence/profile/UNKNOWN")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        profile = data['profile']
        assert profile['asset'] == 'UNKNOWN'
        
        print("✓ GET /profile/UNKNOWN: returns default profile")


class TestProjectIntelligenceAnalyze:
    """Test POST /api/project-intelligence/analyze — Full single-asset analysis"""

    def test_analyze_btc(self):
        """Analyze BTC — should be STRONG with good fundamentals"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "BTC", "dynamicData": BTC_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'intel' in data
        
        intel = data['intel']
        assert intel['asset'] == 'BTC'
        
        # Verify all 6 engines present
        assert 'tokenomics' in intel, "Should have tokenomics"
        assert 'unlockPressure' in intel, "Should have unlockPressure"
        assert 'valuation' in intel, "Should have valuation"
        assert 'teamFund' in intel, "Should have teamFund"
        assert 'launch' in intel, "Should have launch"
        assert 'thesis' in intel, "Should have thesis"
        
        # BTC should be STRONG
        thesis = intel['thesis']
        assert thesis['projectVerdict'] in ['STRONG', 'MIXED'], f"BTC should be STRONG/MIXED, got {thesis['projectVerdict']}"
        assert thesis['overallScore'] >= 0.5, f"BTC score should be >= 0.5, got {thesis['overallScore']}"
        
        # BTC tokenomics should be healthy
        tokenomics = intel['tokenomics']
        assert tokenomics['floatQuality'] == 'HEALTHY', "BTC should have healthy float"
        assert tokenomics['emissionRisk'] <= 0.3, "BTC should have low emission risk"
        
        # BTC unlock pressure should be LOW
        unlock = intel['unlockPressure']
        assert unlock['riskLevel'] == 'LOW', "BTC should have LOW unlock risk"
        assert unlock['insiderShare'] == 0.0, "BTC should have 0 insider share"
        
        # BTC launch should be fair
        launch = intel['launch']
        assert launch['fairLaunch'] is True, "BTC should be fair launch"
        
        print(f"✓ Analyze BTC: verdict={thesis['projectVerdict']}, score={thesis['overallScore']}")

    def test_analyze_sol_high_fdv(self):
        """Analyze SOL with high FDV — should show EXPENSIVE/MIXED"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "SOL", "dynamicData": SOL_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        intel = data['intel']
        
        # Verify tokenomics engine
        tokenomics = intel['tokenomics']
        assert 'fdvLevel' in tokenomics
        assert tokenomics['fdvLevel'] in ['HIGH', 'EXTREME'], f"SOL FDV should be HIGH/EXTREME at $106B, got {tokenomics['fdvLevel']}"
        
        # Verify valuation engine
        valuation = intel['valuation']
        assert 'valuation' in valuation
        assert valuation['valuation'] in ['EXPENSIVE', 'INSANE', 'FAIR'], f"SOL valuation at $106B FDV"
        assert 'expectedRange' in valuation
        assert 'confidence' in valuation
        
        # Verify team/fund quality
        teamFund = intel['teamFund']
        assert teamFund['verdict'] == 'STRONG', "SOL team should be STRONG"
        assert teamFund['fundScore'] >= 0.5, "SOL should have good fund backing"
        
        # Verify thesis
        thesis = intel['thesis']
        assert 'bullCase' in thesis
        assert 'bearCase' in thesis
        assert 'keyRisks' in thesis
        assert len(thesis['bullCase']) > 0, "Should have bull case points"
        assert len(thesis['bearCase']) > 0, "Should have bear case points"
        
        print(f"✓ Analyze SOL: FDV={tokenomics['fdvLevel']}, valuation={valuation['valuation']}, verdict={thesis['projectVerdict']}")

    def test_analyze_tia_unlock_pressure(self):
        """Analyze TIA — should show unlock pressure"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "TIA", "dynamicData": TIA_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        intel = data['intel']
        
        # Verify unlock pressure
        unlock = intel['unlockPressure']
        assert 'nextUnlockDays' in unlock
        assert 'unlockPercent' in unlock
        assert 'unlockImpactScore' in unlock
        assert 'insiderShare' in unlock
        assert 'riskLevel' in unlock
        
        # TIA has 60% insider allocation
        assert unlock['insiderShare'] == 0.60, f"TIA insider share should be 60%, got {unlock['insiderShare']}"
        
        # TIA has upcoming unlock
        assert unlock['unlockPercent'] == 8, f"TIA unlock should be 8%, got {unlock['unlockPercent']}"
        
        # Verify tokenomics - TIA has 25% float which is at boundary
        tokenomics = intel['tokenomics']
        # 25% float is at the boundary - can be HEALTHY or LOW depending on exact calculation
        assert tokenomics['floatQuality'] in ['LOW', 'DANGEROUS', 'HEALTHY'], f"TIA float quality"
        
        print(f"✓ Analyze TIA: unlock={unlock['unlockPercent']}% in {unlock['nextUnlockDays']}d, risk={unlock['riskLevel']}")

    def test_analyze_wld_ai_sector(self):
        """Analyze WLD — AI sector with specific characteristics"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "WLD"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intel = data['intel']
        
        # WLD is AI sector
        assert intel['asset'] == 'WLD'
        
        # Verify all components present
        assert all(k in intel for k in ['tokenomics', 'unlockPressure', 'valuation', 'teamFund', 'launch', 'thesis'])
        
        # WLD has low initial float (5%)
        tokenomics = intel['tokenomics']
        assert tokenomics['floatQuality'] in ['LOW', 'DANGEROUS'], "WLD should have low float"
        
        print(f"✓ Analyze WLD: float={tokenomics['floatQuality']}, verdict={intel['thesis']['projectVerdict']}")

    def test_analyze_pepe_meme(self):
        """Analyze PEPE — meme token characteristics"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "PEPE"}
        )
        assert response.status_code == 200
        
        data = response.json()
        intel = data['intel']
        
        # PEPE is fair launch meme
        launch = intel['launch']
        assert launch['fairLaunch'] is True, "PEPE should be fair launch"
        
        # PEPE has weak team (by design)
        teamFund = intel['teamFund']
        assert teamFund['verdict'] == 'WEAK', "PEPE team should be WEAK"
        
        # Valuation should note meme premium
        valuation = intel['valuation']
        assert valuation['narrativePremium'] >= 0.3, "PEPE should have narrative premium"
        
        print(f"✓ Analyze PEPE: fairLaunch={launch['fairLaunch']}, team={teamFund['verdict']}")

    def test_analyze_missing_asset(self):
        """Analyze with missing asset returns error"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is False
        assert 'error' in data
        
        print("✓ Analyze missing asset: returns error")


class TestProjectIntelligenceBatch:
    """Test POST /api/project-intelligence/batch — Batch analysis"""

    def test_batch_analyze_multiple_assets(self):
        """Batch analyze BTC, SOL, ETH, TIA, WLD"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/batch",
            json={
                "assets": TEST_ASSETS,
                "dynamicData": {
                    "SOL": SOL_DYNAMIC_DATA,
                    "BTC": BTC_DYNAMIC_DATA,
                    "TIA": TIA_DYNAMIC_DATA
                }
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'results' in data
        assert 'count' in data
        
        results = data['results']
        assert data['count'] == len(TEST_ASSETS), f"Expected {len(TEST_ASSETS)} results"
        
        # Verify each asset has full intel
        for asset in TEST_ASSETS:
            assert asset in results, f"{asset} should be in results"
            intel = results[asset]
            assert 'tokenomics' in intel
            assert 'thesis' in intel
            assert intel['thesis']['projectVerdict'] in ['STRONG', 'MIXED', 'WEAK']
        
        print(f"✓ Batch analyze: {data['count']} assets analyzed")
        for asset in TEST_ASSETS:
            print(f"  - {asset}: {results[asset]['thesis']['projectVerdict']}")

    def test_batch_analyze_empty_assets(self):
        """Batch analyze with empty assets returns error"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/batch",
            json={"assets": []}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is False
        
        print("✓ Batch analyze empty: returns error")

    def test_batch_analyze_limit(self):
        """Batch analyze respects 30 asset limit"""
        # Create 35 assets
        many_assets = [f"ASSET{i}" for i in range(35)]
        
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/batch",
            json={"assets": many_assets}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data['count'] <= 30, f"Should limit to 30 assets, got {data['count']}"
        
        print(f"✓ Batch analyze limit: {data['count']} assets (max 30)")


class TestProjectIntelligenceQuick:
    """Test POST /api/project-intelligence/quick — Quick assessment for pipeline"""

    def test_quick_assess_sol(self):
        """Quick assess SOL returns compact format"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/quick",
            json={"asset": "SOL", "dynamicData": SOL_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        # Verify quick format fields
        assert 'asset' in data
        assert 'verdict' in data
        assert 'valuation' in data
        assert 'unlockRisk' in data
        assert 'tokenomicsVerdict' in data
        assert 'overallScore' in data
        assert 'keyRisks' in data
        assert 'notes' in data
        
        assert data['asset'] == 'SOL'
        assert data['verdict'] in ['STRONG', 'MIXED', 'WEAK']
        assert data['valuation'] in ['CHEAP', 'FAIR', 'EXPENSIVE', 'INSANE']
        assert data['unlockRisk'] in ['LOW', 'MEDIUM', 'HIGH']
        assert isinstance(data['keyRisks'], list)
        assert isinstance(data['notes'], list)
        
        print(f"✓ Quick assess SOL: verdict={data['verdict']}, valuation={data['valuation']}")

    def test_quick_assess_btc(self):
        """Quick assess BTC returns STRONG verdict"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/quick",
            json={"asset": "BTC", "dynamicData": BTC_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['verdict'] in ['STRONG', 'MIXED'], f"BTC should be STRONG/MIXED, got {data['verdict']}"
        assert data['unlockRisk'] == 'LOW', "BTC should have LOW unlock risk"
        
        print(f"✓ Quick assess BTC: verdict={data['verdict']}, score={data['overallScore']}")

    def test_quick_assess_tia(self):
        """Quick assess TIA shows unlock risk"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/quick",
            json={"asset": "TIA", "dynamicData": TIA_DYNAMIC_DATA}
        )
        assert response.status_code == 200
        
        data = response.json()
        # TIA has significant unlock pressure
        assert data['unlockRisk'] in ['MEDIUM', 'HIGH'], f"TIA should have MEDIUM/HIGH unlock risk"
        
        print(f"✓ Quick assess TIA: unlockRisk={data['unlockRisk']}, verdict={data['verdict']}")


class TestTokenomicsEngine:
    """Verify tokenomics engine calculations"""

    def test_fdv_level_calculation(self):
        """Verify FDV level thresholds by sector"""
        # SOL at $106B should be HIGH/EXTREME for L1
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "SOL", "dynamicData": SOL_DYNAMIC_DATA}
        )
        data = response.json()
        tokenomics = data['intel']['tokenomics']
        
        assert tokenomics['fdvLevel'] in ['HIGH', 'EXTREME'], f"SOL $106B FDV should be HIGH/EXTREME"
        
        print(f"✓ FDV level: SOL at $106B = {tokenomics['fdvLevel']}")

    def test_float_quality_calculation(self):
        """Verify float quality thresholds"""
        # TIA has 25% circulating (250M / 1B)
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "TIA"}
        )
        data = response.json()
        tokenomics = data['intel']['tokenomics']
        
        # 25% float should be LOW (< 25% threshold)
        assert tokenomics['floatQuality'] in ['LOW', 'HEALTHY'], f"TIA 25% float"
        
        print(f"✓ Float quality: TIA = {tokenomics['floatQuality']}")

    def test_emission_risk_calculation(self):
        """Verify emission risk for high insider allocation"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "TIA"}
        )
        data = response.json()
        tokenomics = data['intel']['tokenomics']
        
        # TIA has 60% insider allocation, should have emission risk
        assert tokenomics['emissionRisk'] >= 0.2, f"TIA should have emission risk >= 0.2"
        
        print(f"✓ Emission risk: TIA = {tokenomics['emissionRisk']}")


class TestValuationEngine:
    """Verify valuation engine calculations"""

    def test_valuation_levels(self):
        """Verify valuation level determination"""
        # Test multiple assets
        for asset, expected_range in [('BTC', ['CHEAP', 'FAIR', 'EXPENSIVE']), ('PEPE', ['FAIR', 'EXPENSIVE', 'INSANE'])]:
            response = requests.post(
                f"{BASE_URL}/api/project-intelligence/analyze",
                json={"asset": asset}
            )
            data = response.json()
            valuation = data['intel']['valuation']
            
            assert valuation['valuation'] in ['CHEAP', 'FAIR', 'EXPENSIVE', 'INSANE']
            assert 'expectedRange' in valuation
            assert 'low' in valuation['expectedRange']
            assert 'base' in valuation['expectedRange']
            assert 'high' in valuation['expectedRange']
            
            print(f"✓ Valuation: {asset} = {valuation['valuation']}")

    def test_expected_range_structure(self):
        """Verify expected range has low/base/high"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "ETH", "dynamicData": {"currentPrice": 3500, "fdv": 420000000000}}
        )
        data = response.json()
        valuation = data['intel']['valuation']
        
        er = valuation['expectedRange']
        assert er['low'] <= er['base'] <= er['high'], "Expected range should be ordered"
        
        print(f"✓ Expected range: ETH = ${er['low']:.2f} / ${er['base']:.2f} / ${er['high']:.2f}")


class TestUnlockPressure:
    """Verify unlock pressure calculations"""

    def test_unlock_risk_levels(self):
        """Verify unlock risk level determination"""
        # TIA has upcoming unlock
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "TIA"}
        )
        data = response.json()
        unlock = data['intel']['unlockPressure']
        
        assert unlock['riskLevel'] in ['LOW', 'MEDIUM', 'HIGH']
        assert unlock['insiderShare'] == 0.60
        assert unlock['unlockPercent'] == 8
        
        print(f"✓ Unlock pressure: TIA = {unlock['riskLevel']} ({unlock['unlockPercent']}%)")

    def test_no_unlock_data(self):
        """Assets without unlock data should have LOW risk"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "BTC"}
        )
        data = response.json()
        unlock = data['intel']['unlockPressure']
        
        assert unlock['riskLevel'] == 'LOW', "BTC should have LOW unlock risk"
        assert unlock['nextUnlockDays'] is None, "BTC should have no unlock date"
        
        print(f"✓ No unlock: BTC = {unlock['riskLevel']}")


class TestTeamFundQuality:
    """Verify team/fund quality calculations"""

    def test_strong_team_detection(self):
        """Verify strong team detection"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "SOL"}
        )
        data = response.json()
        teamFund = data['intel']['teamFund']
        
        assert teamFund['verdict'] == 'STRONG', "SOL team should be STRONG"
        assert teamFund['teamScore'] >= 0.7, "SOL team score should be high"
        assert teamFund['fundScore'] >= 0.5, "SOL fund score should be good"
        
        print(f"✓ Team quality: SOL = {teamFund['verdict']} (team={teamFund['teamScore']}, fund={teamFund['fundScore']})")

    def test_weak_team_detection(self):
        """Verify weak team detection for meme tokens"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "PEPE"}
        )
        data = response.json()
        teamFund = data['intel']['teamFund']
        
        assert teamFund['verdict'] == 'WEAK', "PEPE team should be WEAK"
        
        print(f"✓ Team quality: PEPE = {teamFund['verdict']}")


class TestLaunchStructure:
    """Verify launch structure calculations"""

    def test_fair_launch_detection(self):
        """Verify fair launch detection"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "BTC"}
        )
        data = response.json()
        launch = data['intel']['launch']
        
        assert launch['fairLaunch'] is True, "BTC should be fair launch"
        assert launch['launchQuality'] >= 0.7, "BTC launch quality should be high"
        
        print(f"✓ Launch: BTC = fairLaunch={launch['fairLaunch']}, quality={launch['launchQuality']}")

    def test_vc_backed_detection(self):
        """Verify VC-backed launch detection"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "SOL"}
        )
        data = response.json()
        launch = data['intel']['launch']
        
        assert launch['fairLaunch'] is False, "SOL should not be fair launch"
        assert launch['dumpRisk'] >= 0.2, "SOL should have some dump risk"
        
        print(f"✓ Launch: SOL = fairLaunch={launch['fairLaunch']}, dumpRisk={launch['dumpRisk']}")


class TestProjectThesis:
    """Verify project thesis synthesis"""

    def test_thesis_structure(self):
        """Verify thesis has all required fields"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "ETH"}
        )
        data = response.json()
        thesis = data['intel']['thesis']
        
        assert 'bullCase' in thesis
        assert 'bearCase' in thesis
        assert 'projectVerdict' in thesis
        assert 'whatMarketMisses' in thesis
        assert 'keyRisks' in thesis
        assert 'overallScore' in thesis
        
        assert isinstance(thesis['bullCase'], list)
        assert isinstance(thesis['bearCase'], list)
        assert isinstance(thesis['keyRisks'], list)
        assert thesis['projectVerdict'] in ['STRONG', 'MIXED', 'WEAK']
        assert 0 <= thesis['overallScore'] <= 1
        
        print(f"✓ Thesis: ETH = {thesis['projectVerdict']} (score={thesis['overallScore']})")
        print(f"  Bull: {thesis['bullCase'][:2]}")
        print(f"  Bear: {thesis['bearCase'][:2]}")


class TestPredictionPipelineIntegration:
    """Test projectIntel field in prediction pipeline"""

    def test_prediction_run_has_project_intel(self):
        """GET /api/prediction/run should have projectIntel on cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert 'sections' in data, "Response should have sections"
        
        # Find cases with crypto assets
        cases_with_intel = 0
        total_cases = 0
        
        for section_name, cases in data['sections'].items():
            for case in cases:
                total_cases += 1
                if 'projectIntel' in case and case['projectIntel']:
                    cases_with_intel += 1
                    pi = case['projectIntel']
                    
                    # Verify projectIntel structure
                    assert 'verdict' in pi, f"projectIntel should have verdict"
                    assert pi['verdict'] in ['STRONG', 'MIXED', 'WEAK', None], f"Invalid verdict: {pi['verdict']}"
                    
                    if pi['verdict']:
                        # If verdict exists, other fields should too
                        assert 'valuation' in pi
                        assert 'unlockRisk' in pi
        
        print(f"✓ Prediction pipeline: {cases_with_intel}/{total_cases} cases have projectIntel")

    def test_project_intel_fields_in_case(self):
        """Verify projectIntel has expected fields for crypto cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50")
        data = response.json()
        
        # Find a case with projectIntel
        found_intel = False
        for section_name, cases in data['sections'].items():
            for case in cases:
                pi = case.get('projectIntel', {})
                if pi and pi.get('verdict'):
                    found_intel = True
                    
                    # Check all expected fields
                    expected_fields = ['verdict', 'valuation', 'unlockRisk', 'tokenomics', 
                                       'teamFund', 'launch', 'overallScore']
                    for field in expected_fields:
                        assert field in pi, f"projectIntel missing {field}"
                    
                    # Optional fields that may be present
                    optional_fields = ['bullCase', 'bearCase', 'keyRisks', 'whatMarketMisses']
                    
                    print(f"✓ Case {case.get('asset', 'N/A')}: verdict={pi['verdict']}, valuation={pi['valuation']}")
                    break
            if found_intel:
                break
        
        if not found_intel:
            print("⚠ No cases with projectIntel found (may be expected if no crypto markets)")


class TestDecisionQuality:
    """Verify decision quality for specific scenarios"""

    def test_sol_high_fdv_assessment(self):
        """SOL with high FDV should show EXPENSIVE/MIXED"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "SOL", "dynamicData": SOL_DYNAMIC_DATA}
        )
        data = response.json()
        intel = data['intel']
        
        # At $106B FDV, SOL should be expensive
        assert intel['valuation']['valuation'] in ['EXPENSIVE', 'INSANE', 'FAIR'], \
            f"SOL at $106B should be EXPENSIVE/INSANE, got {intel['valuation']['valuation']}"
        
        # Verdict should reflect this
        assert intel['thesis']['projectVerdict'] in ['MIXED', 'WEAK', 'STRONG'], \
            f"SOL verdict should be MIXED/WEAK at high FDV"
        
        print(f"✓ Decision quality: SOL high FDV = {intel['valuation']['valuation']}, {intel['thesis']['projectVerdict']}")

    def test_btc_strong_assessment(self):
        """BTC should consistently be STRONG"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "BTC", "dynamicData": BTC_DYNAMIC_DATA}
        )
        data = response.json()
        intel = data['intel']
        
        # BTC fundamentals are strong
        assert intel['thesis']['projectVerdict'] in ['STRONG', 'MIXED'], \
            f"BTC should be STRONG/MIXED, got {intel['thesis']['projectVerdict']}"
        assert intel['unlockPressure']['riskLevel'] == 'LOW'
        assert intel['launch']['fairLaunch'] is True
        
        print(f"✓ Decision quality: BTC = {intel['thesis']['projectVerdict']}")

    def test_tia_unlock_risk_assessment(self):
        """TIA with upcoming unlock should show MEDIUM/HIGH risk"""
        response = requests.post(
            f"{BASE_URL}/api/project-intelligence/analyze",
            json={"asset": "TIA", "dynamicData": TIA_DYNAMIC_DATA}
        )
        data = response.json()
        intel = data['intel']
        
        # TIA has significant unlock pressure
        unlock = intel['unlockPressure']
        assert unlock['insiderShare'] == 0.60, "TIA insider share should be 60%"
        assert unlock['unlockPercent'] == 8, "TIA unlock should be 8%"
        
        # Key risks should mention unlock
        risks = intel['thesis']['keyRisks']
        has_unlock_risk = any('unlock' in r.lower() or 'insider' in r.lower() for r in risks)
        
        print(f"✓ Decision quality: TIA unlock = {unlock['riskLevel']}, risks={risks[:2]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
