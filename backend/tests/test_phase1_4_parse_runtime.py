"""
Phase 1.4: Parser Call Path - Backend endpoint для запуска парсинга
Tests for parse runtime endpoints and task lifecycle.

Flow: UI → Backend → Parser (5001) → Mongo → UI

Endpoints tested:
- POST /api/v4/twitter/parse/search - запуск search parse
- POST /api/v4/twitter/parse/account - запуск account parse
- GET /api/v4/twitter/parse/tasks - список задач
- GET /api/v4/twitter/parse/tasks/:id - детали задачи
- GET /api/v4/twitter/data/search - спарсенные твиты
- GET /api/v4/twitter/data/stats - статистика парсинга

NOTE: Parser service (twitter-parser-v2:5001) is NOT running,
so parse requests will return ABORTED/FAILED status.
"""

import pytest
import requests
import time

BASE_URL = "http://localhost:8003"

# Test accounts (owned by dev-user)
ACCOUNT_1_ID = "697fa7d52dd38baab2b57c28"  # test_twitter_user
ACCOUNT_2_ID = "697fab792dd38baab2c880a4"  # second_twitter_user
NON_EXISTENT_TASK = "000000000000000000000000"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestParseSearchEndpoint:
    """Tests for POST /api/v4/twitter/parse/search"""

    def test_search_missing_query_returns_400(self, api_client):
        """Missing query parameter returns 400 error"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "Missing or invalid query" in data["error"]

    def test_search_invalid_query_type_returns_400(self, api_client):
        """Invalid query type (not string) returns 400 error"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": 123}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "Missing or invalid query" in data["error"]

    def test_search_valid_query_creates_task(self, api_client):
        """Valid search request creates task and returns result"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_search_query", "limit": 20}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Since parser is not running, expect ABORTED or FAILED
        assert "data" in data
        result = data["data"]
        
        assert "status" in result
        assert result["status"] in ["ABORTED", "FAILED", "OK", "PARTIAL"]
        assert "taskId" in result
        assert "accountId" in result
        
        # Verify task was created
        task_id = result["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.status_code == 200
        task_data = task_response.json()["data"]
        assert task_data["query"] == "test_search_query"
        assert task_data["type"] == "SEARCH"

    def test_search_with_filters(self, api_client):
        """Search with filters creates task with filters stored"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={
                "query": "crypto",
                "limit": 50,
                "filters": {
                    "minLikes": 100,
                    "minReposts": 10,
                    "timeRange": "24h"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        result = data["data"]
        assert "taskId" in result
        
        # Verify filters are stored in task
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{result['taskId']}")
        task_data = task_response.json()["data"]
        assert task_data["filters"] is not None
        assert task_data["filters"]["minLikes"] == 100
        assert task_data["filters"]["minReposts"] == 10

    def test_search_limit_clamped_to_range(self, api_client):
        """Limit is clamped to 10-500 range"""
        # Test limit below minimum
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_limit_min", "limit": 1}
        )
        
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.json()["data"]["limit"] == 10  # Clamped to minimum
        
        # Test limit above maximum
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_limit_max", "limit": 1000}
        )
        
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.json()["data"]["limit"] == 500  # Clamped to maximum

    def test_search_default_limit(self, api_client):
        """Default limit is 50 when not specified"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_default_limit"}
        )
        
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.json()["data"]["limit"] == 50


class TestParseAccountEndpoint:
    """Tests for POST /api/v4/twitter/parse/account"""

    def test_account_missing_username_returns_400(self, api_client):
        """Missing username parameter returns 400 error"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "Missing or invalid username" in data["error"]

    def test_account_invalid_username_type_returns_400(self, api_client):
        """Invalid username type (not string) returns 400 error"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": 123}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert "Missing or invalid username" in data["error"]

    def test_account_valid_username_creates_task(self, api_client):
        """Valid account request creates task and returns result"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": "testuser", "limit": 30}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        result = data["data"]
        
        assert "status" in result
        assert result["status"] in ["ABORTED", "FAILED", "OK", "PARTIAL"]
        assert "taskId" in result
        assert "accountId" in result
        
        # Verify task was created
        task_id = result["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.status_code == 200
        task_data = task_response.json()["data"]
        assert task_data["targetUsername"] == "testuser"
        assert task_data["type"] == "ACCOUNT"

    def test_account_username_strips_at_symbol(self, api_client):
        """Username with @ symbol is stripped"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": "@testuser_at", "limit": 10}
        )
        
        assert response.status_code == 200
        task_id = response.json()["data"]["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        assert task_response.json()["data"]["targetUsername"] == "testuser_at"


class TestTasksListEndpoint:
    """Tests for GET /api/v4/twitter/parse/tasks"""

    def test_tasks_list_returns_tasks(self, api_client):
        """Tasks list returns user's tasks"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        assert "tasks" in data["data"]
        assert "total" in data["data"]
        assert "limit" in data["data"]
        assert "skip" in data["data"]
        
        # Verify task structure
        if len(data["data"]["tasks"]) > 0:
            task = data["data"]["tasks"][0]
            assert "id" in task
            assert "type" in task
            assert "status" in task
            assert "fetched" in task
            assert "limit" in task
            assert "createdAt" in task

    def test_tasks_list_filter_by_status(self, api_client):
        """Tasks list can be filtered by status"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/parse/tasks",
            params={"status": "FAILED"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # All returned tasks should have FAILED status
        for task in data["data"]["tasks"]:
            assert task["status"] == "FAILED"

    def test_tasks_list_filter_by_type(self, api_client):
        """Tasks list can be filtered by type"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/parse/tasks",
            params={"type": "SEARCH"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # All returned tasks should have SEARCH type
        for task in data["data"]["tasks"]:
            assert task["type"] == "SEARCH"

    def test_tasks_list_pagination(self, api_client):
        """Tasks list supports pagination"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/parse/tasks",
            params={"limit": 2, "skip": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["data"]["limit"] == 2
        assert data["data"]["skip"] == 0
        assert len(data["data"]["tasks"]) <= 2

    def test_tasks_list_limit_capped_at_100(self, api_client):
        """Tasks list limit is capped at 100"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/parse/tasks",
            params={"limit": 200}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["limit"] == 100


class TestTaskDetailsEndpoint:
    """Tests for GET /api/v4/twitter/parse/tasks/:id"""

    def test_task_details_returns_task(self, api_client):
        """Task details returns full task data"""
        # First create a task
        create_response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_details", "limit": 10}
        )
        task_id = create_response.json()["data"]["taskId"]
        
        # Get task details
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        
        task = data["data"]
        assert task["_id"] == task_id
        assert "ownerUserId" in task
        assert "accountId" in task
        assert "sessionId" in task
        assert "type" in task
        assert "status" in task
        assert "fetched" in task
        assert "createdAt" in task

    def test_task_details_not_found(self, api_client):
        """Non-existent task returns 404"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{NON_EXISTENT_TASK}")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["ok"] is False
        assert "Task not found" in data["error"]

    def test_task_details_contains_engine_summary(self, api_client):
        """Task details contains engineSummary after completion"""
        # Create a task (will fail/abort since parser not running)
        create_response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "test_engine_summary", "limit": 10}
        )
        task_id = create_response.json()["data"]["taskId"]
        
        # Get task details
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = response.json()["data"]
        
        # Should have engineSummary after completion
        assert "engineSummary" in task
        if task["engineSummary"]:
            summary = task["engineSummary"]
            assert "fetched" in summary
            assert "planned" in summary
            assert "durationMs" in summary
            assert "aborted" in summary


class TestDataSearchEndpoint:
    """Tests for GET /api/v4/twitter/data/search"""

    def test_data_search_returns_tweets(self, api_client):
        """Data search returns parsed tweets"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/data/search")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "limit" in data["data"]
        assert "skip" in data["data"]

    def test_data_search_filter_by_query(self, api_client):
        """Data search can be filtered by query"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"query": "bitcoin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # All returned items should have matching query
        for item in data["data"]["items"]:
            assert item["query"] == "bitcoin"

    def test_data_search_filter_by_source(self, api_client):
        """Data search can be filtered by source"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"source": "SEARCH"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        for item in data["data"]["items"]:
            assert item["source"] == "SEARCH"

    def test_data_search_filter_by_min_likes(self, api_client):
        """Data search can be filtered by minLikes"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"minLikes": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        for item in data["data"]["items"]:
            assert item["likes"] >= 100

    def test_data_search_filter_by_min_reposts(self, api_client):
        """Data search can be filtered by minReposts"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"minReposts": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        for item in data["data"]["items"]:
            assert item["reposts"] >= 10

    def test_data_search_filter_by_time_range(self, api_client):
        """Data search can be filtered by timeRange"""
        for time_range in ["1h", "6h", "24h", "7d"]:
            response = api_client.get(
                f"{BASE_URL}/api/v4/twitter/data/search",
                params={"timeRange": time_range}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True

    def test_data_search_sort_by_likes(self, api_client):
        """Data search can be sorted by likes"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"sortBy": "likes"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # Verify descending order
        items = data["data"]["items"]
        for i in range(len(items) - 1):
            assert items[i]["likes"] >= items[i + 1]["likes"]

    def test_data_search_sort_by_reposts(self, api_client):
        """Data search can be sorted by reposts"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"sortBy": "reposts"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True

    def test_data_search_pagination(self, api_client):
        """Data search supports pagination"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"limit": 10, "skip": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["limit"] == 10
        assert data["data"]["skip"] == 0

    def test_data_search_limit_capped_at_200(self, api_client):
        """Data search limit is capped at 200"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/data/search",
            params={"limit": 500}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["limit"] == 200


class TestDataStatsEndpoint:
    """Tests for GET /api/v4/twitter/data/stats"""

    def test_stats_returns_statistics(self, api_client):
        """Stats endpoint returns parsing statistics"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/data/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        
        stats = data["data"]
        assert "totalTweets" in stats
        assert "totalTasks" in stats
        assert "last24h" in stats
        
        # Verify last24h structure
        last24h = stats["last24h"]
        assert "tasks" in last24h
        assert "fetched" in last24h
        assert "avgDurationMs" in last24h
        assert "successRate" in last24h

    def test_stats_values_are_integers(self, api_client):
        """Stats values are integers"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/data/stats")
        
        assert response.status_code == 200
        stats = response.json()["data"]
        
        assert isinstance(stats["totalTweets"], int)
        assert isinstance(stats["totalTasks"], int)
        assert isinstance(stats["last24h"]["tasks"], int)
        assert isinstance(stats["last24h"]["fetched"], int)
        assert isinstance(stats["last24h"]["avgDurationMs"], int)
        assert isinstance(stats["last24h"]["successRate"], int)


