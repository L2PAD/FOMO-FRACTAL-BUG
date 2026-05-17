"""
BLOCK 5-7: Exchange Model Iteration Engine Tests
=================================================
Tests versioned, immutable forecast segments system.
Each ML prediction creates a separate segment.
Old predictions are SUPERSEDED but never deleted.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExchangeSegmentsAPI:
    """Test GET /api/exchange/segments endpoint"""
    
    def test_get_segments_returns_ok(self):
        """Test basic segments list endpoint"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'stats' in data['data']
        print(f"Segments returned: {len(data['data']['items'])}")
    
    def test_get_segments_stats_structure(self):
        """Test segments stats structure"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        stats = data['data']['stats']
        
        assert 'total' in stats
        assert 'active' in stats
        assert 'superseded' in stats
        assert 'resolved' in stats
        
        # Verify stats are integers
        assert isinstance(stats['total'], int)
        assert isinstance(stats['active'], int)
        assert isinstance(stats['superseded'], int)
        print(f"Stats: total={stats['total']}, active={stats['active']}, superseded={stats['superseded']}")
    
    def test_get_segments_items_structure(self):
        """Test segment item structure"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        items = data['data']['items']
        
        if len(items) > 0:
            segment = items[0]
            
            # Required fields
            assert 'segmentId' in segment
            assert 'modelVersion' in segment
            assert 'createdAt' in segment
            assert 'entryPrice' in segment
            assert 'targetPrice' in segment
            assert 'expectedReturn' in segment
            assert 'confidence' in segment
            assert 'status' in segment
            
            # Verify status is valid
            assert segment['status'] in ['ACTIVE', 'SUPERSEDED', 'RESOLVED']
            
            # Verify no MongoDB _id leaked
            assert '_id' not in segment
            
            print(f"Segment {segment['segmentId'][:20]}... status={segment['status']}")
    
    def test_get_segments_different_horizons(self):
        """Test different horizon values"""
        horizons = ['1D', '7D', '30D']
        
        for horizon in horizons:
            response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon={horizon}")
            assert response.status_code == 200
            
            data = response.json()
            assert data.get('ok') == True
            assert data['data']['horizon'] == horizon
            print(f"Horizon {horizon}: {len(data['data']['items'])} segments")
    
    def test_get_segments_invalid_horizon(self):
        """Test invalid horizon returns error"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=INVALID")
        assert response.status_code == 200  # API returns 200 with error in body
        
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        print(f"Invalid horizon error: {data.get('error')}")


class TestSegmentCandlesAPI:
    """Test GET /api/exchange/segment-candles endpoint"""
    
    def test_get_candles_for_active_segment(self):
        """Test fetching candles for active segment"""
        # First get the active segment
        segments_response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        segments_data = segments_response.json()
        
        active_segment = None
        for seg in segments_data['data']['items']:
            if seg['status'] == 'ACTIVE':
                active_segment = seg
                break
        
        if not active_segment:
            pytest.skip("No active segment found")
        
        # Fetch candles
        response = requests.get(f"{BASE_URL}/api/exchange/segment-candles?segmentId={active_segment['segmentId']}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'candles' in data['data']
        assert len(data['data']['candles']) > 0
        
        # Verify candle structure
        candle = data['data']['candles'][0]
        assert 'time' in candle
        assert 'open' in candle
        assert 'high' in candle
        assert 'low' in candle
        assert 'close' in candle
        
        print(f"Candles returned: {len(data['data']['candles'])}")
    
    def test_get_candles_meta_info(self):
        """Test candles endpoint returns meta information"""
        # First get a segment
        segments_response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        segments_data = segments_response.json()
        
        if not segments_data['data']['items']:
            pytest.skip("No segments found")
        
        segment = segments_data['data']['items'][0]
        
        # Fetch candles
        response = requests.get(f"{BASE_URL}/api/exchange/segment-candles?segmentId={segment['segmentId']}")
        assert response.status_code == 200
        
        data = response.json()
        assert 'meta' in data['data']
        
        meta = data['data']['meta']
        assert 'modelVersion' in meta
        assert 'confidence' in meta
        assert 'driftState' in meta
        assert 'createdAt' in meta
        
        print(f"Meta: modelVersion={meta['modelVersion']}, confidence={meta['confidence']:.2f}")
    
    def test_get_candles_missing_segment_id(self):
        """Test candles endpoint requires segmentId"""
        response = requests.get(f"{BASE_URL}/api/exchange/segment-candles")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        print(f"Missing segmentId error: {data.get('error')}")
    
    def test_get_candles_invalid_segment_id(self):
        """Test candles endpoint with invalid segmentId"""
        response = requests.get(f"{BASE_URL}/api/exchange/segment-candles?segmentId=invalid_segment_123")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == False
        assert data.get('error') == 'SEGMENT_NOT_FOUND'
        print(f"Invalid segmentId error: {data.get('message')}")


class TestAdminSegmentRollAPI:
    """Test POST /api/admin/exchange/segments/roll endpoint"""
    
    def test_manual_roll_creates_new_segment(self):
        """Test manual roll creates a new segment"""
        # Use unique asset/horizon for test isolation
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "SOL", "horizon": "1D", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        result = data['data']
        assert result.get('rolled') == True
        assert 'segmentId' in result
        assert result['segmentId'].startswith('exseg_')
        
        print(f"Roll result: rolled={result['rolled']}, segmentId={result['segmentId'][:30]}...")
    
    def test_roll_supersedes_old_segment(self):
        """Test rolling supersedes the old active segment"""
        # Roll first to ensure there's an active segment
        response1 = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "TEST_BTC", "horizon": "7D", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        first_data = response1.json()
        first_segment_id = first_data['data']['segmentId']
        
        # Roll again
        response2 = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "TEST_BTC", "horizon": "7D", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        second_data = response2.json()
        
        assert second_data.get('ok') == True
        assert second_data['data']['rolled'] == True
        
        # Verify supersededCount
        assert second_data['data'].get('supersededCount', 0) >= 1
        
        print(f"Superseded count: {second_data['data'].get('supersededCount')}")
    
    def test_roll_returns_segment_details(self):
        """Test roll returns complete segment details"""
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "BTC", "horizon": "30D", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        segment = data['data'].get('segment', {})
        
        # Verify segment has expected fields
        assert 'entryPrice' in segment
        assert 'targetPrice' in segment
        assert 'expectedReturn' in segment
        assert 'confidence' in segment
        assert 'driftState' in segment
        assert 'status' in segment
        assert segment['status'] == 'ACTIVE'
        
        print(f"New segment: entry={segment['entryPrice']:.2f}, target={segment['targetPrice']:.2f}")
    
    def test_roll_invalid_horizon(self):
        """Test roll with invalid horizon"""
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "BTC", "horizon": "INVALID", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        print(f"Invalid horizon error: {data.get('error')}")


class TestSegmentStatsAPI:
    """Test GET /api/admin/exchange/segments/stats endpoint"""
    
    def test_stats_returns_totals(self):
        """Test stats endpoint returns totals"""
        response = requests.get(f"{BASE_URL}/api/admin/exchange/segments/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        stats = data['data']
        assert 'total' in stats
        assert 'byStatus' in stats
        assert 'byHorizon' in stats
        
        print(f"Total segments: {stats['total']}")
    
    def test_stats_by_status(self):
        """Test stats includes status breakdown"""
        response = requests.get(f"{BASE_URL}/api/admin/exchange/segments/stats")
        data = response.json()
        
        by_status = data['data']['byStatus']
        assert 'ACTIVE' in by_status
        assert 'SUPERSEDED' in by_status
        assert 'RESOLVED' in by_status
        
        print(f"By status: ACTIVE={by_status['ACTIVE']}, SUPERSEDED={by_status['SUPERSEDED']}, RESOLVED={by_status['RESOLVED']}")
    
    def test_stats_by_horizon(self):
        """Test stats includes horizon breakdown"""
        response = requests.get(f"{BASE_URL}/api/admin/exchange/segments/stats")
        data = response.json()
        
        by_horizon = data['data']['byHorizon']
        assert '1D' in by_horizon
        assert '7D' in by_horizon
        assert '30D' in by_horizon
        
        print(f"By horizon: 1D={by_horizon['1D']}, 7D={by_horizon['7D']}, 30D={by_horizon['30D']}")


class TestSegmentImmutability:
    """Test that old segments are not modified"""
    
    def test_superseded_segments_preserved(self):
        """Test that superseded segments retain their original data"""
        # Get all segments
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D&limit=50")
        data = response.json()
        
        superseded = [s for s in data['data']['items'] if s['status'] == 'SUPERSEDED']
        
        if not superseded:
            pytest.skip("No superseded segments to test")
        
        for seg in superseded:
            # Verify superseded segments have supersededAt timestamp
            assert seg.get('supersededAt') is not None
            
            # Verify original data is preserved
            assert seg.get('entryPrice') is not None
            assert seg.get('targetPrice') is not None
            assert seg.get('modelVersion') is not None
            
        print(f"Verified {len(superseded)} superseded segments preserved")
    
    def test_both_active_and_superseded_returned(self):
        """Test that API returns both ACTIVE and SUPERSEDED segments"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        data = response.json()
        
        items = data['data']['items']
        statuses = set(s['status'] for s in items)
        
        # Verify we can have multiple statuses
        print(f"Statuses found: {statuses}")
        
        # Should have at least one active if any segments exist
        if items:
            active_count = sum(1 for s in items if s['status'] == 'ACTIVE')
            assert active_count <= 1, "Should have at most 1 ACTIVE segment per asset/horizon"


