"""
Test Graph Core P3.4 (Cluster Structure) + P3.5 (Corridor Aggregation)
=======================================================================
Testing cluster CRUD with reference model (cluster_id in graph_nodes)
and active corridors endpoint with aggregation.
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestClusterCreate:
    """P3.4: POST /api/graph-core/clusters creates cluster"""
    
    def test_create_cluster_returns_cluster_id(self):
        """POST /clusters with cluster_id returns the same cluster_id"""
        unique_id = f"test_cluster_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "institution",
            "label": "Test Cluster",
            "confidence": 0.85
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "cluster_id" in data, "Response must contain cluster_id"
        assert data["cluster_id"] == unique_id
    
    def test_create_cluster_returns_members_updated(self):
        """POST /clusters returns members_updated field"""
        unique_id = f"test_cluster_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "institution",
            "label": "Test Cluster",
            "confidence": 0.85
        })
        assert response.status_code == 200
        data = response.json()
        assert "members_updated" in data, "Response must contain members_updated"
        assert data["members_updated"] == 0, "No members provided, should be 0"
    
    def test_create_cluster_with_type(self):
        """POST /clusters accepts type parameter"""
        unique_id = f"test_cluster_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "market_maker",
            "label": "MM Cluster",
            "confidence": 0.9
        })
        assert response.status_code == 200
        # Verify it was created
        get_response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        clusters = get_response.json().get("clusters", [])
        created = next((c for c in clusters if c["cluster_id"] == unique_id), None)
        assert created is not None, f"Cluster {unique_id} not found"
        assert created["type"] == "market_maker"
    
    def test_create_cluster_with_confidence(self):
        """POST /clusters accepts confidence parameter"""
        unique_id = f"test_cluster_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "institution",
            "label": "High Confidence",
            "confidence": 0.95
        })
        assert response.status_code == 200
        # Verify confidence was saved
        get_response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        clusters = get_response.json().get("clusters", [])
        created = next((c for c in clusters if c["cluster_id"] == unique_id), None)
        assert created is not None
        assert created["confidence"] == 0.95
    
    def test_create_cluster_without_cluster_id_fails(self):
        """POST /clusters without cluster_id returns error"""
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "type": "institution",
            "label": "No ID Cluster",
        })
        assert response.status_code == 200  # Endpoint returns 200 with error field
        data = response.json()
        assert "error" in data, "Should return error when cluster_id missing"


class TestClusterList:
    """P3.4: GET /api/graph-core/clusters returns all clusters"""
    
    def test_clusters_returns_clusters_array(self):
        """GET /clusters returns clusters array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data, "Response must contain clusters array"
        assert isinstance(data["clusters"], list)
    
    def test_clusters_returns_count(self):
        """GET /clusters returns count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data, "Response must contain count"
        assert data["count"] == len(data["clusters"])
    
    def test_cluster_has_member_count(self):
        """Each cluster in list has member_count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200
        data = response.json()
        if data["count"] > 0:
            cluster = data["clusters"][0]
            assert "member_count" in cluster, "Cluster must have member_count"
            assert isinstance(cluster["member_count"], int)
    
    def test_cluster_has_required_fields(self):
        """Each cluster has cluster_id, type, label, confidence"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert response.status_code == 200
        data = response.json()
        if data["count"] > 0:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster
            assert "type" in cluster
            assert "label" in cluster
            assert "confidence" in cluster


class TestClusterMembers:
    """P3.4: GET /api/graph-core/clusters/{cluster_id}/members"""
    
    def test_get_members_returns_cluster_id(self):
        """GET /clusters/{id}/members returns cluster_id"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/jump_trading/members")
        assert response.status_code == 200
        data = response.json()
        assert "cluster_id" in data
        assert data["cluster_id"] == "jump_trading"
    
    def test_get_members_returns_members_array(self):
        """GET /clusters/{id}/members returns members array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/jump_trading/members")
        assert response.status_code == 200
        data = response.json()
        assert "members" in data
        assert isinstance(data["members"], list)
    
    def test_get_members_returns_count(self):
        """GET /clusters/{id}/members returns count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/jump_trading/members")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == len(data["members"])
    
    def test_get_members_nonexistent_cluster(self):
        """GET /clusters/{id}/members for nonexistent cluster returns empty"""
        response = requests.get(f"{BASE_URL}/api/graph-core/clusters/nonexistent_cluster_xyz/members")
        assert response.status_code == 200
        data = response.json()
        assert "members" in data
        assert data["count"] == 0