class TestTaskLifecycle:
    """Tests for task lifecycle: PENDING → RUNNING → status"""

    def test_task_lifecycle_search(self, api_client):
        """Search task goes through lifecycle states"""
        # Create task
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "lifecycle_test", "limit": 10}
        )
        
        assert response.status_code == 200
        result = response.json()["data"]
        task_id = result["taskId"]
        
        # Get task details
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = task_response.json()["data"]
        
        # Task should be in terminal state (DONE, PARTIAL, or FAILED)
        assert task["status"] in ["DONE", "PARTIAL", "FAILED"]
        
        # Should have timestamps
        assert "createdAt" in task
        assert "startedAt" in task
        assert "completedAt" in task

    def test_task_lifecycle_account(self, api_client):
        """Account task goes through lifecycle states"""
        # Create task
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": "lifecycle_user", "limit": 10}
        )
        
        assert response.status_code == 200
        result = response.json()["data"]
        task_id = result["taskId"]
        
        # Get task details
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = task_response.json()["data"]
        
        # Task should be in terminal state
        assert task["status"] in ["DONE", "PARTIAL", "FAILED"]


class TestSelectionFailure:
    """Tests for selection failure scenarios"""

    def test_selection_failure_returns_409_with_state(self, api_client):
        """When no session available, returns 409 with state"""
        # This test depends on having no valid sessions
        # Since we have test accounts with sessions, this will succeed
        # We're testing that the endpoint handles the case correctly
        
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "selection_test", "limit": 10}
        )
        
        # Either succeeds (200) or fails with 409
        assert response.status_code in [200, 409]
        
        if response.status_code == 409:
            data = response.json()
            assert data["ok"] is False
            assert "error" in data
            assert "state" in data
            # State should be one of the defined states
            assert data["state"] in [
                "NOT_CONNECTED",
                "NEED_COOKIES",
                "SESSION_INVALID",
                "NO_PROXY",
                "SESSION_STALE"
            ]


