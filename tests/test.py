"""
Selenium-based smoke tests for the deployed Task Manager app.

Unlike test_app.py (which uses Flask's test client against the app in-process),
these tests drive a real headless browser against a *running* instance of the
app - useful as a post-deployment check in the CI/CD pipeline.

The app is a JSON API with no HTML UI, so:
  - GET endpoints are checked by navigating to the URL and reading the
    raw JSON the browser renders as page text.
  - POST/PUT/DELETE endpoints are exercised via `fetch()` calls run in the
    browser through `execute_script`, since Selenium's navigation only
    supports GET.

Configure the target with the APP_URL environment variable
(defaults to http://localhost:5000).

Run with:
    pytest tests/test.py -v
"""

import json
import os

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")


@pytest.fixture(scope="module")
def driver():
    options = Options()
    options.add_argument("--headless")
    options.set_preference("devtools.jsonview.enabled", False)

    firefox_driver = webdriver.Firefox(
        service=Service(GeckoDriverManager().install()), options=options
    )
    yield firefox_driver
    firefox_driver.quit()


def get_json(driver, path):
    """Navigate to a GET endpoint and parse the JSON body rendered by the browser."""
    driver.get(f"{BASE_URL}{path}")
    body_text = driver.find_element("tag name", "body").text
    return json.loads(body_text)


def fetch_json(driver, method, path, payload=None):
    """Call a non-GET endpoint from inside the browser via fetch() and return
    (status_code, parsed_json_body)."""
    script = """
    const [method, url, body, callback] = arguments;
    fetch(url, {
        method: method,
        headers: {"Content-Type": "application/json"},
        body: body !== null ? JSON.stringify(body) : undefined,
    })
        .then(async (response) => {
            const text = await response.text();
            callback([response.status, text]);
        })
        .catch((error) => callback([0, String(error)]));
    """
    driver.get(BASE_URL)  # ensure we're on the app's origin before calling fetch
    status, text = driver.execute_async_script(
        script, method, f"{BASE_URL}{path}", payload
    )
    parsed = json.loads(text) if text else None
    return status, parsed


# --- Health check ------------------------------------------------------------
class TestHealthCheck:
    def test_health_check(self, driver):
        data = get_json(driver, "/health")
        assert data["status"] == "ok"


# --- Create --------------------------------------------------------------------
class TestCreateTask:
    def test_create_task_success(self, driver):
        status, data = fetch_json(
            driver,
            "POST",
            "/tasks",
            {"title": "Sample Task", "description": "Sample description"},
        )
        assert status == 201
        assert data["title"] == "Sample Task"
        assert data["completed"] is False
        assert "id" in data

    def test_create_task_missing_title(self, driver):
        status, data = fetch_json(driver, "POST", "/tasks", {"description": "No title"})
        assert status == 400
        assert "error" in data


# --- Read ------------------------------------------------------------------
class TestGetTasks:
    def test_get_tasks_returns_list(self, driver):
        fetch_json(driver, "POST", "/tasks", {"title": "Task for listing"})
        data = get_json(driver, "/tasks")
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_single_task_not_found(self, driver):
        status, _ = fetch_json(driver, "GET", "/tasks/999999")
        assert status == 404


# --- Update ------------------------------------------------------------------
class TestUpdateTask:
    def test_update_task_title(self, driver):
        _, created = fetch_json(driver, "POST", "/tasks", {"title": "Before update"})
        status, data = fetch_json(
            driver, "PUT", f"/tasks/{created['id']}", {"title": "After update"}
        )
        assert status == 200
        assert data["title"] == "After update"


# --- Delete ------------------------------------------------------------------
class TestDeleteTask:
    def test_delete_task_success(self, driver):
        _, created = fetch_json(driver, "POST", "/tasks", {"title": "To be deleted"})
        status, _ = fetch_json(driver, "DELETE", f"/tasks/{created['id']}")
        assert status == 204

        status, _ = fetch_json(driver, "GET", f"/tasks/{created['id']}")
        assert status == 404
