// Browser test of the WHOLE app (real backend + built React app). Needs: `npm install --no-save puppeteer` (downloads Chromium),
// `npm run build` in ../frontend, and `python serve.py` running in another window. Run:  node e2e.mjs
import fs from "fs";
import os from "os";
import path from "path";
let puppeteer;
try { puppeteer = (await import("puppeteer")).default; } catch { puppeteer = (await import("puppeteer-core")).default; }
const BASE = process.env.E2E_URL || "http://127.0.0.1:8765";
const BACKUP_FILE = path.join(os.tmpdir(), "azeem-e2e-backup.json");
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || undefined, args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900 });
page.setDefaultTimeout(8000);

const problems = [];
page.on("pageerror", (e) => problems.push("PAGEERROR " + e));
page.on("console", (m) => { if (m.type() === "error" && !/status of 4\d\d/.test(m.text())) problems.push("CONSOLE " + m.text()); });
let pass = 0, fail = 0;
const check = (cond, name) => { if (cond) { pass++; console.log("ok  :", name); } else { fail++; console.log("FAIL:", name); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const text = () => page.evaluate(() => document.body.innerText);
const has = async (t) => (await text()).toLowerCase().includes(t.toLowerCase());
const waitText = async (t, ms = 8000) => { try { await page.waitForFunction((t) => document.body.innerText.toLowerCase().includes(t.toLowerCase()), { timeout: ms }, t); return true; } catch { return false; } };
const gone = async (t) => { try { await page.waitForFunction((t) => !document.body.innerText.toLowerCase().includes(t.toLowerCase()), { timeout: 5000 }, t); return true; } catch { return false; } };

// ---- helpers that work on real DOM controls (React controlled inputs need native setters + events)
const scopeSel = () => page.evaluate(() => (document.querySelector(".modal") ? ".modal" : "main.content, .login-card"));
async function fill(label, value, nth = 0) {
  const ok = await page.evaluate((label, value, nth) => {
    const root = document.querySelector(".modal") || document.querySelector("main.content") || document.body;
    const ls = [...root.querySelectorAll("label")].filter((l) => { const t = (l.querySelector(":scope > span")?.textContent ?? l.childNodes[0]?.textContent ?? "").trim().toLowerCase(); return t.startsWith(label.toLowerCase()); });
    const el = ls[nth]?.querySelector("input, select, textarea");
    if (!el) return false;
    if (el.tagName === "SELECT") {
      const opt = [...el.options].find((o) => o.textContent.trim().toLowerCase().includes(String(value).toLowerCase()) || o.value === String(value));
      if (!opt) return false;
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, opt.value);
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    return true;
  }, label, value, nth);
  if (!ok) throw new Error(`cannot fill "${label}"`);
}
async function fillAria(aria, value, nth = 0) {
  const ok = await page.evaluate((aria, value, nth) => {
    const els = [...document.querySelectorAll(`[aria-label="${aria}"]`)];
    const el = els[nth]; if (!el) return false;
    if (el.tagName === "SELECT") {
      const opt = [...el.options].find((o) => o.textContent.trim().toLowerCase().includes(String(value).toLowerCase()) || o.value === String(value));
      if (!opt) return false;
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, opt.value);
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    return true;
  }, aria, value, nth);
  if (!ok) throw new Error(`cannot fill aria "${aria}"`);
}
async function click(label, { nth = 0, scope = null, exact = true, inRow = null } = {}) {
  const ok = await page.evaluate((label, nth, scope, exact, inRow) => {
    const root = scope ? document.querySelector(scope) : (document.querySelector(".modal") || document.querySelector("main.content") || document.body);
    let els = [...root.querySelectorAll("button, a.btn, [role=tab]")].filter((b) => !b.disabled);
    els = els.filter((b) => { const t = (b.getAttribute("aria-label") || b.textContent).trim(); return exact ? t === label : t.includes(label); });
    if (inRow) els = els.filter((b) => b.closest("tr")?.textContent.includes(inRow));
    const el = els[nth]; if (!el) return false;
    el.click(); return true;
  }, label, nth, scope, exact, inRow);
  if (!ok) throw new Error(`cannot click "${label}"${inRow ? " in row " + inRow : ""}`);
  await sleep(150);
}
async function submitForm() { // click the gold submit button of the open form
  await page.evaluate(() => {
    const root = document.querySelector(".modal") || document.querySelector("main.content") || document.body;
    const form = root.querySelector("form"); form.requestSubmit();
  });
  await sleep(250);
}
const nav = async (id) => { await page.evaluate((id) => { location.hash = "#/" + id; }, id); await sleep(300); };
const h1 = () => page.evaluate(() => document.querySelector("h1")?.textContent.trim());

// ============================================================ LOGIN
await page.goto(BASE + "/", { waitUntil: "networkidle0" });
check(await has("Owner sign in"), "login screen is shown first");
await fill("Username", "azeem"); await fill("Password", "wrong-password-1"); await submitForm();
check(await waitText("invalid credentials"), "wrong password shows an error and stays on login");
await fill("Password", "a-strong-password"); await submitForm();
check(await waitText("Today's sales"), "correct login opens the dashboard");

// ============================================================ every navigation item opens its page
const pages = { dashboard: "Dashboard", pos: "Sales POS", invoices: "Invoices", customers: "Customers", products: "Products", attar: "Attar Inventory",
  bottles: "Bottles & Supplies", production: "Production", suppliers: "Suppliers", purchases: "Purchases", expenses: "Expenses", reports: "Profit & Loss",
  stock: "Stock Reports", settings: "Settings" };
for (const [id, title] of Object.entries(pages)) {
  await page.evaluate((id) => document.querySelector(`.sidebar nav a[href="#/${id}"]`).click(), id);
  await sleep(350);
  check((await h1()) === title, `sidebar link opens "${title}"`);
}
check(await page.evaluate(() => document.querySelector(".sidebar nav a.active")?.textContent === "Settings"), "active sidebar item is highlighted");

// ============================================================ SETTINGS
await nav("settings"); await waitText("Shop and invoice");
await fill("Phone", "0300 1234567"); await fill("UPI ID", "azeem@upi"); await fill("Tax rate", "5"); await fill("Attar oil (grams)", "2000");
await click("Save settings"); check(await waitText("Settings saved"), "settings saved");

// ============================================================ ATTAR INVENTORY
await nav("attar"); await waitText("No fragrances yet");
await click("Add fragrance");
await fill("Name", "Oudh Royal"); await fill("Density", "0.90"); await submitForm();
check(await waitText("Fragrance added") && await waitText("Oudh Royal"), "fragrance added");
await click("Edit", { inRow: "Oudh Royal" }); await fill("Name", "Oudh Royal Gold"); await submitForm();
check(await waitText("Oudh Royal Gold"), "fragrance edited");

// ============================================================ BOTTLES & SUPPLIES
await nav("bottles"); await waitText("12 ml bottle");
check(await has("100 ml bottle") && await has("6 ml bottle"), "default bottle sizes 6/12/30/50/100 ml are listed");
await click("Caps"); await waitText("Nothing here yet");
await click("Add cap"); await fill("Name", "Gold cap"); await submitForm();
check(await waitText("Gold cap"), "cap added");
await click("Sprays"); await click("Add spray"); await fill("Name", "Spray pump"); await submitForm();
check(await waitText("Spray pump"), "spray added");
await click("Packing"); await click("Add packing item"); await fill("Name", "Gift box"); await submitForm();
check(await waitText("Gift box"), "packing item added");

// ============================================================ SUPPLIERS
await nav("suppliers"); await waitText("No suppliers yet");
await click("Add supplier"); await fill("Name", "Haji & Sons"); await fill("Phone", "0300111"); await submitForm();
check(await waitText("Supplier added") && await waitText("Haji & Sons"), "supplier added");

// ============================================================ PURCHASES (invoice with transport, part payment)
await nav("purchases"); await waitText("New purchase invoice");
await fill("Supplier", "Haji"); await fill("Supplier invoice no.", "H-101");
await fillAria("Item", "Oudh Royal Gold", 0); await fillAria("Quantity", "1", 0); await fillAria("Unit", "kg", 0); await fillAria("Line price", "50000", 0);
await click("Add another item");
await fillAria("Type", "bottle", 1); await fillAria("Item", "12 ml", 1); await fillAria("Quantity", "30", 1); await fillAria("Line price", "1200", 1);
await click("Add another item");
await fillAria("Type", "supply", 2); await fillAria("Item", "Gold cap", 2); await fillAria("Quantity", "100", 2); await fillAria("Line price", "500", 2);
await fill("Transport charges", "1000"); await fill("Paid to supplier now", "10000");
check(await has("Rs. 52,700.00"), "purchase form shows total landed cost 52,700 (goods 51,700 + transport 1,000)");
await click("Save purchase and update stock");
check(await waitText("Purchase saved"), "purchase invoice saved");
check(await has("H-101") && await has("Gold cap"), "purchase history lists the lines");
await nav("attar"); await waitText("Oudh Royal Gold");
check(await has("1,000") && await has("1 ") , "1 kg purchase shows as 1,000 g in attar inventory");
await nav("suppliers"); await waitText("Haji & Sons");
check(await has("Rs. 42,700.00"), "supplier balance due is 42,700 (52,700 landed - 10,000 paid)");
await click("Record payment"); await fill("Amount", "2700"); await submitForm();
check(await waitText("Payment recorded") && await waitText("Rs. 40,000.00"), "supplier payment recorded, balance 40,000");
await click("Payments"); check(await waitText("Rs. 2,700.00") && await has("Rs. 10,000.00"), "payment history shows both payments");
await page.keyboard.press("Escape");

// ============================================================ PRODUCTS
await nav("products"); await waitText("No products found");
await click("Add product");
await fill("Product name", "Oudh Royal 12ml"); await fill("Fragrance", "Oudh Royal Gold"); await fill("Bottle size", "12 ml"); await fill("Selling price", "1300"); await fill("Barcode", "8901234500012"); await submitForm();
check(await waitText("Product added") && await waitText("Oudh Royal 12ml"), "product added");
check(await has("10.8 g") && await has("Rs. 1,300.00"), "oil per bottle uses density (12 ml x 0.9 = 10.8 g)");
await click("Caps/packing"); await waitText("Gold cap"); await fillAria("Gold cap per bottle", "1"); await click("Save");
check(await waitText("Components saved"), "cap-per-bottle saved");
check(await has("Rs. 5") , "product cost shown (oil + bottle + cap)");
await click("Edit", { inRow: "Oudh Royal 12ml" }); await fill("Selling price", "1350"); await submitForm();
check(await waitText("Product updated") && await waitText("Rs. 1,350.00"), "product edited");
await click("Edit", { inRow: "Oudh Royal 12ml" }); await fill("Selling price", "1300"); await submitForm(); await waitText("Rs. 1,300.00");
await fill("Search", "zzzz", 0).catch(() => {});
await page.evaluate(() => { const el = document.querySelector("input.search"); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, "zzzz"); el.dispatchEvent(new Event("input", { bubbles: true })); });
check(await waitText("No products found"), "product search filters the list");
await page.evaluate(() => { const el = document.querySelector("input.search"); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, "8901234500012"); el.dispatchEvent(new Event("input", { bubbles: true })); });
check(await waitText("Oudh Royal 12ml"), "product found by barcode");