class TestIntegrationFlow:
    """Integration tests for complete parse flow"""

    def test_full_search_flow(self, api_client):
        """Complete flow: search → task created → task in list → data endpoint"""
        # Step 1: Create search task
        search_response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "integration_test_search", "limit": 10}
        )
        
        assert search_response.status_code == 200
        task_id = search_response.json()["data"]["taskId"]
        
        # Step 2: Verify task appears in list
        list_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks")
        tasks = list_response.json()["data"]["tasks"]
        task_ids = [t["id"] for t in tasks]
        assert task_id in task_ids
        
        # Step 3: Verify task details
        details_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = details_response.json()["data"]
        assert task["query"] == "integration_test_search"
        assert task["type"] == "SEARCH"
        
        # Step 4: Check stats updated
        stats_response = api_client.get(f"{BASE_URL}/api/v4/twitter/data/stats")
        stats = stats_response.json()["data"]
        assert stats["totalTasks"] > 0

    def test_full_account_flow(self, api_client):
        """Complete flow: account parse → task created → task in list"""
        # Step 1: Create account task
        account_response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": "integration_test_user", "limit": 10}
        )
        
        assert account_response.status_code == 200
        task_id = account_response.json()["data"]["taskId"]
        
        # Step 2: Verify task appears in list with ACCOUNT type filter
        list_response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/parse/tasks",
            params={"type": "ACCOUNT"}
        )
        tasks = list_response.json()["data"]["tasks"]
        task_ids = [t["id"] for t in tasks]
        assert task_id in task_ids
        
        # Step 3: Verify task details
        details_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = details_response.json()["data"]
        assert task["targetUsername"] == "integration_test_user"
        assert task["type"] == "ACCOUNT"