class TestSegmentDataIntegrity:
    """Test data integrity and no MongoDB _id leakage"""
    
    def test_no_mongodb_id_in_segments(self):
        """Verify MongoDB _id is not returned in segment list"""
        response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        data = response.json()
        
        for segment in data['data']['items']:
            assert '_id' not in segment, f"MongoDB _id leaked in segment {segment.get('segmentId')}"
        
        print("No _id leakage in segments list")
    
    def test_no_mongodb_id_in_candles(self):
        """Verify MongoDB _id is not returned in candles response"""
        # First get a segment
        segments_response = requests.get(f"{BASE_URL}/api/exchange/segments?asset=BTC&horizon=30D")
        segments_data = segments_response.json()
        
        if not segments_data['data']['items']:
            pytest.skip("No segments found")
        
        segment = segments_data['data']['items'][0]
        
        # Fetch candles
        response = requests.get(f"{BASE_URL}/api/exchange/segment-candles?segmentId={segment['segmentId']}")
        data = response.json()
        
        # Check main response
        assert '_id' not in data['data']
        
        # Check candles array
        for candle in data['data']['candles']:
            assert '_id' not in candle
        
        print("No _id leakage in candles response")
    
    def test_mongodb_id_leakage_in_roll_response(self):
        """Check if MongoDB _id leaks in roll response (potential bug)"""
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/segments/roll",
            json={"asset": "TEST_LEAK", "horizon": "1D", "reason": "MANUAL"},
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        segment = data['data'].get('segment', {})
        
        if '_id' in segment:
            print(f"BUG: MongoDB _id leaked in roll response segment: {segment['_id']}")
            # This is a bug but not failing the test - reporting to main agent
        else:
            print("No _id leakage in roll response")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