// ============================================================ PRODUCTION (batch with wastage)
await nav("production"); await waitText("New batch");
await fill("Product", "Oudh Royal 12ml"); await fill("Bottles filled", "10"); await fill("Wastage", "2");
check(await waitText("Needs 110 g"), "batch preview: 10 x 10.8 g + 2 g wastage = 110 g");
await click("Record batch"); check(await waitText("Batch recorded"), "production batch recorded");
check(await has("110") && await has("Rs. 6,065"), "batch history shows oil used 110 g and total cost");
await nav("attar"); await waitText("Oudh Royal Gold"); check(await has("890"), "oil stock reduced to 890 g after the batch");
await nav("products"); await waitText("Oudh Royal 12ml");
check(await page.evaluate(() => [...document.querySelectorAll("tbody tr")].some((r) => r.textContent.includes("Oudh Royal 12ml") && /\b10\b/.test(r.children[6].textContent))), "ready stock shows 10 filled bottles");

// ============================================================ CUSTOMERS
await nav("customers"); await waitText("No customers yet");
await click("Add customer"); await fill("Name", "Ali Khan"); await fill("Phone", "0300555"); await submitForm();
check(await waitText("Customer added") && await waitText("Ali Khan"), "customer added");

// ============================================================ POS
await nav("pos"); await waitText("Search product or scan barcode");
await page.type('input[aria-label="Search product or scan barcode"]', "8901234500012"); await page.keyboard.press("Enter"); await sleep(300);
check(await has("Current bill") && await page.evaluate(() => document.querySelector("table.cart") !== null), "scanning the barcode (type + Enter) adds the product to the bill");
await fillAria("Quantity Oudh Royal 12ml", "12");
await fill("Customer", "Ali Khan"); await fill("Payment", "UPI"); await fill("Discount", "100");
check(await has("Rs. 15,600.00") && await has("Rs. 100.00") && await has("Rs. 775.00") && await has("Rs. 16,275.00"), "bill: subtotal 15,600, discount 100, GST 5% = 775, total 16,275");
await click("Complete sale");
check(await waitText("Sale recorded") && await has("INV-000001"), "sale completed with invoice number INV-000001");
let pdfOk = false;
page.on("response", (r) => { if (r.url().includes("/invoice.pdf") && r.status() === 200 && (r.headers()["content-type"] || "").includes("pdf")) pdfOk = true; });
await click("Open PDF invoice"); await sleep(800);
check(pdfOk, "PDF invoice downloads (application/pdf, HTTP 200)");
await click("New sale"); await waitText("Search product or scan barcode");

