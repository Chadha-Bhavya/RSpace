import unittest

from auth import AuthError, SupabaseAuthClient


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.is_error = status_code >= 400

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses.pop(0)

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses.pop(0)


class TestSupabaseAuthClient(unittest.IsolatedAsyncioTestCase):
    async def test_signup_sends_name_as_metadata(self):
        client = FakeClient([FakeResponse(200, {"user": {"id": "abc"}})])
        auth = SupabaseAuthClient(client, "https://project.supabase.co", "public-key")

        await auth.sign_up("person@example.com", "password123", "Sam Person")

        request = client.requests[0]
        self.assertEqual(request[0], "POST")
        self.assertEqual(request[2]["json"]["data"]["display_name"], "Sam Person")
        self.assertEqual(request[2]["headers"]["apikey"], "public-key")

    async def test_login_uses_password_grant(self):
        client = FakeClient([FakeResponse(200, {"access_token": "token", "user": {"id": "abc"}})])
        auth = SupabaseAuthClient(client, "https://project.supabase.co", "public-key")

        await auth.sign_in("person@example.com", "password123")

        request = client.requests[0]
        self.assertEqual(request[2]["params"], {"grant_type": "password"})

    async def test_get_user_sends_bearer_token(self):
        client = FakeClient([FakeResponse(200, {"id": "abc", "email": "person@example.com"})])
        auth = SupabaseAuthClient(client, "https://project.supabase.co", "public-key")

        user = await auth.get_user("access-token")

        self.assertEqual(user["id"], "abc")
        self.assertEqual(client.requests[0][2]["headers"]["Authorization"], "Bearer access-token")

    async def test_login_error_does_not_reveal_account_details(self):
        client = FakeClient([FakeResponse(400, {"message": "internal detail"})])
        auth = SupabaseAuthClient(client, "https://project.supabase.co", "public-key")

        with self.assertRaisesRegex(AuthError, "email or password is incorrect"):
            await auth.sign_in("person@example.com", "wrong-password")


if __name__ == "__main__":
    unittest.main()
