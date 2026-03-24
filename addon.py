import bpy
import json
import threading
import socket
import time
import traceback
import io
import mathutils
from contextlib import redirect_stdout, suppress
from bpy.props import IntProperty, BoolProperty

bl_info = {
    "name":        "Blender MCP",
    "author":      "Jagath Jayakumar",
    "version":     (1, 0, 0),
    "blender":     (3, 0, 0),
    "location":    "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to AI services via the Model Context Protocol",
    "doc_url":     "https://hellojagath.com",
    "tracker_url": "https://hellojagath.com",
    "category":    "Interface",
}


class BlenderMCPServer:
    def __init__(self, host="localhost", port=9876):
        self.host = host
        self.port = port
        self.running = False
        self._socket = None
        self._thread = None

    def start(self):
        if self.running:
            print("Server is already running")
            return
        self.running = True
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.listen(5)
            self._thread = threading.Thread(target=self._server_loop, daemon=True)
            self._thread.start()
            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self._socket:
            with suppress(Exception):
                self._socket.close()
            self._socket = None
        if self._thread:
            with suppress(Exception):
                if self._thread.is_alive():
                    self._thread.join(timeout=2.0)
            self._thread = None
        print("BlenderMCP server stopped")

    def _server_loop(self):
        self._socket.settimeout(1.0)
        while self.running:
            try:
                client, address = self._socket.accept()
                print(f"Connected to client: {address}")
                t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")
                time.sleep(0.2)

    def _handle_client(self, client):
        client.settimeout(None)
        buffer = b""
        try:
            while self.running:
                chunk = client.recv(65536)
                if not chunk:
                    print("Client disconnected")
                    break
                buffer += chunk
                while buffer:
                    try:
                        command, idx = json.JSONDecoder().raw_decode(buffer.decode("utf-8"))
                        buffer = buffer[idx:].lstrip()
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        break

                    _command, _client = command, client

                    def execute_wrapper(cmd=_command, sock=_client):
                        try:
                            response = self.execute_command(cmd)
                            with suppress(Exception):
                                sock.sendall(json.dumps(response).encode("utf-8"))
                        except Exception as e:
                            print(f"Error executing command: {e}")
                            traceback.print_exc()
                            with suppress(Exception):
                                sock.sendall(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
                        return None

                    bpy.app.timers.register(execute_wrapper, first_interval=0.0)
        except Exception as e:
            print(f"Error in client handler: {e}")
        finally:
            with suppress(Exception):
                client.close()
            print("Client handler stopped")

    def execute_command(self, command):
        try:
            return self._execute_command_internal(command)
        except Exception as e:
            print(f"Error executing command: {e}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _execute_command_internal(self, command):
        cmd_type = command.get("type")
        params = command.get("params", {})

        handlers = {
            "ping":                    self._ping,
            "get_scene_info":          self.get_scene_info,
            "get_object_info":         self.get_object_info,
            "list_objects":            self.list_objects,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code":            self.execute_code,
        }

        handler = handlers.get(cmd_type)
        if handler:
            try:
                result = handler(**params)
                return {"status": "success", "result": result}
            except Exception as e:
                print(f"Error in handler: {e}")
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    def _ping(self):
        return {"pong": True, "blender_version": list(bpy.app.version)}

    def get_scene_info(self):
        scene = bpy.context.scene
        scene_info = {
            "name":          scene.name,
            "object_count":  len(scene.objects),
            "frame_current": scene.frame_current,
            "frame_start":   scene.frame_start,
            "frame_end":     scene.frame_end,
            "render_engine": scene.render.engine,
            "objects":       [],
        }
        for i, obj in enumerate(bpy.context.scene.objects):
            if i >= 50:
                break
            scene_info["objects"].append({
                "name":     obj.name,
                "type":     obj.type,
                "location": [round(float(obj.location.x), 2),
                             round(float(obj.location.y), 2),
                             round(float(obj.location.z), 2)],
            })
        return scene_info

    def list_objects(self, type_filter=None):
        result = []
        for obj in bpy.context.scene.objects:
            if type_filter and obj.type != type_filter.upper():
                continue
            result.append({
                "name":     obj.name,
                "type":     obj.type,
                "visible":  obj.visible_get(),
                "location": [round(v, 4) for v in obj.location],
            })
        return {"objects": result, "count": len(result)}

    def get_object_info(self, name):
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        info = {
            "name":      obj.name,
            "type":      obj.type,
            "location":  [obj.location.x, obj.location.y, obj.location.z],
            "rotation":  [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale":     [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible":   obj.visible_get(),
            "materials": [s.material.name for s in obj.material_slots if s.material],
        }

        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges":    len(mesh.edges),
                "polygons": len(mesh.polygons),
            }
            info["world_bounding_box"] = self._get_aabb(obj)

        return info

    def get_viewport_screenshot(self, filepath, max_size=1024, fmt="PNG"):
        if not filepath:
            return {"error": "No filepath provided"}

        area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
        if not area:
            return {"error": "No 3D viewport found"}

        with bpy.context.temp_override(area=area):
            bpy.ops.screen.screenshot_area(filepath=filepath)

        img = bpy.data.images.load(filepath)
        width, height = img.size

        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            new_width  = int(width * scale)
            new_height = int(height * scale)
            img.scale(new_width, new_height)
            img.file_format = fmt.upper()
            img.save()
            width, height = new_width, new_height

        bpy.data.images.remove(img)
        return {"success": True, "width": width, "height": height, "filepath": filepath}

    def execute_code(self, code):
        try:
            namespace = {"bpy": bpy, "mathutils": mathutils}
            capture_buffer = io.StringIO()
            with redirect_stdout(capture_buffer):
                exec(code, namespace)
            return {"executed": True, "result": capture_buffer.getvalue()}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    @staticmethod
    def _get_aabb(obj):
        corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
        mn = [min(c[i] for c in corners) for i in range(3)]
        mx = [max(c[i] for c in corners) for i in range(3)]
        return [mn, mx]


class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label       = "Blender MCP"
    bl_idname      = "BLENDERMCP_PT_Panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "BlenderMCP"

    def draw(self, context):
        layout  = self.layout
        scene   = context.scene
        running = scene.blendermcp_server_running

        row = layout.row()
        row.enabled = not running
        row.prop(scene, "blendermcp_port", text="Port")

        layout.separator()

        if not running:
            layout.operator("blendermcp.start_server", text="Connect to MCP Server", icon="PLAY")
        else:
            box = layout.box()
            box.label(text="● Connected", icon="SEQUENCE_COLOR_04")
            box.label(text=f"Running on port {scene.blendermcp_port}")
            layout.separator()
            layout.operator("blendermcp.stop_server", text="Disconnect from MCP Server", icon="PAUSE")


class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname      = "blendermcp.start_server"
    bl_label       = "Connect to MCP Server"
    bl_description = "Start the BlenderMCP server"

    def execute(self, context):
        scene = context.scene
        try:
            if not hasattr(bpy.types, "blendermcp_server") or bpy.types.blendermcp_server is None:
                bpy.types.blendermcp_server = BlenderMCPServer(port=scene.blendermcp_port)
            bpy.types.blendermcp_server.start()
            scene.blendermcp_server_running = True
            self.report({"INFO"}, f"BlenderMCP server started on port {scene.blendermcp_port}")
        except Exception as e:
            self.report({"ERROR"}, f"Failed to start server: {e}")
        return {"FINISHED"}


class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname      = "blendermcp.stop_server"
    bl_label       = "Disconnect"
    bl_description = "Stop the BlenderMCP server"

    def execute(self, context):
        if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
            bpy.types.blendermcp_server.stop()
            del bpy.types.blendermcp_server
        context.scene.blendermcp_server_running = False
        return {"FINISHED"}


_CLASSES = [
    BLENDERMCP_PT_Panel,
    BLENDERMCP_OT_StartServer,
    BLENDERMCP_OT_StopServer,
]


def register():
    bpy.types.Scene.blendermcp_port = IntProperty(
        name="Port",
        description="Port for the BlenderMCP server",
        default=9876, min=1024, max=65535,
    )
    bpy.types.Scene.blendermcp_server_running = BoolProperty(
        name="Server Running",
        default=False,
    )
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    print("BlenderMCP addon registered")


def unregister():
    if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
        bpy.types.blendermcp_server.stop()
        del bpy.types.blendermcp_server
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blendermcp_port
    del bpy.types.Scene.blendermcp_server_running
    print("BlenderMCP addon unregistered")


if __name__ == "__main__":
    register()
