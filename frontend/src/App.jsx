import { useEffect, useState } from "react";
import { clearToken, getToken, login, setToken, setUnauthorizedHandler } from "./api.js";
import { ToastProvider } from "./ui.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import Login from "./Login.jsx";
import Layout from "./Layout.jsx";

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));

  const logout = () => { clearToken(); setAuthed(false); };
  useEffect(() => { setUnauthorizedHandler(logout); }, []);

  async function handleLogin(username, password) {
    const { token } = await login(username, password); // throws ApiError on failure
    setToken(token);
    setAuthed(true);
  }

  return (
    <ErrorBoundary onReset={logout}>
      <ToastProvider>
        {authed ? <Layout onLogout={logout} /> : <Login onLogin={handleLogin} />}
      </ToastProvider>
    </ErrorBoundary>
  );
}