// ============================================================ INVOICES
await nav("invoices"); await waitText("INV-000001");
await click("View"); check(await waitText("Oudh Royal 12ml") && await has("Tax (5%)") && await has("Rs. 16,275.00"), "invoice details show items, tax and total");
await page.keyboard.press("Escape"); await sleep(200);
await page.evaluate(() => { const el = document.querySelector("input.search"); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, "nobody"); el.dispatchEvent(new Event("input", { bubbles: true })); });
check(await waitText("No sales found"), "invoice search filters");
await page.evaluate(() => { const el = document.querySelector("input.search"); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, "ali"); el.dispatchEvent(new Event("input", { bubbles: true })); });
check(await waitText("INV-000001"), "invoice search finds sale by customer name");
await nav("attar"); await waitText("Oudh Royal Gold"); check(await has("868.4"), "sale deducted oil: 890 - 2 x 10.8 g = 868.4 g (10 bottles came from finished stock)");
await nav("bottles"); await waitText("12 ml bottle"); check(await page.evaluate(() => [...document.querySelectorAll("tbody tr")].some((r) => r.textContent.includes("12 ml bottle") && r.children[1].textContent.trim() === "18")), "bottle stock 30 - 10 (batch) - 2 (sale) = 18");

// ============================================================ DASHBOARD + REPORTS before cancelling
await nav("dashboard"); await waitText("Today's sales");
check(await has("Rs. 15,500.00"), "dashboard: today's sales = 15,500 (revenue excludes the 775 tax)");
check(await has("Inventory value") && await has("Best-selling fragrances") && await has("Low stock alerts"), "dashboard shows inventory value, best sellers and low-stock alerts");
check(await has("Oudh Royal Gold"), "best seller listed");
await nav("reports"); await waitText("Profit & Loss");
check(await has("Rs. 15,500.00") && await has("Rs. 775.00"), "monthly P&L: revenue 15,500, tax collected 775");
check(await has("Oil wastage in production: 2 g"), "wastage reported");
await click("Daily"); await waitText("Sales on"); check(await has("INV-000001"), "daily report lists the day's sales");
await click("Monthly"); await waitText("Day by day");
await click("Download CSV"); await sleep(300);

