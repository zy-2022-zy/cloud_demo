# Cloud Browser Agent

基于 Python、FastAPI 和 Playwright 的云浏览器控制服务。

本项目运行在 Windows 本地，通过 SSH 隧道连接 Debian 服务器上的 Docker Chromium，并通过 HTTP API 提供浏览器操作能力，为后续接入 WorkBuddy、自研 Agent 和 MCP 做准备。

## 一、项目架构

```text
WorkBuddy / 自研 Agent
        |
        | HTTP + X-API-Key
        v
Windows 本地服务
FastAPI + Playwright
        |
        | http://127.0.0.1:19222
        v
SSH 隧道
        |
        v
Debian 服务器
Docker Chromium :9222
```

当前服务连接已有的远程 Chromium，不会另外启动一个浏览器。浏览器进程及其持久化配置由服务器上的 Docker 服务管理。

## 二、运行环境

- Windows 10 / 11
- Python 3.11
- Conda
- Git
- VS Code
- Debian 服务器上的云浏览器 Docker 服务
- 可用的 SSH 连接

## 三、项目目录

```text
cloud_demo/
├── app/
│   ├── __init__.py
│   ├── config.py       # 配置管理
│   ├── browser.py      # Playwright 浏览器操作
│   └── main.py         # FastAPI 接口及鉴权
├── .env.example       # 环境变量模板
├── .env               # 本地环境配置，不提交 Git
├── .gitignore
├── requirements.txt
└── README.md
```

## 四、部署与启动

### 1. 克隆项目

```powershell
git clone https://github.com/zy-2022-zy/cloud_demo.git
cd cloud_demo
git switch feature/cloud-browser-mvp
code .
```

### 2. 创建 Python 环境

使用 Conda 创建环境：

```powershell
conda create -n cloud-browser python=3.11 -y
conda activate cloud-browser
```

安装项目依赖：

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑项目根目录下的 `.env`：

```env
CDP_URL=http://127.0.0.1:19222
API_KEY=替换为至少32位的随机密钥
```

注意：

- `CDP_URL` 是本地 SSH 隧道转发后的 CDP 地址。
- `API_KEY` 用于验证 API 调用权限，至少32个字符。
- `.env` 仅用于本地配置，不要提交到 Git，也不要分享给他人。

### 4. 建立 SSH 隧道

打开一个独立的 PowerShell 窗口，执行：

```powershell
ssh -N `
  -i "$env:USERPROFILE\.ssh\cloud_browser_ed25519" `
  -L 127.0.0.1:16080:127.0.0.1:6080 `
  -L 127.0.0.1:19222:127.0.0.1:9222 `
  root@172.16.9.18
```

保持该窗口运行，不要关闭。

远程浏览器可视化地址：

http://127.0.0.1:16080/vnc.html?autoconnect=true

CDP 连接地址：

http://127.0.0.1:19222

### 5. 启动 FastAPI 服务

在 VS Code 终端中执行：

```powershell
conda activate cloud-browser
python -m uvicorn app.main:app
```

注意：当前 Windows 环境下不要添加 `--reload`。Playwright 的异步连接需要使用兼容的事件循环，启用 Uvicorn 热重载可能导致连接失败。

服务默认监听：

```text
http://127.0.0.1:8000
```

API 文档：

http://127.0.0.1:8000/docs

修改代码后，使用 `Ctrl + C` 停止服务，再重新启动。

## 五、接口调用

所有 `/api/*` 接口都需要在请求头中携带：

```text
X-API-Key: 你的API密钥
```

在另一个 PowerShell 窗口中读取本地密钥：

```powershell
$apiKey = (Get-Content .env | Where-Object { $_ -match '^API_KEY=' } | Select-Object -First 1) -replace '^API_KEY=', ''
$apiKey = $apiKey.Trim()
$headers = @{ "X-API-Key" = $apiKey }
```

不要打印或分享 `$apiKey`。

### 1. 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 2. 获取浏览器连接状态

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/browser/status -Headers $headers
```

### 3. 获取浏览器标签页

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/browser/pages -Headers $headers
```

### 4. 打开网页

```powershell
$body = @{
    url = "https://example.com"
    page_index = 0
} | ConvertTo-Json

Invoke-RestMethod `
    http://127.0.0.1:8000/api/browser/navigate `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### 5. 获取网页内容

```powershell
Invoke-RestMethod `
    "http://127.0.0.1:8000/api/browser/snapshot?page_index=0" `
    -Headers $headers
```

### 6. 点击网页元素

```powershell
$body = @{
    selector = "text=Sign in"
    page_index = 0
} | ConvertTo-Json

Invoke-RestMethod `
    http://127.0.0.1:8000/api/browser/click `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### 7. 填写网页输入框

```powershell
$body = @{
    selector = "input[name='username']"
    value = "example"
    page_index = 0
} | ConvertTo-Json

Invoke-RestMethod `
    http://127.0.0.1:8000/api/browser/fill `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

## 六、API 接口清单

| 请求方式 | 接口 | 功能 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/api/browser/status` | 浏览器连接状态 |
| GET | `/api/browser/pages` | 获取标签页列表 |
| POST |