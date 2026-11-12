# Frontend build troubleshooting (Windows)

Normal path: in this `frontend` folder run `build.bat` (or `npm install` then `npm run build`). Success ends with a `dist` folder.

If something fails, **copy the first 15-20 error lines and send them to Claude**. The usual causes:

| Message | Cause and fix |
|---|---|
| `npm : File ...npm.ps1 cannot be loaded because running scripts is disabled` | PowerShell policy. Use **Command Prompt** (cmd), not PowerShell. |
| `EPERM`, `EBUSY`, `operation not permitted, unlink/rename ... esbuild` | Antivirus or OneDrive is locking files. Move the whole project to a plain folder such as `C:\azeem-erp` (not Desktop/Documents/OneDrive), close editors, delete `node_modules`, run again. If it still fails, pause antivirus for that folder while installing. |
| `EACCES` / `Permission denied` on `vite` (Linux, WSL, or a folder unzipped from Windows) | The `vite` shortcut lost its execute permission. Use `npm run build:safe` (runs Vite through `node`), or `chmod -R +x node_modules/.bin`. |
| `Unsupported engine` / `SyntaxError: Unexpected token '?'` / `crypto.getRandomValues is not a function` | Node is too old. Install Node 18 or newer (LTS) from nodejs.org. |
| `ENOTFOUND`, `ETIMEDOUT`, `ECONNRESET` | No internet or a proxy is blocking the npm registry. |
| `Cannot find module '@rollup/rollup-win32-x64-msvc'` (or similar) | Half-finished install. Delete `node_modules` AND `package-lock.json`, run `npm install` again. |
| Anything about the project being inside a `.zip` | Extract the ZIP fully first. |

Clean reinstall: delete the `node_modules` folder and `package-lock.json`, then `npm install` and `npm run build`.
