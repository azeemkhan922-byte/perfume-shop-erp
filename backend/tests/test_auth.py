import unittest
from tests.helpers import fresh_db
from app.services import auth

SECRET = "s" * 40


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        auth.create_owner(self.db, "azeem", "a-strong-password")

    def test_only_one_owner(self):
        with self.assertRaises(auth.AuthError):
            auth.create_owner(self.db, "other", "another-password")

    def test_login_ok_and_token_valid(self):
        t = auth.login(self.db, "azeem", "a-strong-password", SECRET, 12)
        self.assertTrue(auth.verify_token(t, SECRET))

    def test_wrong_password(self):
        with self.assertRaises(auth.AuthError):
            auth.login(self.db, "azeem", "nope-nope-nope", SECRET, 12)

    def test_wrong_username(self):
        with self.assertRaises(auth.AuthError):
            auth.login(self.db, "bob", "a-strong-password", SECRET, 12)

    def test_token_tampered_or_wrong_secret(self):
        t = auth.make_token(SECRET, 1)
        self.assertFalse(auth.verify_token(t + "x", SECRET))
        self.assertFalse(auth.verify_token(t, "z" * 40))
        self.assertFalse(auth.verify_token("garbage", SECRET))

    def test_token_expires(self):
        t = auth.make_token(SECRET, 1, now=1000)
        self.assertTrue(auth.verify_token(t, SECRET, now=1000 + 3599))
        self.assertFalse(auth.verify_token(t, SECRET, now=1000 + 3601))

    def test_short_secret_rejected(self):
        with self.assertRaises(ValueError):
            auth.make_token("short", 1)

    def test_lockout_after_five_failures_even_with_right_password(self):
        for _ in range(5):
            with self.assertRaises(auth.AuthError):
                auth.login(self.db, "azeem", "bad-password-x", SECRET, 12)
        with self.assertRaises(auth.AuthError) as cm:
            auth.login(self.db, "azeem", "a-strong-password", SECRET, 12)
        self.assertIn("too many", str(cm.exception))

    def test_success_resets_failures(self):
        for _ in range(3):
            with self.assertRaises(auth.AuthError):
                auth.login(self.db, "azeem", "bad-password-x", SECRET, 12)
        auth.login(self.db, "azeem", "a-strong-password", SECRET, 12)
        self.assertEqual(self.db.one("SELECT failed_logins FROM owner")["failed_logins"], 0)

    def test_change_password(self):
        auth.change_password(self.db, "a-strong-password", "brand-new-password")
        auth.login(self.db, "azeem", "brand-new-password", SECRET, 12)
        with self.assertRaises(auth.AuthError):
            auth.change_password(self.db, "wrong-old-password", "whatever-long-1")


if __name__ == "__main__":
    unittest.main()