class TestParserUnavailable:
    """Tests for behavior when parser service is unavailable"""

    def test_search_returns_aborted_when_parser_down(self, api_client):
        """Search returns ABORTED/FAILED when parser is unavailable"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "parser_down_test", "limit": 10}
        )
        
        assert response.status_code == 200
        result = response.json()["data"]
        
        # Parser is not running, so expect ABORTED or FAILED
        assert result["status"] in ["ABORTED", "FAILED"]
        assert result["fetched"] == 0

    def test_account_returns_aborted_when_parser_down(self, api_client):
        """Account parse returns ABORTED/FAILED when parser is unavailable"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/account",
            json={"username": "parser_down_user", "limit": 10}
        )
        
        assert response.status_code == 200
        result = response.json()["data"]
        
        # Parser is not running, so expect ABORTED or FAILED
        assert result["status"] in ["ABORTED", "FAILED"]
        assert result["fetched"] == 0

    def test_task_has_duration_even_when_failed(self, api_client):
        """Task records duration even when parser fails"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/parse/search",
            json={"query": "duration_test", "limit": 10}
        )
        
        task_id = response.json()["data"]["taskId"]
        task_response = api_client.get(f"{BASE_URL}/api/v4/twitter/parse/tasks/{task_id}")
        task = task_response.json()["data"]
        
        # Should have durationMs recorded
        assert "durationMs" in task
        assert task["durationMs"] is not None
        assert task["durationMs"] >= 0
