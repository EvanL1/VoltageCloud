import os
import importlib.util
from unittest.mock import patch, MagicMock

import boto3


def load_auth_manager(monkeypatch):
    monkeypatch.setenv("USER_PROFILE_TABLE", "test_user_table")
    monkeypatch.setenv("DEVICE_PERMISSIONS_TABLE", "test_perm_table")
    monkeypatch.setenv("USER_POOL_ID", "pool")
    monkeypatch.setenv("REGION", "us-east-1")

    monkeypatch.setattr(boto3, "client", lambda *a, **k: MagicMock())
    monkeypatch.setattr(boto3, "resource", lambda *a, **k: MagicMock())

    spec = importlib.util.spec_from_file_location(
        "auth_manager", os.path.join(os.path.dirname(__file__), "..", "lambda", "auth_manager.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_user_profile_route(monkeypatch):
    auth_manager = load_auth_manager(monkeypatch)
    with patch.object(auth_manager, "extract_user_info_from_jwt", return_value={"user_id": "123", "role": "admin"}):
        with patch.object(auth_manager, "get_user_profile", return_value={"statusCode": 200}) as get_profile:
            event = {"httpMethod": "GET", "path": "/users/123", "pathParameters": {"user_id": "123"}}
            resp = auth_manager.handler(event, None)
            assert resp["statusCode"] == 200
            get_profile.assert_called_once_with("123")


def test_get_user_permissions_route(monkeypatch):
    auth_manager = load_auth_manager(monkeypatch)
    with patch.object(auth_manager, "extract_user_info_from_jwt", return_value={"user_id": "123", "role": "admin"}):
        with patch.object(auth_manager, "get_user_device_permissions", return_value={"statusCode": 200}) as get_perms:
            event = {
                "httpMethod": "GET",
                "path": "/users/123/permissions",
                "pathParameters": {"user_id": "123"},
            }
            resp = auth_manager.handler(event, None)
            assert resp["statusCode"] == 200
            get_perms.assert_called_once_with("123")


def test_grant_device_permission_route(monkeypatch):
    auth_manager = load_auth_manager(monkeypatch)
    with patch.object(auth_manager, "extract_user_info_from_jwt", return_value={"user_id": "admin", "role": "admin"}):
        with patch.object(auth_manager, "grant_device_permission", return_value={"statusCode": 200}) as grant_perm:
            event = {
                "httpMethod": "POST",
                "path": "/users/123/permissions/devices",
                "pathParameters": {"user_id": "123"},
                "body": "{}",
            }
            resp = auth_manager.handler(event, None)
            assert resp["statusCode"] == 200
            grant_perm.assert_called_once_with("123", None, [])
