
# MCP Proxmox AI Operator 🤖

An intelligent companion for your Proxmox data center.  
This project enables natural language control of Proxmox clusters—either as an MCP (Model Context Protocol) server for integrations like LibreChat or as an interactive CLI bot.

---

## ✨ Features

- **VM Management:** List, start, stop, and create VMs.
- **Intelligent VM Creation:** Automatically search for matching ISO files in `local` storage.
- **Cloud-Init Support:** Automated setup for users, passwords, and networking.
- **Resource Monitoring:** Query CPU and RAM utilization for nodes and individual VMs.
- **Snapshot Management:** Create, list, and roll back snapshots.

---

## 🏗️ Project Structure

- `mcp_server.py`: Entry point for running as an MCP server via SSE (Server-Sent Events).
- `main.py`: Interactive CLI bot for direct communication with a local Ollama instance.
- `proxmox_mgr.py`: API interface to Proxmox built on `proxmoxer`.
- `Dockerfile` & `docker-compose.yml`: Full containerization for easy deployment.

---

## 🚀 Installation & Setup

### 1. Configuration

Create a `.env` file in the project root directory:

```env
# Proxmox API Credentials
PVE_HOST=192.168.1.100
PVE_USER=root@pam
PVE_TOKEN_NAME=ai-operator
PVE_TOKEN_VALUE=your-token-uuid

# AI Settings (for main.py)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b
```

### 2. Run with Docker (Recommended)
Build and run the container:


```
docker compose up -d
```

### Check logs to confirm connection
```
docker logs -f proxmox-ai-operator
```

The container automatically serves the MCP server on port 8000.

---

# 🔌 Integration into LibreChat
To connect this operator to LibreChat (including from a remote host), add the following configuration to your librechat.yaml:

```
mcpServers:
  proxmox:
    type: sse
    # Replace <NVIDIA-HOST-IP> with your host's IP address
    url: http://<NVIDIA-HOST-IP>:8000/sse
```

---

# 🛠️ Manual Usage
If you prefer running the project without Docker in a Python virtual environment:

Create and activate virtual environment
```
  python -m venv .venv
  source .venv/bin/activate
```

 Install dependencies
```
  pip install -r requirements.txt
```
 Start as MCP server

  ```
    python mcp_server.py
  ```

---

# 📝 Dependencies
The project relies on these core libraries:

proxmoxer: For Proxmox API communication.

fastmcp: For serving the MCP server.

uvicorn & starlette: For running the web server backend.

---

# 📋 Logs
All actions are logged in detail inside proxmox_ai.log to track tool calls and API responses.


---

# ⚠️ Disclaimer
This is a powerful tool capable of modifying real resources in your Proxmox cluster. Always exercise caution when testing destructive operations like delete_vm or rollback_snapshot.