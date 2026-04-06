# Blender MCP

Blender MCP connects Blender to AI assistants through the Model Context Protocol (MCP), allowing AI to directly interact with and control Blender. This enables prompt-assisted 3D modelling, scene creation, and manipulation.

## Features

- **Two-way communication** — Connect AI assistants to Blender through a socket-based server
- **Scene inspection** — Get detailed information about the current Blender scene and objects
- **Object manipulation** — Create, modify, and delete 3D objects via AI-generated Python code
- **Material control** — Apply and modify materials and colours
- **Viewport screenshot** — Let the AI see the current state of your 3D viewport
- **Code execution** — Run arbitrary Python / bpy code in Blender from your AI client

## Components

```
blender-mcp/
├── addon.py                  ← Blender addon (install inside Blender)
├── src/
│   └── blender_mcp/
│       ├── __init__.py
│       └── server.py         ← MCP bridge server (runs on your machine)
├── pyproject.toml
├── LICENSE
└── README.md
```

The system has two parts:

1. **Blender Addon (`addon.py`)** — creates a socket server inside Blender that receives and executes commands
2. **MCP Server (`src/blender_mcp/server.py`)** — implements the Model Context Protocol and connects to the Blender addon

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Blender | 3.0 or newer |
| Python | 3.10 or newer |
| uv | latest |

### Install uv

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal after installing.

**Windows (PowerShell)**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Then add uv to your PATH (windows only, restart terminal after):
```powershell
$localBin = "$env:USERPROFILE\.local\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$userPath;$localBin", "User")
```

Verify uv is installed:
```bash
uv --version
```

---

## Installation

### Step 1 — Clone the repo

```bash
git clone https://github.com/jagathgj/BlenderMCP.git
cd BlenderMCP
```

### Step 2 — Set up the Python environment

```bash
uv venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### Step 3 — Install dependencies

```bash
uv pip install mcp
```

Verify the install:
```bash
python3 -c "import mcp; print('mcp installed ok')"
```

### Step 4 — Install the Blender Addon

1. Open Blender
2. Go to **Edit → Preferences → Add-ons → Install…**
3. Select `addon.py` from this repo
4. Enable it by checking the box next to **Interface: Blender MCP**

### Step 5 — Start the addon in Blender

1. In the 3D Viewport press **N** to open the sidebar
2. Click the **BlenderMCP** tab
3. Click **Connect to MCP Server**

### Step 6 — Configure your AI client

Find the full path to the venv Python:
```bash
which python3   # after activating the venv
# e.g. path/to/BlenderMCP/.venv/bin/python3
```

### IBM Bob IDE

IBM Bob IDE uses a specialized mode that provides an optimized workflow for Blender 3D development. It includes scene analysis, viewport inspection, and intelligent code generation for bpy operations.

**Step 1: Configure MCP Server in IBM Bob IDE**

1. Go to **Settings → MCP**

2. Add the BlenderMCP server configuration:

```json
{
    "mcpServers": {
        "blender-mcp": {
            "command": "path/to/BlenderMCP/.venv/bin/python3",
            "args": ["path/to/BlenderMCP/src/blender_mcp/server.py"],
            "description": "Connect Blender to AI assistants for 3D scene creation and manipulation"
        }
    }
}
```

> Replace `path/to/BlenderMCP` with your actual clone path(Refer step 6) in both **command** and **args** .

**Step 2: Import Bob Mode**

1. Go to **Settings → Modes**

2. Click **Import** button

3. Select the `blender-bob-mode.yaml` file from this repository

4. Select "🧊 Blender for 3D" mode from the mode selector in Bob IDE

The Bob mode will automatically use the BlenderMCP server configured in your MCP settings.

---

#### Claude Desktop

Edit `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
    "mcpServers": {
        "blender-mcp": {
            "command": "path/to/BlenderMCP/.venv/bin/python3",
            "args": ["path/to/BlenderMCP/src/blender_mcp/server.py"]
        }
    }
}
```

> Replace `path/to/BlenderMCP` with your actual clone path.

#### Cursor

Go to **Settings → MCP** and add:

```json
{
    "mcpServers": {
        "blender-mcp": {
            "command": "/path/to/BlenderMCP/.venv/bin/python3",
            "args": ["/path/to/BlenderMCP/src/blender_mcp/server.py"]
        }
    }
}
```

**Windows (Cursor)**:
```json
{
    "mcpServers": {
        "blender-mcp": {
            "command": "C:\\path\\to\\BlenderMCP\\.venv\\Scripts\\python.exe",
            "args": ["C:\\path\\to\\BlenderMCP\\src\\blender_mcp\\server.py"]
        }
    }
}
```

#### VS Code

```json
{
    "mcpServers": {
        "blender-mcp": {
            "type": "stdio",
            "command": "/path/to/BlenderMCP/.venv/bin/python3",
            "args": ["/path/to/BlenderMCP/src/blender_mcp/server.py"]
        }
    }
}
```

> ⚠️ Run only **one** instance of the MCP server at a time (either Claude Desktop or Cursor, not both).

Restart your AI client after saving the config.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLENDER_HOST` | `localhost` | Host where the Blender addon is running |
| `BLENDER_PORT` | `9876` | Port configured in the Blender addon panel |

