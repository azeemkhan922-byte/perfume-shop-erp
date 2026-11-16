# Free cloud deployment (Render Free + Supabase Free)

**Status: prepared, NOT deployed or verified.** Do not treat the site as live until you can sign in at your own https address
and the checklist at the bottom passes.

## What the free tiers actually give you (checked while preparing this)
* **Vercel Hobby - not used.** It is for personal, non-commercial use. Business software for a shop does not clearly qualify. The same React app is served by the Render service instead, so you need no third host.
* **Render Free web service:** sleeps after about 15 minutes without requests and takes about a minute to wake; disk is wiped on restart (so the database must be external - it is); Render's own docs say Free is not meant for production. Render's own free PostgreSQL expires after 30 days: **not used.**
* **Supabase Free PostgreSQL:** 500 MB; the project is paused after about a week without activity; **no automatic backups**. Its direct connection is IPv6-only, so use the **Session pooler** connection string (works over IPv4). Check current limits on supabase.com/pricing before relying on them.
Terms change. Re-read the pricing pages before you commit.

## Steps
1. **Code on GitHub.** Create a PRIVATE repository and push this folder. (`.gitignore` already excludes databases and secrets.)
2. **Supabase.** New project, choose a region near you, set and SAVE a database password. Click **Connect**, pick **Session pooler**, copy the URI
   (looks like `postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-REGION.pooler.supabase.com:5432/postgres`), put your password in,
   and add `?sslmode=require` at the end. Special characters in the password must be URL-encoded.
3. **Render.** New -> Blueprint -> pick the repository (it reads `render.yaml`; region is set to Singapore, so create the Supabase project in Singapore or Mumbai). Fill in:
   * `DATABASE_URL` = the string from step 2
   * `OWNER_USERNAME` and `OWNER_PASSWORD` = your login (10+ characters). They are used only to create the owner on the very first start.
   `SECRET_KEY` is generated for you. Deploy; the first build takes several minutes.
4. **After the first successful start, delete `OWNER_USERNAME` and `OWNER_PASSWORD`** in Render -> Environment, so no password stays stored there.
5. **Keep it awake (optional).** A free monitor (for example UptimeRobot - check its current free terms) calling
   `https://YOUR-APP.onrender.com/api/health?db=1` every 5 minutes keeps the service awake and touches the database so Supabase does not pause it.
   Without it: the first page load after idle takes about a minute.
6. **Updating later:** push to GitHub; Render redeploys. Tables upgrade themselves at start; download a backup first.

## Test PostgreSQL BEFORE deploying (recommended, free, safe)
The code was only ever run on SQLite. These checks run the whole shop workflow on a real PostgreSQL **inside a temporary schema that is deleted
afterwards; your real tables are never touched.** In `backend` with the venv active (`pip install -r requirements-dev.txt` once):

    set DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
    python -m app.selfcheck

Expected: a list of `ok` lines ending with `All checks passed.`. Then also run the two PostgreSQL unit tests (they include a two-cash-registers-at-once test):

    set TEST_POSTGRES_URL=%DATABASE_URL%
    python -m unittest tests.test_selfcheck_and_concurrency -v

Use the **Session pooler** string (port 5432). The "Transaction pooler" (port 6543) does not keep per-connection settings and is not supported.
No Supabase yet? Install free PostgreSQL for Windows from postgresql.org, or run `docker run -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16`,
and use `postgresql://postgres:pw@localhost:5432/postgres`.
If any line says FAIL, send me the full output. Also available: `python tools/audit_sql.py` (static check, works offline).

On PostgreSQL every write waits for the previous one (a database lock), so two devices can never sell the same last bottle. SQLite does the same by itself.

## Verification checklist (do all of these on the live site)
- [ ] `https://YOUR-APP.onrender.com/api/health?db=1` shows `"database": "OK"`
- [ ] You can sign in, and a wrong password is refused
- [ ] Add a fragrance, a supplier, a purchase, a product, make a sale, open the PDF invoice
- [ ] Settings -> Download backup works, and the file opens as text
- [ ] Wait 20 minutes, reload: data is still there (proves it is in Supabase, not on Render's disk)

## Things only you can confirm
Whether the Docker build succeeds on Render, whether the pooler string connects from Render, and how long wake-ups take. I could not test any of these.
