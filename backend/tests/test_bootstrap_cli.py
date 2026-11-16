import os, tempfile, unittest
from unittest import mock
from tests.api_helper import Api
from tests.helpers import fresh_db, seed
from app import config
from app.bootstrap import ensure_owner_from_env
from app.services import auth


class TestBootstrap(unittest.TestCase):
    ENV = {"OWNER_USERNAME": "azeem", "OWNER_PASSWORD": "a-strong-password"}

    def test_creates_owner_once_from_env(self):
        db = fresh_db()
        self.assertTrue(ensure_owner_from_env(db, self.ENV))
        auth.login(db, "azeem", "a-strong-password", "k" * 40, 1)
        self.assertFalse(ensure_owner_from_env(db, {"OWNER_USERNAME": "other", "OWNER_PASSWORD": "another-password-1"}))   # never overwrites
        auth.login(db, "azeem", "a-strong-password", "k" * 40, 1)

    def test_does_nothing_without_variables(self):
        db = fresh_db()
        self.assertFalse(ensure_owner_from_env(db, {}))
        self.assertFalse(ensure_owner_from_env(db, {"OWNER_USERNAME": "azeem"}))
        self.assertIsNone(db.one("SELECT id FROM owner"))

    def test_short_password_is_rejected_loudly(self):
        with self.assertRaises(ValueError):
            ensure_owner_from_env(fresh_db(), {"OWNER_USERNAME": "azeem", "OWNER_PASSWORD": "short"})


class TestHealth(unittest.TestCase):
    def test_database_health_check(self):
        api = Api()
        try:
            self.assertEqual(api.call("GET", "/api/health?db=1", token=None)[:2], (200, {"status": "UP", "database": "OK"}))
            self.assertEqual(api.call("GET", "/api/health", token=None)[1], {"status": "UP"})
        finally:
            api.close()


class TestCli(unittest.TestCase):
    def test_backup_and_restore_commands(self):
        from app import cli
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        old = config.DATABASE_URL
        try:
            config.DATABASE_URL = "sqlite:///" + os.path.join(tmp.name, "a.db")
            from app.db import connect
            from app.schema import create_schema
            from app.services import purchasing
            db = connect(config.DATABASE_URL); create_schema(db); auth.create_owner(db, "azeem", "a-strong-password")
            purchasing.add_supplier(db, "Haji"); db.conn.close()
            f = os.path.join(tmp.name, "b.json")
            self.assertEqual(cli.main(["backup", f]), 0)
            self.assertTrue(os.path.getsize(f) > 100)
            config.DATABASE_URL = "sqlite:///" + os.path.join(tmp.name, "new.db")          # restore into an empty database
            with mock.patch("builtins.input", return_value="RESTORE"):
                self.assertEqual(cli.main(["restore", f]), 0)
            db = connect(config.DATABASE_URL)
            self.assertEqual(db.one("SELECT name FROM suppliers")["name"], "Haji")
            db.conn.close()
            with mock.patch("builtins.input", return_value="no"):                            # confirmation required
                self.assertEqual(cli.main(["restore", f]), 1)
            with mock.patch("builtins.input", return_value="RESTORE"):                      # bad file changes nothing
                open(f, "w").write("not json")
                self.assertEqual(cli.main(["restore", f]), 1)
            self.assertEqual(cli.main(["nonsense"]), 2)
        finally:
            config.DATABASE_URL = old
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