// ============================================================ EXPENSES
await nav("expenses"); await waitText("Add expense");
await fill("Amount", "500"); await fill("Note", "shop rent"); await click("Add expense");
check(await waitText("Expense added") && await waitText("shop rent"), "expense added");
await nav("reports"); await waitText("Profit & Loss"); check(await has("Expenses by category") && await has("Rent"), "expense appears in P&L");
await nav("expenses"); await waitText("shop rent"); await click("Delete"); await click("Delete", { scope: ".modal" });
check(await waitText("Expense deleted") && await gone("shop rent"), "expense deleted after confirmation");

// ============================================================ STOCK REPORTS
await nav("stock"); await waitText("Total inventory value");
check(await has("Attar oil") && await has("Bottle") && await has("Cap"), "stock report lists oil, bottles and caps");
await page.evaluate(() => { const c = document.querySelector('.check input'); c.click(); }); await sleep(300);
check(await has("Out of stock") || await has("Low"), "low-stock filter shows low/out items");
await click("Download CSV"); await sleep(300);
await page.evaluate(() => document.querySelector('.check input').click());

// ============================================================ CANCEL SALE restores stock
await nav("invoices"); await waitText("INV-000001");
await click("Cancel sale"); await fill("Reason", "customer returned"); await click("Cancel this sale", { scope: ".modal" });
check(await waitText("Sale cancelled") && await waitText("Cancelled"), "sale cancelled");
await nav("attar"); await waitText("Oudh Royal Gold"); check(await has("890"), "cancelling restored the oil (890 g)");
await nav("dashboard"); await waitText("Today's sales"); check(await has("0 sales and 0 items sold today") || await has("Rs. 0.00"), "cancelled sale removed from today's figures");