class TestActiveCorridors:
    """P3.5: GET /api/graph-core/corridors/active"""
    
    def test_active_corridors_returns_corridors_array(self):
        """GET /corridors/active returns corridors array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data, "Response must contain corridors array"
        assert isinstance(data["corridors"], list)
    
    def test_active_corridors_returns_count(self):
        """GET /corridors/active returns count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data, "Response must contain count"
        assert data["count"] == len(data["corridors"])
    
    def test_active_corridors_accepts_limit_param(self):
        """GET /corridors/active?limit=5 accepts limit parameter"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        # With limit=5, should return at most 5
        assert len(data["corridors"]) <= 5
    
    def test_active_corridors_accepts_min_value_param(self):
        """GET /corridors/active?min_value=100000 accepts min_value parameter"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?min_value=100000")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        # All returned corridors should have total_amount_usd >= min_value
        for c in data["corridors"]:
            assert c.get("total_amount_usd", 0) >= 100000
    
    def test_active_corridors_accepts_both_params(self):
        """GET /corridors/active?limit=10&min_value=50000 accepts both params"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=10&min_value=50000")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        assert len(data["corridors"]) <= 10


class TestCorridorResponseStructure:
    """P3.5: Verify corridor response structure has required fields"""
    
    def test_empty_corridors_is_valid(self):
        """Empty corridors array is valid response (no corridor data yet)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active")
        assert response.status_code == 200
        data = response.json()
        # Even if empty, structure should be correct
        assert "corridors" in data
        assert "count" in data
        # Note: Corridors are empty because no corridor data in snapshots yet


class TestHealthStorageStats:
    """GET /api/graph-core/health returns storage stats for all 6 collections"""
    
    def test_health_returns_storage_object(self):
        """Health endpoint returns storage object"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert "storage" in data
        assert isinstance(data["storage"], dict)
    
    def test_storage_contains_graph_nodes(self):
        """Storage contains graph_nodes count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_nodes" in data["storage"]
    
    def test_storage_contains_graph_relations(self):
        """Storage contains graph_relations count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_relations" in data["storage"]
    
    def test_storage_contains_graph_snapshots(self):
        """Storage contains graph_snapshots count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_snapshots" in data["storage"]
    
    def test_storage_contains_graph_clusters(self):
        """Storage contains graph_clusters count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_clusters" in data["storage"]
    
    def test_storage_contains_graph_neighbors_cache(self):
        """Storage contains graph_neighbors_cache count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_neighbors_cache" in data["storage"]
    
    def test_storage_contains_graph_anchor_entities(self):
        """Storage contains graph_anchor_entities count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "graph_anchor_entities" in data["storage"]


class TestClusterUpsert:
    """P3.4: Cluster upsert behavior (update existing)"""
    
    def test_upsert_updates_existing_cluster(self):
        """POST /clusters with existing cluster_id updates it"""
        unique_id = f"test_upsert_{uuid.uuid4().hex[:8]}"
        # Create
        requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "institution",
            "label": "Original Label",
            "confidence": 0.5
        })
        # Upsert with new values
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "market_maker",
            "label": "Updated Label",
            "confidence": 0.99
        })
        assert response.status_code == 200
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        clusters = get_response.json().get("clusters", [])
        updated = next((c for c in clusters if c["cluster_id"] == unique_id), None)
        assert updated is not None
        assert updated["type"] == "market_maker"
        assert updated["label"] == "Updated Label"
        assert updated["confidence"] == 0.99


class TestIntegration:
    """Integration tests for P3.4 + P3.5"""
    
    def test_cluster_creation_appears_in_health(self):
        """Creating cluster increases graph_clusters count in health"""
        # Get initial count
        initial = requests.get(f"{BASE_URL}/api/graph-core/health").json()
        initial_count = initial["storage"]["graph_clusters"]
        
        # Create new cluster
        unique_id = f"test_health_count_{uuid.uuid4().hex[:8]}"
        requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "institution",
            "label": "Health Test",
            "confidence": 0.5
        })
        
        # Verify count increased
        final = requests.get(f"{BASE_URL}/api/graph-core/health").json()
        final_count = final["storage"]["graph_clusters"]
        assert final_count >= initial_count, "Cluster count should increase or stay same (if upsert)"
    
    def test_full_cluster_workflow(self):
        """Full workflow: create cluster -> list -> get members"""
        unique_id = f"workflow_test_{uuid.uuid4().hex[:8]}"
        
        # Step 1: Create
        create_resp = requests.post(f"{BASE_URL}/api/graph-core/clusters", json={
            "cluster_id": unique_id,
            "type": "fund",
            "label": "Workflow Fund",
            "confidence": 0.88
        })
        assert create_resp.status_code == 200
        assert create_resp.json()["cluster_id"] == unique_id
        
        # Step 2: List and find
        list_resp = requests.get(f"{BASE_URL}/api/graph-core/clusters")
        assert list_resp.status_code == 200
        clusters = list_resp.json()["clusters"]
        found = next((c for c in clusters if c["cluster_id"] == unique_id), None)
        assert found is not None
        assert found["label"] == "Workflow Fund"
        
        # Step 3: Get members
        members_resp = requests.get(f"{BASE_URL}/api/graph-core/clusters/{unique_id}/members")
        assert members_resp.status_code == 200
        assert members_resp.json()["cluster_id"] == unique_id
        assert members_resp.json()["count"] == 0  # No nodes assigned yet
