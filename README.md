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

## Prerequisites

- Blender 3.0 or newer
- Python 3.10 or newer
- uv package manager

### Install uv

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Then add uv to your PATH and restart your terminal:
```powershell
$localBin = "$env:USERPROFILE\.local\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$userPath;$localBin", "User")
```

## Installation

### Step 1 — Install the Blender Addon

1. Download `addon.py` from this repo
2. Open Blender
3. Go to **Edit → Preferences → Add-ons → Install…**
4. Select `addon.py`
5. Enable the addon by checking the box next to **Interface: Blender MCP**

### Step 2 — Start the server in Blender

1. In the 3D Viewport press **N** to open the sidebar
2. Click the **BlenderMCP** tab
3. Click **Connect to Claude**

### Step 3 — Configure your AI client

#### Claude Desktop

Edit `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
    "mcpServers": {
        "blender": {
            "command": "uvx",
            "args": ["blender-mcp"]
        }
    }
}
```

#### Cursor

Go to **Settings → MCP** and add:

```json
{
    "mcpServers": {
        "blender": {
            "command": "uvx",
            "args": ["blender-mcp"]
        }
    }
}
```

**Windows (Cursor)**:
```json
{
    "mcpServers": {
        "blender": {
            "command": "cmd",
            "args": ["/c", "uvx", "blender-mcp"]
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
            "command": "uvx",
            "args": ["blender-mcp"]
        }
    }
}
```

> ⚠️ Run only **one** instance of the MCP server at a time.

## Running Locally from Source

```bash
# Clone the repo
git clone https://github.com/jagath/blender-mcp.git
cd blender-mcp

# Create virtual environment and install
uv venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

uv pip install -e .
```

Then point your AI client config at the script directly:

```json
{
    "mcpServers": {
        "blender": {
            "command": "python",
            "args": ["/absolute/path/to/blender-mcp/src/blender_mcp/server.py"]
        }
    }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLENDER_HOST` | `localhost` | Host where the Blender addon is running |
| `BLENDER_PORT` | `9876` | Port configured in the Blender addon panel |

Example for a remote Blender instance:
```bash
export BLENDER_HOST=192.168.1.100
export BLENDER_PORT=9876
uvx blender-mcp
```

Or in your MCP config:
```json
{
    "mcpServers": {
        "blender": {
            "command": "uvx",
            "args": ["blender-mcp"],
            "env": {
                "BLENDER_HOST": "192.168.1.100",
                "BLENDER_PORT": "9876"
            }
        }
    }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Check connectivity with the Blender addon |
| `get_scene_info` | Scene name, object count, render engine, frame range |
| `list_objects` | All objects; optional type filter (MESH, CAMERA, LIGHT…) |
| `get_object_info` | Location, rotation, scale, mesh stats, bounding box |
| `get_viewport_screenshot` | Capture the 3D viewport as an image |
| `execute_blender_code` | Run arbitrary Python / bpy code inside Blender |

## Example Prompts

- *"What objects are in my current Blender scene?"*
- *"Take a screenshot of the viewport so I can see what's there"*
- *"Create a red metallic sphere at position (0, 0, 2)"*
- *"Point the camera at the origin and set it to isometric projection"*
- *"Add a sun light above the scene and set its strength to 3"*
- *"List all mesh objects and show their bounding box dimensions"*

## Troubleshooting

**"Could not connect to Blender"**  
Make sure you clicked **Connect to Claude** in the BlenderMCP panel inside Blender first.

**Connection refused on port 9876**  
Check the port in Blender's panel matches the one in your environment variables.

**Tool calls time out**  
Break complex requests into smaller steps. Code execution has a 180-second timeout.

**Addon not visible in the sidebar**  
Press **N** in the 3D Viewport to reveal the sidebar, then look for the **BlenderMCP** tab.

**Still stuck?**  
Disable and re-enable the addon in Blender Preferences, then click Connect again.

## Technical Details

### Communication Protocol

Simple JSON over TCP sockets:

- **Request**: `{ "type": "<command>", "params": { ... } }`
- **Response**: `{ "status": "success"|"error", "result": <any> | "message": <str> }`

## Security

The `execute_blender_code` tool runs arbitrary Python code inside Blender. Always save your work before using it, and only connect to AI services you trust.

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

MIT © [Jagath Jayakumar](https://hellojagath.com)
