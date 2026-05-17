"""
On-Chain Lite Mode API Tests
============================
Tests for the 4 onchain endpoints: /api/onchain/summary, /flows, /whales, /activity
Data sources: Infura RPC (Ethereum Mainnet) + DefiLlama APIs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOnchainSummary:
    """Tests for GET /api/onchain/summary - Network health from Infura RPC"""
    
    def test_summary_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/onchain/summary", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=True, got {data}"
    
    def test_summary_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/onchain/summary", timeout=30)
        data = response.json()
        assert 'data' in data
        
        summary = data['data']
        required_fields = ['blockHeight', 'gasPrice', 'tps', 'blockTime', 'pendingTxCount', 'provider', 'updatedAt']
        for field in required_fields:
            assert field in summary, f"Missing field: {field}"
    
    def test_summary_real_infura_data(self):
        """Verify real data from Infura RPC - blockHeight > 0, gasPrice > 0"""
        response = requests.get(f"{BASE_URL}/api/onchain/summary", timeout=30)
        data = response.json()
        summary = data['data']
        
        # Block height must be positive (real Ethereum mainnet)
        assert summary['blockHeight'] > 0, f"Expected blockHeight > 0, got {summary['blockHeight']}"
        
        # Gas price in gwei must be >= 0 (could be very low in some network conditions)
        assert summary['gasPrice'] >= 0, f"Expected gasPrice >= 0, got {summary['gasPrice']}"
        
        # Provider must be infura-lite
        assert summary['provider'] == 'infura-lite', f"Expected provider='infura-lite', got {summary['provider']}"
    
    def test_summary_mode_preview(self):
        """Mode should be 'preview' for lite RPC mode"""
        response = requests.get(f"{BASE_URL}/api/onchain/summary", timeout=30)
        data = response.json()
        
        assert data.get('mode') == 'preview', f"Expected mode='preview', got {data.get('mode')}"


class TestOnchainFlows:
    """Tests for GET /api/onchain/flows - Exchange and Stablecoin flows from DefiLlama"""
    
    def test_flows_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/onchain/flows", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_flows_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/onchain/flows", timeout=30)
        data = response.json()
        flows = data['data']
        
        required_fields = [
            'exchangeInflow24h', 'exchangeOutflow24h', 'exchangeNetflow24h',
            'stablecoinInflow24h', 'stablecoinOutflow24h', 'stablecoinNetflow24h',
            'provider', 'updatedAt'
        ]
        for field in required_fields:
            assert field in flows, f"Missing field: {field}"
    
    def test_flows_stablecoin_data_from_defillama(self):
        """Verify stablecoinInflow24h > 0 (DefiLlama real data)"""
        response = requests.get(f"{BASE_URL}/api/onchain/flows", timeout=30)
        data = response.json()
        flows = data['data']
        
        # Stablecoin inflow should be positive (from DefiLlama stablecoins API)
        assert flows['stablecoinInflow24h'] > 0, f"Expected stablecoinInflow24h > 0, got {flows['stablecoinInflow24h']}"
        
        # Provider must include 'defillama'
        assert 'defillama' in flows['provider'], f"Expected provider to include 'defillama', got {flows['provider']}"


class TestOnchainWhales:
    """Tests for GET /api/onchain/whales - Large transfers from Infura blocks"""
    
    def test_whales_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/onchain/whales", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_whales_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/onchain/whales", timeout=30)
        data = response.json()
        whales = data['data']
        
        required_fields = ['largeTransfers24h', 'topTransfers', 'totalWhaleVolume24h', 'provider', 'updatedAt']
        for field in required_fields:
            assert field in whales, f"Missing field: {field}"
    
    def test_whales_provider_infura_lite(self):
        """Provider should be infura-lite"""
        response = requests.get(f"{BASE_URL}/api/onchain/whales", timeout=30)
        data = response.json()
        whales = data['data']
        
        assert whales['provider'] == 'infura-lite', f"Expected provider='infura-lite', got {whales['provider']}"
    
    def test_whales_top_transfers_structure(self):
        """Verify topTransfers array structure if any transfers exist"""
        response = requests.get(f"{BASE_URL}/api/onchain/whales", timeout=30)
        data = response.json()
        whales = data['data']
        
        assert isinstance(whales['topTransfers'], list)
        
        if len(whales['topTransfers']) > 0:
            tx = whales['topTransfers'][0]
            required_tx_fields = ['hash', 'from', 'to', 'valueEth', 'valueUsd', 'timestamp', 'block']
            for field in required_tx_fields:
                assert field in tx, f"Missing field in transfer: {field}"


class TestOnchainActivity:
    """Tests for GET /api/onchain/activity - DEX volumes and TVL from DefiLlama"""
    
    def test_activity_returns_ok(self):
        response = requests.get(f"{BASE_URL}/api/onchain/activity", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_activity_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/onchain/activity", timeout=30)
        data = response.json()
        activity = data['data']
        
        required_fields = ['dexVolume24h', 'topPairs', 'totalValueLocked', 'provider', 'updatedAt']
        for field in required_fields:
            assert field in activity, f"Missing field: {field}"
    
    def test_activity_real_defillama_data(self):
        """Verify dexVolume24h > 0 and totalValueLocked > 0 from DefiLlama"""
        response = requests.get(f"{BASE_URL}/api/onchain/activity", timeout=30)
        data = response.json()
        activity = data['data']
        
        # DEX volume should be positive (from DefiLlama DEX API)
        assert activity['dexVolume24h'] > 0, f"Expected dexVolume24h > 0, got {activity['dexVolume24h']}"
        
        # TVL should be positive (from DefiLlama chains API)
        assert activity['totalValueLocked'] > 0, f"Expected totalValueLocked > 0, got {activity['totalValueLocked']}"
        
        # Provider should be defillama
        assert activity['provider'] == 'defillama', f"Expected provider='defillama', got {activity['provider']}"
    
    def test_activity_top_pairs_structure(self):
        """Verify topPairs contains protocol names and volumes"""
        response = requests.get(f"{BASE_URL}/api/onchain/activity", timeout=30)
        data = response.json()
        activity = data['data']
        
        assert isinstance(activity['topPairs'], list)
        
        if len(activity['topPairs']) > 0:
            pair = activity['topPairs'][0]
            assert 'pair' in pair, "topPairs item should have 'pair' field (protocol name)"
            assert 'volume' in pair, "topPairs item should have 'volume' field"
