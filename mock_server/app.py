from typing import Any, Dict, Tuple

from flask import Flask, jsonify, request


VALID_USERNAME = "admin"
VALID_PASSWORD = "password123"
VALID_TOKEN = "demo-access-token"
USERS: Dict[int, Dict[str, Any]] = {
    1: {"id": 1, "username": "admin", "display_name": "Automation Admin"},
    2: {"id": 2, "username": "tester", "display_name": "API Tester"},
}


def error_response(code: str, message: str, status: int) -> Tuple[Any, int]:
    return jsonify({"code": code, "message": message}), status


def create_app() -> Flask:
    app = Flask(__name__)
    users = {user_id: dict(user) for user_id, user in USERS.items()}

    def require_token() -> Tuple[Any, int] | None:
        if request.headers.get("Authorization") != f"Bearer {VALID_TOKEN}":
            return error_response(
                "UNAUTHORIZED",
                "a valid bearer token is required",
                401,
            )
        return None

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "mock-api"})

    @app.post("/api/login")
    def login() -> Any:
        payload = request.get_json(silent=True) or {}
        if not payload.get("username") or not payload.get("password"):
            return error_response("VALIDATION_ERROR", "username and password are required", 400)
        if payload["username"] != VALID_USERNAME or payload["password"] != VALID_PASSWORD:
            return error_response("INVALID_CREDENTIALS", "invalid username or password", 401)
        return jsonify(
            {
                "code": "SUCCESS",
                "access_token": VALID_TOKEN,
                "token_type": "Bearer",
                "user_id": 1,
            }
        )

    @app.get("/api/users/<int:user_id>")
    def get_user(user_id: int) -> Any:
        unauthorized = require_token()
        if unauthorized:
            return unauthorized
        user = users.get(user_id)
        if user is None:
            return error_response("USER_NOT_FOUND", "user does not exist", 404)
        return jsonify({"code": "SUCCESS", "data": user})

    @app.get("/api/users")
    def list_users() -> Any:
        unauthorized = require_token()
        if unauthorized:
            return unauthorized
        return jsonify(
            {
                "code": "SUCCESS",
                "data": [users[user_id] for user_id in sorted(users)],
            }
        )

    @app.post("/api/users")
    def create_user() -> Any:
        unauthorized = require_token()
        if unauthorized:
            return unauthorized
        payload = request.get_json(silent=True) or {}
        if not payload.get("username") or not payload.get("display_name"):
            return error_response(
                "VALIDATION_ERROR",
                "username and display_name are required",
                400,
            )
        if any(
            user["username"] == payload["username"] for user in users.values()
        ):
            return error_response(
                "USERNAME_CONFLICT",
                "username already exists",
                409,
            )
        user_id = max(users, default=0) + 1
        user = {
            "id": user_id,
            "username": payload["username"],
            "display_name": payload["display_name"],
        }
        users[user_id] = user
        return jsonify({"code": "SUCCESS", "data": user})

    @app.patch("/api/users/<int:user_id>")
    def update_user(user_id: int) -> Any:
        unauthorized = require_token()
        if unauthorized:
            return unauthorized
        user = users.get(user_id)
        if user is None:
            return error_response("USER_NOT_FOUND", "user does not exist", 404)
        payload = request.get_json(silent=True) or {}
        if "display_name" in payload:
            user["display_name"] = payload["display_name"]
        return jsonify({"code": "SUCCESS", "data": user})

    @app.delete("/api/users/<int:user_id>")
    def delete_user(user_id: int) -> Any:
        unauthorized = require_token()
        if unauthorized:
            return unauthorized
        user = users.pop(user_id, None)
        if user is None:
            return error_response("USER_NOT_FOUND", "user does not exist", 404)
        return jsonify({"code": "SUCCESS", "data": {"id": user_id}})

    return app