// ============================================================ ATTAR: count stock + history
await nav("attar"); await waitText("Oudh Royal Gold");
await click("Count stock"); await fill("Counted quantity", "880"); await submitForm();
check(await waitText("Stock updated") && await has("880"), "stock count adjusts oil to 880 g");
await click("History"); check(await waitText("Stock count") && await has("Purchase") && await has("Production"), "stock history lists purchase, production and count");
await page.keyboard.press("Escape");

// ============================================================ SETTINGS: password, backup, restore
await nav("settings"); await waitText("Backup and restore");
let backupStatus = 0;
page.on("response", (r) => { if (r.url().endsWith("/api/backup")) backupStatus = r.status(); });
await click("Download backup"); check(await waitText("Backup downloaded"), "Download backup button works"); await sleep(300);
check(backupStatus === 200, "backup request succeeded (HTTP 200)");
const backupText = await page.evaluate(async () => (await fetch("/api/backup", { headers: { Authorization: "Bearer " + sessionStorage.getItem("azeem_token") } })).text());
check(JSON.parse(backupText).app === "azeem-erp", "backup file content is a valid AZEEM backup");
fs.writeFileSync(BACKUP_FILE, backupText);
// change data after the backup, then restore
await nav("expenses"); await waitText("Add expense"); await fill("Amount", "77"); await fill("Category", "AfterBackup"); await click("Add expense"); await waitText("Expense added");
await nav("settings"); await waitText("Backup and restore");
const fileInput = await page.$('input[type=file]'); await fileInput.uploadFile(BACKUP_FILE);
await fill("Your password", "wrong-password-1"); await click("Restore backup"); await click("Yes, replace everything");
check(await waitText("wrong password"), "restore refuses a wrong password");
await sleep(300);
await fill("Your password", "a-strong-password"); await click("Restore backup"); await click("Yes, replace everything");
check(await waitText("Backup restored"), "restore with correct password succeeds");
await sleep(2200); await waitText("Today's sales").catch(() => {}); 
await nav("expenses"); await waitText("Add expense"); check(await gone("AfterBackup"), "data after the backup is gone: restore worked");
await nav("settings"); await waitText("Change password");
await fill("Current password", "a-strong-password"); await fill("New password (10+", "brand-new-password-9"); await fill("New password again", "brand-new-password-9");
await click("Change password", { scope: "main.content", nth: 1 }).catch(async () => { await click("Change password"); });
check(await waitText("Password changed"), "password changed");

// ============================================================ MOBILE layout
await page.setViewport({ width: 390, height: 800 });
await nav("dashboard"); await waitText("Today's sales");
check(await page.evaluate(() => document.querySelector(".sidebar").getBoundingClientRect().right <= 0), "mobile: sidebar is hidden by default");
await click("Open menu", { scope: ".topbar" }); await sleep(500);
check(await page.evaluate(() => document.querySelector(".sidebar").getBoundingClientRect().left >= 0), "mobile: Menu button opens the sidebar");
await page.evaluate(() => document.querySelector('.sidebar nav a[href="#/pos"]').click()); await sleep(400);
check((await h1()) === "Sales POS" && await page.evaluate(() => document.querySelector(".sidebar").getBoundingClientRect().right <= 0), "mobile: choosing a page closes the sidebar");
for (const id of ["dashboard", "pos", "purchases", "products", "reports", "invoices", "settings"]) {
  await nav(id); await sleep(500);
  const ok = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  check(ok, `mobile 390px: no sideways page scroll on ${id}`);
}
await page.setViewport({ width: 1280, height: 900 });

// ============================================================ SIGN OUT / EXPIRED SESSION
await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.textContent === "Sign out").click());
check(await waitText("Owner sign in") && await page.evaluate(() => sessionStorage.getItem("azeem_token") === null), "sign out returns to login and clears the token");
await fill("Username", "azeem"); await fill("Password", "brand-new-password-9"); await submitForm();
check(await waitText("Shop and invoice"), "can sign in again with the NEW password (returns to the page you were on)");
await page.evaluate(() => sessionStorage.setItem("azeem_token", "garbage-token")); await page.reload({ waitUntil: "networkidle0" });
check(await waitText("Owner sign in"), "an invalid/expired token sends the owner back to login");
check(await page.evaluate(() => localStorage.length === 0), "nothing stored in localStorage");

check(problems.length === 0, "no unexpected browser errors" + (problems.length ? ": " + problems.join(" | ").slice(0, 600) : ""));
await browser.close();
console.log(`\n${pass} checks passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
