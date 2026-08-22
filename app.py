"""
Simple Flask-based Task Manager REST API.

Endpoints
---------
GET    /health              -> health check
GET    /tasks                -> list all tasks (optional ?completed=true|false filter)
GET    /tasks/<task_id>      -> get a single task
POST   /tasks                -> create a task (JSON body: {"title": ..., "description": ..., "completed": ...})
PUT    /tasks/<task_id>      -> update a task (partial updates allowed)
DELETE /tasks/<task_id>      -> delete a task

Data is stored in-memory for simplicity. Swap `tasks` / `id_counter` for a
real database (e.g. SQLAlchemy) in a production setting.
"""

import itertools
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, request

app = Flask(__name__)

# --- In-memory "database" -------------------------------------------------
tasks = {}
id_counter = itertools.count(1)


def serialize_task(task):
    """Convert an internal task dict into a JSON-safe representation."""
    return {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "completed": task["completed"],
        "created_at": task["created_at"],
    }


# --- Routes ----------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="ok"), 200


@app.route("/tasks", methods=["GET"])
def get_tasks():
    completed_param = request.args.get("completed")
    result = list(tasks.values())

    if completed_param is not None:
        wants_completed = completed_param.lower() == "true"
        result = [t for t in result if t["completed"] == wants_completed]

    result.sort(key=lambda t: t["id"])
    return jsonify([serialize_task(t) for t in result]), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = tasks.get(task_id)
    if task is None:
        abort(404, description="Task not found")
    return jsonify(serialize_task(task)), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)

    if not data or not str(data.get("title", "")).strip():
        abort(400, description="Title is required")

    task_id = next(id_counter)
    task = {
        "id": task_id,
        "title": data["title"].strip(),
        "description": str(data.get("description", "")).strip(),
        "completed": bool(data.get("completed", False)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tasks[task_id] = task
    return jsonify(serialize_task(task)), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = tasks.get(task_id)
    if task is None:
        abort(404, description="Task not found")

    data = request.get_json(silent=True)
    if not data:
        abort(400, description="No update data provided")

    if "title" in data:
        if not str(data["title"]).strip():
            abort(400, description="Title cannot be empty")
        task["title"] = data["title"].strip()

    if "description" in data:
        task["description"] = str(data["description"])

    if "completed" in data:
        task["completed"] = bool(data["completed"])

    return jsonify(serialize_task(task)), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = tasks.get(task_id)
    if task is None:
        abort(404, description="Task not found")
    del tasks[task_id]
    return "", 204


# --- Error handlers ----------------------------------------------------------
@app.errorhandler(400)
def bad_request(e):
    return jsonify(error=str(e.description)), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify(error=str(e.description)), 404


if __name__ == "__main__":
    app.run(debug=False)
