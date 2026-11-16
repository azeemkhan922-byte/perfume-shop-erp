// Same-origin by default: in production the backend serves this app; in `npm run dev` Vite proxies /api to the backend.
// Set VITE_API_URL only if the backend lives on a different address.
const BASE = import.meta.env.VITE_API_URL || "";
const KEY = "azeem_token";

export const getToken = () => sessionStorage.getItem(KEY); // cleared when the tab closes
export const setToken = (t) => sessionStorage.setItem(KEY, t);
export const clearToken = () => sessionStorage.removeItem(KEY);

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

async function send(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* keep statusText */ }
    if (res.status === 401 && path !== "/api/login") onUnauthorized(); // session expired
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }
  return res;
}

const json = async (path, opts) => (await send(path, opts)).json();

export const api = {
  get: (p) => json(p),
  post: (p, body = {}) => json(p, { method: "POST", body }),
  put: (p, body = {}) => json(p, { method: "PUT", body }),
  del: (p) => json(p, { method: "DELETE" }),
};

export const login = (username, password) => api.post("/api/login", { username, password });

export async function fetchBlob(path) {
  return (await send(path)).blob();
}

// Opens a PDF (invoice) in a new tab. The tab is opened first so pop-up blockers allow it.
export async function openPdf(path) {
  const w = window.open("", "_blank");
  try {
    const url = URL.createObjectURL(await fetchBlob(path));
    if (w) w.location.href = url;
    else saveUrl(url, "invoice.pdf");
  } catch (e) {
    if (w) w.close();
    throw e;
  }
}

function saveUrl(url, filename) {
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
}

export async function downloadFile(path, filename) {
  saveUrl(URL.createObjectURL(await fetchBlob(path)), filename);
}

export function downloadText(text, filename, type = "text/csv") {
  saveUrl(URL.createObjectURL(new Blob([text], { type })), filename);
}