For a remote Blender instance, add to your MCP config:
```json
{
    "mcpServers": {
        "blender-mcp": {
            "command": "/path/to/.venv/bin/python3",
            "args": ["/path/to/server.py"],
            "env": {
                "BLENDER_HOST": "192.168.1.100",
                "BLENDER_PORT": "9876"
            }
        }
    }
}
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Check connectivity with the Blender addon |
| `get_scene_info` | Scene name, object count, render engine, frame range |
| `list_objects` | All objects; optional type filter (MESH, CAMERA, LIGHT…) |
| `get_object_info` | Location, rotation, scale, mesh stats, bounding box |
| `get_viewport_screenshot` | Capture the 3D viewport as an image |
| `execute_blender_code` | Run arbitrary Python / bpy code inside Blender |

---

## Example Prompts

- *"What objects are in my current Blender scene?"*
- *"Take a screenshot of the viewport so I can see what's there"*
- *"Create a red metallic sphere at position (0, 0, 2)"*
- *"Point the camera at the origin and set it to isometric projection"*
- *"Add a sun light above the scene and set its strength to 3"*
- *"List all mesh objects and show their bounding box dimensions"*

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`**  
The venv Python isn't being used. Make sure the `command` in your config points to `.venv/bin/python3` inside the repo, not a system Python. Run `uv pip install mcp` inside the activated venv.

**`Connection closed` / MCP error -32000**  
Usually means the server crashed on startup. Check that `mcp` is installed and the path to `server.py` in your config is correct.

**`Could not connect to Blender`**  
Make sure you clicked **Connect to MCP Server** in the BlenderMCP panel inside Blender before issuing any commands.

**Connection refused on port 9876**  
Check the port in Blender's panel matches `BLENDER_PORT` (both default to 9876).

**Addon not visible in the sidebar**  
Press **N** in the 3D Viewport to reveal the sidebar, then look for the **BlenderMCP** tab.

**Tool calls time out**  
Break complex requests into smaller steps. Code execution has a 180-second timeout.

**Still stuck?**  
Disable and re-enable the addon in Blender Preferences, then click Connect again.

---

## Technical Details

### Communication Protocol

Simple JSON over TCP sockets:

- **Request**: `{ "type": "<command>", "params": { ... } }`
- **Response**: `{ "status": "success"|"error", "result": <any> | "message": <str> }`

---

## Security

The `execute_blender_code` tool runs arbitrary Python code inside Blender. Always save your work before using it, and only connect to AI services you trust.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

MIT © [Jagath Jayakumar](https://hellojagath.com)
