import socket
import json
import logging
import tempfile
import os
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP, Context, Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("BlenderMCPServer")

DEFAULT_HOST = os.getenv("BLENDER_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("BLENDER_PORT", "9876"))


@dataclass
class BlenderConnection:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    _sock: socket.socket = field(default=None, init=False, repr=False)

    def connect(self) -> bool:
        if self._sock:
            return True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self.host, self.port))
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Blender: {e}")
            self._sock = None
            return False

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self._sock = None

    def receive_full_response(self, timeout=180.0) -> bytes:
        self._sock.settimeout(timeout)
        chunks = []
        try:
            while True:
                chunk = self._sock.recv(8192)
                if not chunk:
                    if not chunks:
                        raise Exception("Connection closed before receiving any data")
                    break
                chunks.append(chunk)
                try:
                    data = b"".join(chunks)
                    json.loads(data.decode("utf-8"))
                    logger.info(f"Received complete response ({len(data)} bytes)")
                    return data
                except json.JSONDecodeError:
                    continue
        except socket.timeout:
            logger.warning("Socket timeout during receive")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {e}")
            raise

        data = b"".join(chunks)
        if not data:
            raise Exception("No data received")
        try:
            json.loads(data.decode("utf-8"))
            return data
        except json.JSONDecodeError:
            raise Exception("Incomplete JSON response received")

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._sock and not self.connect():
            raise ConnectionError("Not connected to Blender")

        command = {"type": command_type, "params": params or {}}

        try:
            logger.info(f"Sending command: {command_type} with params: {params}")
            self._sock.sendall(json.dumps(command).encode("utf-8"))
            logger.info("Command sent, waiting for response...")

            response_data = self.receive_full_response()
            response = json.loads(response_data.decode("utf-8"))
            logger.info(f"Response status: {response.get('status', 'unknown')}")

            if response.get("status") == "error":
                raise Exception(response.get("message", "Unknown error from Blender"))

            return response.get("result", {})

        except socket.timeout:
            self._sock = None
            raise Exception("Timeout waiting for Blender response - try simplifying your request")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            self._sock = None
            raise Exception(f"Connection to Blender lost: {e}")
        except json.JSONDecodeError as e:
            self._sock = None
            raise Exception(f"Invalid response from Blender: {e}")
        except Exception as e:
            self._sock = None
            raise Exception(f"Communication error with Blender: {e}")


_blender_connection: Optional[BlenderConnection] = None


def get_blender_connection() -> BlenderConnection:
    global _blender_connection

    if _blender_connection is not None:
        try:
            _blender_connection.send_command("ping")
            return _blender_connection
        except Exception as e:
            logger.warning(f"Existing connection is no longer valid: {e}")
            try:
                _blender_connection.disconnect()
            except Exception:
                pass
            _blender_connection = None

    _blender_connection = BlenderConnection()
    if not _blender_connection.connect():
        _blender_connection = None
        raise Exception("Could not connect to Blender. Make sure the Blender addon is running.")

    logger.info("Created new connection to Blender")
    return _blender_connection


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    logger.info("BlenderMCP server starting up")
    try:
        get_blender_connection()
        logger.info("Successfully connected to Blender on startup")
    except Exception as e:
        logger.warning(f"Could not connect to Blender on startup: {e}")
        logger.warning("Make sure the Blender addon is running before using any tools")
    try:
        yield {}
    finally:
        global _blender_connection
        if _blender_connection:
            _blender_connection.disconnect()
            _blender_connection = None
        logger.info("BlenderMCP server shut down")


mcp = FastMCP("BlenderMCP", lifespan=server_lifespan)


@mcp.tool()
def ping(ctx: Context) -> str:
    """Check connectivity with the Blender addon."""
    blender = get_blender_connection()
    result = blender.send_command("ping")
    return json.dumps(result, indent=2)


@mcp.tool()
def get_scene_info(ctx: Context) -> str:
    """Get detailed information about the current Blender scene."""
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_scene_info")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting scene info: {e}")
        return f"Error getting scene info: {e}"


@mcp.tool()
def list_objects(ctx: Context, type_filter: str = None) -> str:
    """
    List all objects in the current Blender scene.

    Parameters:
    - type_filter: Optional. Filter by object type e.g. MESH, CAMERA, LIGHT, EMPTY.
    """
    try:
        blender = get_blender_connection()
        params = {}
        if type_filter:
            params["type_filter"] = type_filter
        result = blender.send_command("list_objects", params)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing objects: {e}")
        return f"Error listing objects: {e}"


@mcp.tool()
def get_object_info(ctx: Context, object_name: str) -> str:
    """
    Get detailed information about a specific object in the Blender scene.

    Parameters:
    - object_name: The name of the object to get information about
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_object_info", {"name": object_name})
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting object info: {e}")
        return f"Error getting object info: {e}"


@mcp.tool()
def get_viewport_screenshot(ctx: Context, max_size: int = 800) -> Image:
    """
    Capture a screenshot of the current Blender 3D viewport.

    Parameters:
    - max_size: Maximum size in pixels for the largest dimension (default: 800)
    """
    try:
        blender = get_blender_connection()
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"blender_mcp_screenshot_{os.getpid()}.png",
        )
        result = blender.send_command("get_viewport_screenshot", {
            "filepath": temp_path,
            "max_size": max_size,
            "fmt": "PNG",
        })
        if "error" in result:
            raise Exception(result["error"])
        if not os.path.exists(temp_path):
            raise Exception("Screenshot file was not created")
        with open(temp_path, "rb") as f:
            image_bytes = f.read()
        os.remove(temp_path)
        return Image(data=image_bytes, format="png")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        raise Exception(f"Screenshot failed: {e}")


@mcp.tool()
def execute_blender_code(ctx: Context, code: str) -> str:
    """
    Execute arbitrary Python code in Blender.

    Parameters:
    - code: The Python code to execute in Blender's context
    """
    try:
        blender = get_blender_connection()
        result = blender.send_command("execute_code", {"code": code})
        return f"Code executed successfully: {result.get('result', '')}"
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        return f"Error executing code: {e}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
