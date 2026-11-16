"""STATIC PostgreSQL-compatibility audit (not a substitute for running on a real PostgreSQL).
1. Generates the PostgreSQL DDL the app would send (schema + migrations) and checks it for SQLite-only syntax and reserved words.
2. Records every SQL statement the app executes while the whole test-suite runs, and flags constructs that behave
   differently on PostgreSQL (SQLite-only functions, literal % signs, string-built values, etc.).
Run from the backend folder:   python tools/audit_sql.py"""
import re, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db as dbmod
from app.schema import create_schema

RESERVED = set("""all analyse analyze and any array as asc asymmetric both case cast check collate column constraint create current_catalog
current_date current_role current_time current_timestamp current_user default deferrable desc distinct do else end except false fetch for
foreign from grant group having in initially intersect into lateral leading limit localtime localtimestamp not null offset on only or order
placing primary references returning select session_user some symmetric system_user table then to trailing true union unique user using
variadic when where window with""".split())
SQLITE_ONLY = [r"\bAUTOINCREMENT\b", r"\bPRAGMA\b", r"\bIFNULL\s*\(", r"\bSUBSTR\s*\(", r"\bDATETIME\s*\(", r"\bSTRFTIME\s*\(", r"\bGLOB\b",
               r"\bRANDOM\s*\(", r"\bINSERT\s+OR\s+(REPLACE|IGNORE)\b", r"\bREPLACE\s+INTO\b", r"\bROWID\b", r"\bTYPEOF\s*\("]
problems, notes = [], []


class FakeCursor:
    def __init__(self, c): self.c = c
    def execute(self, sql, params=()): self.c.log.append(sql)
    def fetchone(self): return {"id": 1, "version": 1}
    def fetchall(self): return []


class FakeConn:
    def __init__(self): self.log = []
    def cursor(self): return FakeCursor(self)
    def commit(self): pass
    def rollback(self): pass


def audit_postgres_ddl():
    c = FakeConn()
    create_schema(dbmod.Db(c, "postgres"))
    ddl = [s for s in c.log if re.match(r"\s*(CREATE|ALTER)", s, re.I)]
    idents = set()
    for s in ddl:
        for pat in (r"CREATE TABLE IF NOT EXISTS (\w+)", r"ADD COLUMN (\w+)"):
            idents.update(re.findall(pat, s))
        m = re.search(r"CREATE TABLE IF NOT EXISTS \w+ \((.*)\)\s*$", s, re.S)
        if m:
            for part in re.split(r",\s*(?![^()]*\))", m.group(1)):
                w = part.strip().split()
                if w and w[0].upper() not in ("UNIQUE", "PRIMARY", "CHECK", "FOREIGN", "CONSTRAINT"):
                    idents.add(w[0])
    for s in ddl:
        for pat in SQLITE_ONLY:
            if re.search(pat, s, re.I):
                problems.append(f"SQLite-only syntax in PostgreSQL DDL: {pat}  ->  {s[:90]}")
        if "?" in s:
            problems.append("unreplaced ? in DDL: " + s[:80])
    bad = sorted(i for i in idents if i.lower() in RESERVED)
    if bad:
        problems.append("reserved words used as identifiers: " + ", ".join(bad))
    ids = [s for s in ddl if "GENERATED" in s]
    notes.append(f"PostgreSQL DDL statements generated: {len(ddl)} ({len(ids)} tables with identity ids), {len(idents)} identifiers checked against reserved words")


def audit_executed_sql():
    seen = set()
    orig = dbmod.Db.execute

    def rec(self, sql, params=()):
        if self.dialect == "sqlite":
            seen.add(re.sub(r"\s+", " ", sql).strip())
        return orig(self, sql, params)
    dbmod.Db.execute = rec
    try:
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent.parent / "tests"), top_level_dir=str(Path(__file__).resolve().parent.parent))
        res = unittest.TextTestRunner(stream=open("nul" if sys.platform == "win32" else "/dev/null", "w"), verbosity=0).run(suite)
    finally:
        dbmod.Db.execute = orig
    notes.append(f"test-suite run while recording: {res.testsRun} tests, {len(res.failures) + len(res.errors)} failed")
    dml = sorted(s for s in seen if not re.match(r"(CREATE|ALTER|BEGIN|COMMIT|ROLLBACK|PRAGMA|DROP)", s, re.I))
    funcs = set()
    for s in dml:
        funcs.update(f.upper() for f in re.findall(r"\b([A-Za-z_]+)\s*\(", s) if f.upper() not in ("VALUES", "IN", "AND", "OR", "ON", "SET"))
        for pat in SQLITE_ONLY:
            if re.search(pat, s, re.I) and "AUTOINCREMENT" not in pat:
                problems.append(f"SQLite-only construct in: {s[:100]}")
        if "%" in s:
            problems.append("literal % in SQL text (psycopg treats % as a placeholder): " + s[:100])
        if re.search(r"'[^']*\?[^']*'", s):
            problems.append("? inside a string literal: " + s[:100])
        if re.search(r"\bLIKE\b", s, re.I) and not re.search(r"LIKE\s+\?", s, re.I):
            problems.append("LIKE with an inline pattern: " + s[:100])
        if re.search(r"\bGROUP BY\b", s, re.I):
            notes.append("GROUP BY present (PostgreSQL needs every selected column grouped): " + s[:90])
    notes.append(f"distinct DML statements executed: {len(dml)}")
    notes.append("SQL functions used: " + ", ".join(sorted(f for f in funcs if f.isalpha())))
    ci = [s for s in dml if re.search(r"\bLIKE\b", s, re.I)]
    notes.append(f"{len(ci)} LIKE queries (PostgreSQL LIKE is case-SENSITIVE; the app lower-cases where it needs case-insensitive search)")
    for s in ci:
        if re.search(r"LOWER\(", s, re.I) is None and "sold_on" not in s and "spent_on" not in s and "made_on" not in s:
            notes.append("   check case-sensitivity: " + s[:100])


if __name__ == "__main__":
    audit_postgres_ddl()
    audit_executed_sql()
    print("\n".join("note: " + n for n in notes))
    print()
    if problems:
        print("PROBLEMS FOUND:\n" + "\n".join(" - " + p for p in dict.fromkeys(problems)))
        sys.exit(1)
    print("No PostgreSQL-incompatible constructs found by this static audit.")
    print("(This does NOT prove it runs on PostgreSQL. Run: set TEST_POSTGRES_URL=... and the tests, see docs/DEPLOY.md.)")
