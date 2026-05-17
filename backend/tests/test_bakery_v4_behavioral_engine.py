"""
Bakery v4 Behavioral Engine Tests — NEW DECISION MECHANICS

Tests for 5 new behavioral mechanics:
1. BAKER DNA (style, marketRole, edge, weakness)
2. COPY STRATEGY (how to copy this baker)
3. ALPHA TYPE (EARLY/MOMENTUM/EXIT/NOISE)
4. WHERE HE MAKES MONEY (sectorPerformance)
5. TRUST MODE (YES/WEAK/NO)
6. MARKET CONTROL (sector control status)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBakeryLeaderboardV4NewFields:
    """Tests for GET /api/bakery — v4 new behavioral fields"""
    
    def test_bakers_have_dna_field(self):
        """P0: Bakers have dna field with style, marketRole, edge, weakness"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert len(data.get("bakers", [])) > 0
        
        baker = data["bakers"][0]
        assert "dna" in baker, "Missing 'dna' field"
        
        dna = baker["dna"]
        assert "style" in dna, "dna missing 'style'"
        assert "marketRole" in dna, "dna missing 'marketRole'"
        assert "edge" in dna, "dna missing 'edge'"
        assert "weakness" in dna, "dna missing 'weakness'"
        
        # Validate style values
        valid_styles = ["Early Hunter", "Momentum Rider", "Exit Caller", "Narrative Creator"]
        assert dna["style"] in valid_styles, f"Invalid style: {dna['style']}"
        
        print(f"PASS: Baker '{baker['name']}' DNA - style={dna['style']}, edge={dna['edge']}, weakness={dna['weakness']}")
    
    def test_bakers_have_alpha_type(self):
        """P0: Bakers have alphaType field (EARLY/MOMENTUM/EXIT/NOISE)"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        alpha_types_found = set()
        for baker in data.get("bakers", []):
            assert "alphaType" in baker, f"Baker {baker['name']} missing 'alphaType'"
            assert baker["alphaType"] in ["EARLY", "MOMENTUM", "EXIT", "NOISE"], \
                f"Invalid alphaType: {baker['alphaType']}"
            alpha_types_found.add(baker["alphaType"])
        
        print(f"PASS: alphaType values found: {alpha_types_found}")
    
    def test_bakers_have_trust_mode(self):
        """P0: Bakers have trustMode field (YES/WEAK/NO)"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        trust_modes_found = set()
        for baker in data.get("bakers", []):
            assert "trustMode" in baker, f"Baker {baker['name']} missing 'trustMode'"
            assert baker["trustMode"] in ["YES", "WEAK", "NO"], \
                f"Invalid trustMode: {baker['trustMode']}"
            trust_modes_found.add(baker["trustMode"])
        
        print(f"PASS: trustMode values found: {trust_modes_found}")
    
    def test_bakers_have_sector_performance(self):
        """P0: Bakers have sectorPerformance field (WHERE HE MAKES MONEY)"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        bakers_with_sector_perf = 0
        for baker in data.get("bakers", []):
            assert "sectorPerformance" in baker, f"Baker {baker['name']} missing 'sectorPerformance'"
            assert isinstance(baker["sectorPerformance"], dict)
            
            if baker["sectorPerformance"]:
                bakers_with_sector_perf += 1
                # Validate sector keys
                valid_sectors = {"AI", "MEME", "DEFI", "INFRA", "MARKET"}
                for sec in baker["sectorPerformance"].keys():
                    assert sec in valid_sectors, f"Invalid sector: {sec}"
                # Validate values are numbers
                for sec, val in baker["sectorPerformance"].items():
                    assert isinstance(val, (int, float)), f"sectorPerformance[{sec}] should be number"
        
        print(f"PASS: {bakers_with_sector_perf}/{len(data['bakers'])} bakers have sector performance data")
    
    def test_bakers_have_copy_strategy(self):
        """P0: Bakers have copyStrategy field (list of steps)"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        for baker in data.get("bakers", []):
            assert "copyStrategy" in baker, f"Baker {baker['name']} missing 'copyStrategy'"
            assert isinstance(baker["copyStrategy"], list)
            assert len(baker["copyStrategy"]) > 0, f"Baker {baker['name']} has empty copyStrategy"
            
            # Validate steps are strings
            for step in baker["copyStrategy"]:
                assert isinstance(step, str)
        
        sample = data["bakers"][0]
        print(f"PASS: copyStrategy for '{sample['name']}': {sample['copyStrategy'][:2]}...")
    
    def test_market_control_in_response(self):
        """P0: /api/bakery returns marketControl with sector control status"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "marketControl" in data, "Missing 'marketControl' in response"
        
        mc = data["marketControl"]
        assert isinstance(mc, dict)
        
        # Should have sector keys
        expected_sectors = {"AI", "MEME", "DEFI", "INFRA"}
        assert set(mc.keys()) == expected_sectors, f"marketControl keys: {mc.keys()}"
        
        # Validate structure
        for sector, control in mc.items():
            assert "leader" in control, f"marketControl[{sector}] missing 'leader'"
            assert "topBakers" in control, f"marketControl[{sector}] missing 'topBakers'"
            assert "status" in control, f"marketControl[{sector}] missing 'status'"
            assert "bakerCount" in control, f"marketControl[{sector}] missing 'bakerCount'"
            
            # Validate status values
            valid_statuses = ["controlled", "building", "fragmented", "no leader"]
            assert control["status"] in valid_statuses, f"Invalid status: {control['status']}"
        
        print(f"PASS: marketControl has {len(mc)} sectors")
        for sec, ctrl in mc.items():
            leader_name = ctrl["leader"]["name"] if ctrl["leader"] else "none"
            print(f"  {sec}: {ctrl['status']} (leader: {leader_name}, count: {ctrl['bakerCount']})")


class TestBakerDetailV4NewFields:
    """Tests for GET /api/bakery/:slug — v4 new behavioral fields"""
    
    def test_detail_has_dna_block(self):
        """P0: Baker detail has dna block with style, marketRole, edge, weakness"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        baker = data.get("baker", {})
        
        assert "dna" in baker, "Baker missing 'dna'"
        dna = baker["dna"]
        
        assert "style" in dna
        assert "marketRole" in dna
        assert "edge" in dna
        assert "weakness" in dna
        
        print(f"PASS: cz_binance DNA - style={dna['style']}, marketRole={dna['marketRole']}, edge={dna['edge']}, weakness={dna['weakness']}")
    
    def test_detail_has_copy_strategy_in_root(self):
        """P0: Baker detail has copyStrategy in response root (not just in baker object)"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        # copyStrategy should be in root for detail page
        assert "copyStrategy" in data, "Missing 'copyStrategy' in response root"
        assert isinstance(data["copyStrategy"], list)
        assert len(data["copyStrategy"]) > 0
        
        print(f"PASS: copyStrategy in root: {data['copyStrategy']}")
    
    def test_detail_has_alpha_type(self):
        """P0: Baker detail has alphaType"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        baker = data.get("baker", {})
        assert "alphaType" in baker
        assert baker["alphaType"] in ["EARLY", "MOMENTUM", "EXIT", "NOISE"]
        
        print(f"PASS: cz_binance alphaType = {baker['alphaType']}")
    
    def test_detail_has_trust_mode(self):
        """P0: Baker detail has trustMode"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        baker = data.get("baker", {})
        assert "trustMode" in baker
        assert baker["trustMode"] in ["YES", "WEAK", "NO"]
        
        print(f"PASS: cz_binance trustMode = {baker['trustMode']}")
    
    def test_detail_has_sector_performance(self):
        """P0: Baker detail has sectorPerformance (WHERE HE MAKES MONEY)"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        baker = data.get("baker", {})
        assert "sectorPerformance" in baker
        assert isinstance(baker["sectorPerformance"], dict)
        
        print(f"PASS: cz_binance sectorPerformance = {baker['sectorPerformance']}")
    
    def test_vitalikbuterin_v4_fields(self):
        """Test vitalikbuterin has all v4 fields"""
        response = requests.get(f"{BASE_URL}/api/bakery/vitalikbuterin")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        baker = data.get("baker", {})
        
        # All v4 fields
        assert "dna" in baker
        assert "alphaType" in baker
        assert "trustMode" in baker
        assert "sectorPerformance" in baker
        assert "copyStrategy" in data  # in root
        
        print(f"PASS: vitalikbuterin - alphaType={baker['alphaType']}, trustMode={baker['trustMode']}")
        print(f"  DNA: {baker['dna']}")


