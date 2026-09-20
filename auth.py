"""Small server-side client for Supabase email and password authentication."""

from __future__ import annotations

import os
from typing import Any

import httpx


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthClient:
    def __init__(self, client: httpx.AsyncClient, url: str, publishable_key: str) -> None:
        self.client = client
        self.url = url.rstrip("/")
        self.publishable_key = publishable_key

    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.publishable_key, "Content-Type": "application/json"}

    async def sign_up(self, email: str, password: str, display_name: str) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.url}/auth/v1/signup",
            headers=self.headers,
            json={
                "email": email,
                "password": password,
                "data": {"display_name": display_name},
            },
        )
        return self._result(response, "Account creation failed. Please check your details.")

    async def sign_in(self, email: str, password: str) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.url}/auth/v1/token",
            params={"grant_type": "password"},
            headers=self.headers,
            json={"email": email, "password": password},
        )
        return self._result(response, "The email or password is incorrect.")

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.url}/auth/v1/token",
            params={"grant_type": "refresh_token"},
            headers=self.headers,
            json={"refresh_token": refresh_token},
        )
        return self._result(response, "Your session has expired. Please log in again.")

    async def get_user(self, access_token: str) -> dict[str, Any]:
        response = await self.client.get(
            f"{self.url}/auth/v1/user",
            headers={**self.headers, "Authorization": f"Bearer {access_token}"},
        )
        data = self._result(response, "Please log in to continue.")
        if not data.get("id"):
            raise AuthError("Please log in to continue.")
        return data

    async def sign_out(self, access_token: str) -> None:
        response = await self.client.post(
            f"{self.url}/auth/v1/logout",
            headers={**self.headers, "Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 500:
            raise AuthError("Logout could not be completed.", 502)

    @staticmethod
    def _result(response: httpx.Response, fallback: str) -> dict[str, Any]:
        if response.is_error:
            status = 401 if response.status_code in {400, 401, 403, 422} else 502
            raise AuthError(fallback, status)
        try:
            return response.json()
        except ValueError as error:
            raise AuthError("The authentication service returned an invalid response.", 502) from error


def create_auth_client(client: httpx.AsyncClient) -> SupabaseAuthClient:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    if not url or not key or url.startswith("your_") or key.startswith("your_"):
        raise RuntimeError(
            "Supabase Auth is not configured. Add SUPABASE_URL and "
            "SUPABASE_PUBLISHABLE_KEY to the environment."
        )
    return SupabaseAuthClient(client, url, key)
