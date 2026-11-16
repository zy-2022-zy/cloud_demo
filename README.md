# Cloud Browser Agent

A local Python service that controls the existing Chromium instance on the Debian server through an SSH-forwarded Chrome DevTools Protocol (CDP) endpoint.

## Architecture

```text
WorkBuddy / Agent
       |
       | HTTP + X-API-Key (planned MCP adapter can call this API)
       v
Windows: FastAPI + Playwright
       |
       | http://127.0.0.1:19222
       v
SSH tunnel
       |
       v
Debian Docker: Chromium CDP :9222
```

This project does **not** launch a second browser. It connects to the already-running remote Chromium. The remote browser and its persistent profile remain managed by the existing Docker service.

## Requirements

- Windows 10/11
- Python 3.11 or newer
- Git
- The Debian cloud-browser Docker container running
- SSH access to the Debian server

## 1. Start the SSH tunnel

Open a dedicated Windows PowerShell window and keep it open:

```powershell
ssh -N `
  -i "$env:USERPROFILE\.ssh\cloud_browser_ed25519" `
  -L 127.0.0.1:16080:127.0.0.1:6080 `
  -L 127.0.0.1:19222:127.0.0.1:9222 `
  root@172.16.9.18
```

The API uses the forwarded CDP endpoint `http://127.0.0.1:19222`. The noVNC page remains available at `http://127.0.0.1:16080/vnc.html?autoconnect=true`.

## 2. Open the project in VS Code

Clone the repository and switch to the implementation branch:

```powershell
git clone https://github.com/zy-2022-zy/cloud_demo.git
cd cloud_demo
git switch feature/cloud-browser-mvp
code .
```

## 3. Create a virtual environment

Run in the VS Code terminal (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use this for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Configure local settings

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace `API_KEY` with a long random value. Do not commit `.env` or share the key. The default CDP URL is already set to `http://127.0.0.1:19222`.

## 5. Start the API

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep the API bound to loopback. Do not expose this browser-control API directly to the public internet.

Open the interactive API docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## 6. Verify the remote browser connection

In another PowerShell terminal, set the same API key that you configured in `.env`:

```powershell
$env:CLOUD_BROWSER_API_KEY = "your-local-api-key"
$headers = @{ "X-API-Key" = $env:CLOUD_BROWSER_API_KEY }
Invoke-RestMethod http://127.0.0.1:8000/api/browser/status -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/api/browser/pages -Headers $headers
```

Open a page:

```powershell
$body = @{ url = "https://example.com" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/browser/navigate -Method Post -Headers $headers -ContentType "application/json" -Body $body
Invoke-RestMethod http://127.0.0.1:8000/api/browser/snapshot -Headers $headers
```

## API endpoints

All `/api/*` endpoints require the `X-API-Key` header.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API process health |
| GET | `/api/browser/status` | CDP connection and browser version |
| GET | `/api/browser/pages` | List tabs |
| POST | `/api/browser/navigate` | Navigate a tab |
| GET | `/api/browser/snapshot` | Read page title, URL and body text |
| POST | `/api/browser/click` | Click the first matching selector |
| POST | `/api/browser/fill` | Fill the first matching input |

Example click request body:

```json
{ "selector": "text=Sign in", "page_index": 0 }
```

Example fill request body:

```json
{ "selector": "input[name='username']", "value": "example", "page_index": 0 }
```

## Security notes

- API listens on `127.0.0.1` by default and requires an API key for browser operations.
- Keep `.env` private. Never commit passwords, SMS codes, session cookies, or API keys.
- Do not log form values or authentication codes.
- This MVP is intended for one local developer session. Before multi-user deployment, add per-user browser contexts, authorization, rate limits, audit redaction and credential expiry.
- Human verification, CAPTCHA, MFA and QR-code steps must pause for the user rather than be bypassed.
- The API disconnects its Playwright client on shutdown; it does not close the remote Chromium process.
