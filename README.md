# AZEEM FRAGRANCES - Personal ERP (single owner)

Private shop-management software for ONE attar and perfume shop and ONE owner: no SaaS, no multi-tenant, no customer sign-up.
You own all the code. Everything runs on free software and free hosting tiers.

## Read this first: what has and has not been verified

| Area | Status | By whom |
|---|---|---|
| Business logic, API layer, PDF, backup/restore | 136 backend tests pass | Claude (in the build environment) |
| Same suite on a Windows PC, **including the 4 FastAPI wrapper tests** | 136/136 passed (before the latest additions) | **you** |
| React app, all 14 screens, driven in headless Chromium against the real backend | 93 browser checks pass (login/logout, purchase-to-sale stock maths, PDF, backup/restore, phone layout, expired session) | Claude |
| Newest additions (PostgreSQL write-lock, self-check, concurrency test, build helper) | tested in the build environment; **not yet run on your PC** | Claude |
| `npm install` + `npm run build` (Vite) | **not run by Claude** (no internet there). Package config hardened; `build.bat` added. Needs your confirmation | open |
| Real PostgreSQL / Supabase | **never run.** Static SQL audit is clean and a self-check script is provided, but only a real PostgreSQL can prove it | open |
| Docker image, Render, Supabase, live website | **not deployed, not verified.** Nothing has been deployed | open |

Expected on your PC: `Ran 142 tests ... OK (skipped=2)` (the 2 skips are the optional real-PostgreSQL tests). Anything else: send me the output.

## What is inside
Owner login (scrypt-hashed password, signed expiring token, lock-out after 5 wrong tries) - Dashboard - Products (price, real cost, margin,
barcode, caps/sprays/packing per bottle) - Attar inventory (grams; kg and ml purchases; per-fragrance density) - Bottles, caps, sprays, packing
inventory (separate) - Suppliers with balances and payments - Purchase invoices with transport (landed cost, average cost) - Production batches
with wastage - Sales POS (search/barcode, multi-item, discount, tax, cash/UPI/card, customer) - PDF invoices - Cancel sale (stock restored) -
Customers - Expenses - Profit & Loss (daily/monthly) - Stock reports with CSV - Settings (shop, tax, alert levels, password) - Backup and restore.

How the attar maths works: 1 kg = 1000 g. ml are converted with the fragrance's own density (never 1 g = 1 ml). A bottle uses
`size_ml x density x oil strength` grams. Purchase cost (incl. transport) updates a moving-average cost per gram. A sale uses ready-filled
bottles first, then fills the rest from raw oil + bottle + caps/packing; cost and tax are frozen on the sale.
Profit = revenue (without tax) - frozen cost of goods - expenses. Buying stock is not an expense; its cost reaches profit when sold.

## Windows installation
Install **Python 3.12** (python.org, tick "Add python.exe to PATH") and **Node.js LTS** (nodejs.org). Use **Command Prompt**.

1. **Backend tests** (in the `backend` folder)

       python -m venv venv
       venv\Scripts\activate
       pip install -r requirements-dev.txt
       python -m unittest discover -s tests -t . -v

2. **Build the website** (in the `frontend` folder)

       npm install
       npm run build

3. **Run the tests again** (step 1 command). Expected: `Ran 142 tests ... OK (skipped=2)`.
   If step 2 fails, read `frontend/BUILD-TROUBLESHOOTING.md` or just run `frontend\build.bat`, and send me the first error lines.
4. **Create your secret key and owner** (in `backend`, venv active)

       python -c "import secrets; print(secrets.token_urlsafe(48))"
       set SECRET_KEY=paste-the-text-printed-above
       python -m app.cli create-owner

5. **Start it**

       uvicorn app.main:app

   Open http://127.0.0.1:8000 and sign in. Your data is the file `backend\azeem.db`.
   (No-install alternative that uses only Python: `python -m app.devserver`.)

Developing the screens with live reload: run the backend (step 5) and in `frontend` run `npm run dev`, then open http://localhost:5173.
Settings are listed in `backend/.env.example`.

## Database setup
* **Local:** nothing to do. `DATABASE_URL=sqlite:///azeem.db` (default). Tables are created and upgraded automatically at start.
* **Cloud:** a free Supabase PostgreSQL project. Steps in `docs/DEPLOY.md`.

## Cloud deployment (free tiers) - see `docs/DEPLOY.md`
One Render Free web service serves both the API and the website, with data in Supabase Free PostgreSQL.
**I did not use Vercel**: its Hobby plan is limited to personal, non-commercial use, which a shop's software does not clearly fit.
Free tiers have real limits (sleeping, no automatic backups, Render says Free is not for production), explained in `docs/DEPLOY.md`.

## Backup and restore - see `docs/BACKUP.md`
Settings -> Download backup (one JSON file with everything). Restore from the same page (needs your password), or with
`python -m app.cli backup` / `restore`. Free Supabase has no automatic backups: **make your own, weekly.**

## Optional: full browser test
See `e2e/README.md`.

## Folder map
`backend/app/core` units, costing, password hashing (original code, kept) - `backend/app/services` business rules - `backend/app/api.py` all routes -
`backend/app/main.py` FastAPI + website serving - `backend/app/devserver.py` standard-library server - `frontend/src` React app - `Dockerfile`, `render.yaml` deployment.