class TestActiveMoneyFlowV4:
    """Tests for GET /api/bakery/active — still works with v4"""
    
    def test_active_endpoint_works(self):
        """P0: /api/bakery/active still returns flows"""
        response = requests.get(f"{BASE_URL}/api/bakery/active")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "flows" in data
        assert isinstance(data["flows"], list)
        
        if data["flows"]:
            flow = data["flows"][0]
            assert "slug" in flow
            assert "name" in flow
            assert "role" in flow
            assert "sector" in flow
            assert "phase" in flow
            assert "context" in flow
        
        print(f"PASS: /api/bakery/active returns {len(data['flows'])} flows")


class TestDNAStyleClassification:
    """Tests for DNA style classification logic"""
    
    def test_dna_styles_distribution(self):
        """Check distribution of DNA styles across bakers"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        style_counts = {}
        for baker in data.get("bakers", []):
            style = baker.get("dna", {}).get("style", "Unknown")
            style_counts[style] = style_counts.get(style, 0) + 1
        
        print(f"PASS: DNA style distribution: {style_counts}")
    
    def test_dna_edge_values(self):
        """Check DNA edge values"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        edge_counts = {}
        for baker in data.get("bakers", []):
            edge = baker.get("dna", {}).get("edge", "Unknown")
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
        
        valid_edges = {"Timing", "Narrative Creation", "Distribution", "Consistency", "Network"}
        for edge in edge_counts.keys():
            assert edge in valid_edges, f"Invalid edge: {edge}"
        
        print(f"PASS: DNA edge distribution: {edge_counts}")


