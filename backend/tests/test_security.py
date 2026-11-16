import unittest
from app.core.security import hash_password, verify_password


class TestSecurity(unittest.TestCase):
    def test_roundtrip(self):
        h = hash_password("correct horse battery")
        self.assertTrue(verify_password("correct horse battery", h))
        self.assertFalse(verify_password("wrong password!!", h))

    def test_salted(self):
        self.assertNotEqual(hash_password("same password 1"), hash_password("same password 1"))

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("short")

    def test_garbage_hash_is_false_not_crash(self):
        self.assertFalse(verify_password("x" * 12, "not-a-hash"))


if __name__ == "__main__":
    unittest.main()
