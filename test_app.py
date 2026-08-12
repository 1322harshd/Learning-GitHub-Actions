"""
Unit tests for app.py, using Flask's test client + pytest.

Run with:
    pytest test_app.py -v
"""

import itertools

import pytest

import app as app_module


@pytest.fixture
def client():
    """Fresh Flask test client with the in-memory store reset each test."""
    app_module.app.config["TESTING"] = True
    app_module.tasks.clear()
    app_module.id_counter = itertools.count(1)

    with app_module.app.test_client() as test_client:
        yield test_client


def create_sample_task(client, title="Sample Task", description="Sample description", completed=False):
    return client.post(
        "/tasks",
        json={"title": title, "description": description, "completed": completed},
    )


# --- Health check ------------------------------------------------------------
class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


# --- Create --------------------------------------------------------------------
class TestCreateTask:
    def test_create_task_success(self, client):
        response = create_sample_task(client)
        assert response.status_code == 201

        data = response.get_json()
        assert data["title"] == "Sample Task"
        assert data["description"] == "Sample description"
        assert data["completed"] is False
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        response = client.post("/tasks", json={"description": "No title here"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_create_task_empty_title(self, client):
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 400

    def test_create_task_no_body(self, client):
        response = client.post("/tasks")
        assert response.status_code == 400

    def test_create_task_defaults_completed_to_false(self, client):
        response = client.post("/tasks", json={"title": "No completed field"})
        assert response.status_code == 201
        assert response.get_json()["completed"] is False

    def test_create_task_ids_increment(self, client):
        first = create_sample_task(client, title="First").get_json()
        second = create_sample_task(client, title="Second").get_json()
        assert second["id"] == first["id"] + 1


# --- Read ------------------------------------------------------------------
class TestGetTasks:
    def test_get_tasks_empty(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_get_tasks_returns_all(self, client):
        create_sample_task(client, title="Task 1")
        create_sample_task(client, title="Task 2")

        response = client.get("/tasks")
        data = response.get_json()
        assert response.status_code == 200
        assert len(data) == 2

    def test_get_tasks_filter_completed_true(self, client):
        create_sample_task(client, title="Done", completed=True)
        create_sample_task(client, title="Not done", completed=False)

        response = client.get("/tasks?completed=true")
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Done"

    def test_get_tasks_filter_completed_false(self, client):
        create_sample_task(client, title="Done", completed=True)
        create_sample_task(client, title="Not done", completed=False)

        response = client.get("/tasks?completed=false")
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Not done"

    def test_get_single_task_success(self, client):
        created = create_sample_task(client).get_json()
        response = client.get(f"/tasks/{created['id']}")
        assert response.status_code == 200
        assert response.get_json()["id"] == created["id"]

    def test_get_single_task_not_found(self, client):
        response = client.get("/tasks/999")
        assert response.status_code == 404


# --- Update ------------------------------------------------------------------
class TestUpdateTask:
    def test_update_task_title(self, client):
        created = create_sample_task(client).get_json()
        response = client.put(f"/tasks/{created['id']}", json={"title": "Updated Title"})
        assert response.status_code == 200
        assert response.get_json()["title"] == "Updated Title"

    def test_update_task_description(self, client):
        created = create_sample_task(client).get_json()
        response = client.put(
            f"/tasks/{created['id']}", json={"description": "New description"}
        )
        assert response.status_code == 200
        assert response.get_json()["description"] == "New description"

    def test_update_task_completed_status(self, client):
        created = create_sample_task(client).get_json()
        response = client.put(f"/tasks/{created['id']}", json={"completed": True})
        assert response.status_code == 200
        assert response.get_json()["completed"] is True

    def test_update_task_partial_update_preserves_other_fields(self, client):
        created = create_sample_task(client, title="Original", description="Original desc").get_json()
        response = client.put(f"/tasks/{created['id']}", json={"completed": True})
        data = response.get_json()
        assert data["title"] == "Original"
        assert data["description"] == "Original desc"
        assert data["completed"] is True

    def test_update_task_not_found(self, client):
        response = client.put("/tasks/999", json={"title": "Nope"})
        assert response.status_code == 404

    def test_update_task_empty_title_rejected(self, client):
        created = create_sample_task(client).get_json()
        response = client.put(f"/tasks/{created['id']}", json={"title": "   "})
        assert response.status_code == 400

    def test_update_task_no_data(self, client):
        created = create_sample_task(client).get_json()
        response = client.put(f"/tasks/{created['id']}")
        assert response.status_code == 400


# --- Delete ------------------------------------------------------------------
class TestDeleteTask:
    def test_delete_task_success(self, client):
        created = create_sample_task(client).get_json()

        response = client.delete(f"/tasks/{created['id']}")
        assert response.status_code == 204

        get_response = client.get(f"/tasks/{created['id']}")
        assert get_response.status_code == 404

    def test_delete_task_not_found(self, client):
        response = client.delete("/tasks/999")
        assert response.status_code == 404

    def test_delete_task_removes_only_target(self, client):
        first = create_sample_task(client, title="Keep me").get_json()
        second = create_sample_task(client, title="Delete me").get_json()

        client.delete(f"/tasks/{second['id']}")

        response = client.get("/tasks")
        remaining_ids = [t["id"] for t in response.get_json()]
        assert first["id"] in remaining_ids
        assert second["id"] not in remaining_ids