class TestAlphaTypeClassification:
    """Tests for ALPHA TYPE classification"""
    
    def test_alpha_type_distribution(self):
        """Check distribution of alpha types"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        alpha_counts = {}
        for baker in data.get("bakers", []):
            alpha = baker.get("alphaType", "Unknown")
            alpha_counts[alpha] = alpha_counts.get(alpha, 0) + 1
        
        print(f"PASS: Alpha type distribution: {alpha_counts}")
    
    def test_early_alpha_has_good_timing(self):
        """EARLY alpha bakers should have early/mid entry"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        early_alphas = [b for b in data.get("bakers", []) if b.get("alphaType") == "EARLY"]
        
        for baker in early_alphas:
            # EARLY alpha should not have LATE/EXIT entry
            assert baker["entry"] in ["EARLY", "MID"], \
                f"EARLY alpha {baker['name']} has {baker['entry']} entry"
        
        print(f"PASS: {len(early_alphas)} EARLY alpha bakers all have EARLY/MID entry")


class TestTrustModeClassification:
    """Tests for TRUST MODE classification"""
    
    def test_trust_mode_distribution(self):
        """Check distribution of trust modes"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        trust_counts = {}
        for baker in data.get("bakers", []):
            trust = baker.get("trustMode", "Unknown")
            trust_counts[trust] = trust_counts.get(trust, 0) + 1
        
        print(f"PASS: Trust mode distribution: {trust_counts}")


class TestMarketControlLogic:
    """Tests for MARKET CONTROL logic"""
    
    def test_market_control_status_logic(self):
        """Verify market control status logic"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        mc = data.get("marketControl", {})
        
        for sector, control in mc.items():
            count = control["bakerCount"]
            status = control["status"]
            
            # Verify status logic
            if count == 0:
                assert status == "no leader"
            elif count >= 3 and control.get("leader"):
                # Could be controlled or building
                assert status in ["controlled", "building", "fragmented"]
            
            print(f"  {sector}: count={count}, status={status}")
        
        print("PASS: Market control status logic verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
