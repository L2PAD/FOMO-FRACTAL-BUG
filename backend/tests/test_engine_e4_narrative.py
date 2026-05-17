"""
E4 Engine Narrative Service — Backend Tests
============================================
Tests the rule-based narrative generator for the Engine tab.
Verifies:
  - narrative field in /api/engine/context response
  - 7 sections: summary, regime, setup, flow, probability, risk, action
  - Each section has non-empty content
  - Versions: narrative.version = '4.4', meta.version = '4.4'
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEngineNarrativeE4:
    """E4: Engine Narrative Service tests"""

    @pytest.fixture(scope="class")
    def engine_response(self):
        """Fetch engine context once for all tests in this class"""
        response = requests.get(f"{BASE_URL}/api/engine/context", timeout=60)
        assert response.status_code == 200, f"API returned {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"API returned error: {data}"
        return data

    def test_narrative_field_exists(self, engine_response):
        """Verify narrative field exists in response"""
        assert "narrative" in engine_response, "Missing 'narrative' field in response"
        narrative = engine_response["narrative"]
        assert narrative is not None, "narrative field is None"

    def test_narrative_has_sections_array(self, engine_response):
        """Verify narrative.sections is an array"""
        narrative = engine_response["narrative"]
        assert "sections" in narrative, "Missing 'sections' in narrative"
        assert isinstance(narrative["sections"], list), "sections is not an array"

    def test_narrative_has_7_sections(self, engine_response):
        """Verify exactly 7 sections exist"""
        sections = engine_response["narrative"]["sections"]
        assert len(sections) == 7, f"Expected 7 sections, got {len(sections)}"

    def test_narrative_section_ids(self, engine_response):
        """Verify all required section IDs are present"""
        required_ids = ["summary", "regime", "setup", "flow", "probability", "risk", "action"]
        sections = engine_response["narrative"]["sections"]
        section_ids = [s.get("id") for s in sections]
        
        for req_id in required_ids:
            assert req_id in section_ids, f"Missing section: {req_id}"

    def test_each_section_has_content(self, engine_response):
        """Verify each section has non-empty content"""
        sections = engine_response["narrative"]["sections"]
        
        for section in sections:
            section_id = section.get("id", "unknown")
            assert "content" in section, f"Section '{section_id}' missing content field"
            content = section.get("content", "")
            assert content and len(content) > 10, f"Section '{section_id}' has empty/short content"
            assert "title" in section, f"Section '{section_id}' missing title field"

    def test_narrative_has_full_text(self, engine_response):
        """Verify narrative.full_text exists and is non-empty"""
        narrative = engine_response["narrative"]
        assert "full_text" in narrative, "Missing full_text in narrative"
        full_text = narrative.get("full_text", "")
        assert len(full_text) > 100, f"full_text too short: {len(full_text)} chars"

    def test_narrative_has_generated_at(self, engine_response):
        """Verify narrative.generated_at exists"""
        narrative = engine_response["narrative"]
        assert "generated_at" in narrative, "Missing generated_at in narrative"
        assert narrative["generated_at"], "generated_at is empty"

    def test_narrative_version_44(self, engine_response):
        """Verify narrative.version is '4.4'"""
        narrative = engine_response["narrative"]
        assert "version" in narrative, "Missing version in narrative"
        assert narrative["version"] == "4.4", f"Expected narrative version '4.4', got '{narrative['version']}'"

    def test_meta_version_44(self, engine_response):
        """Verify meta.version is '4.4'"""
        meta = engine_response.get("meta", {})
        assert "version" in meta, "Missing version in meta"
        assert meta["version"] == "4.4", f"Expected meta version '4.4', got '{meta['version']}'"

    def test_summary_section_content(self, engine_response):
        """Verify summary section has expected structure"""
        sections = engine_response["narrative"]["sections"]
        summary = next((s for s in sections if s.get("id") == "summary"), None)
        
        assert summary is not None, "Summary section not found"
        assert summary.get("title") == "Executive Summary", f"Summary title: {summary.get('title')}"
        content = summary.get("content", "")
        # Summary should mention key elements
        assert any(word in content.lower() for word in ["market", "composite", "confidence", "setup"]), \
            f"Summary missing key terms: {content[:200]}"

    def test_regime_section_content(self, engine_response):
        """Verify regime section has expected structure"""
        sections = engine_response["narrative"]["sections"]
        regime = next((s for s in sections if s.get("id") == "regime"), None)
        
        assert regime is not None, "Regime section not found"
        assert regime.get("title") == "Regime Analysis", f"Regime title: {regime.get('title')}"
        content = regime.get("content", "")
        # Regime should mention status/confidence
        assert any(word in content.lower() for word in ["status", "confidence", "trend", "regime"]), \
            f"Regime missing key terms: {content[:200]}"

    def test_action_section_content(self, engine_response):
        """Verify action section has expected structure"""
        sections = engine_response["narrative"]["sections"]
        action = next((s for s in sections if s.get("id") == "action"), None)
        
        assert action is not None, "Action section not found"
        assert action.get("title") == "Action Plan", f"Action title: {action.get('title')}"
        content = action.get("content", "")
        # Action should mention position/recommendation
        assert any(word in content.lower() for word in ["position", "upgrade", "action", "waiting", "recommends"]), \
            f"Action missing key terms: {content[:200]}"


class TestNarrativeSectionTitles:
    """Verify each section has correct title"""
    
    @pytest.fixture(scope="class")
    def sections(self):
        """Fetch sections once"""
        response = requests.get(f"{BASE_URL}/api/engine/context", timeout=60)
        return response.json().get("narrative", {}).get("sections", [])
    
    def test_summary_title(self, sections):
        s = next((x for x in sections if x.get("id") == "summary"), {})
        assert s.get("title") == "Executive Summary"
    
    def test_regime_title(self, sections):
        s = next((x for x in sections if x.get("id") == "regime"), {})
        assert s.get("title") == "Regime Analysis"
    
    def test_setup_title(self, sections):
        s = next((x for x in sections if x.get("id") == "setup"), {})
        assert s.get("title") == "Setup Intelligence"
    
    def test_flow_title(self, sections):
        s = next((x for x in sections if x.get("id") == "flow"), {})
        assert s.get("title") == "Flow & Liquidity"
    
    def test_probability_title(self, sections):
        s = next((x for x in sections if x.get("id") == "probability"), {})
        assert s.get("title") == "Probability Assessment"
    
    def test_risk_title(self, sections):
        s = next((x for x in sections if x.get("id") == "risk"), {})
        assert s.get("title") == "Risk Factors"
    
    def test_action_title(self, sections):
        s = next((x for x in sections if x.get("id") == "action"), {})
        assert s.get("title") == "Action Plan"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
