# Browser end-to-end test (optional)

Drives a real browser through the whole shop: login, every screen, purchase -> production -> sale -> PDF -> cancel,
backup + restore, password change, phone layout, expired session. It uses a throw-away database, never your real one.

1. `cd frontend` then `npm install` then `npm run build`
2. `cd ../e2e` then `npm install --no-save puppeteer`   (downloads a Chromium browser, ~170 MB)
3. Window A:  `python serve.py`
4. Window B:  `node e2e.mjs`      -> expect "93 checks passed, 0 failed"
