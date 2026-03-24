import re
import bpy
import mathutils
import json
import threading
import socket
import time
import traceback
import os
import io
from contextlib import redirect_stdout, suppress
from bpy.props import IntProperty, BoolProperty

bl_info = {
    "name": "Blender MCP",
    "author": "Jagath Jayakumar",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to AI services via the Model Context Protocol",
    "doc_url": "https://hellojagath.com",
    "category": "Interface",
}


class JJBlenderMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.srv_socket = None
        self.srv_thread = None

    def start(self):
        if self.running:
            print("Server is already running")
            return

        self.running = True

        try:
            self.srv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.srv_socket.bind((self.host, self.port))
            self.srv_socket.listen(1)

            self.srv_thread = threading.Thread(target=self._loop)
            self.srv_thread.daemon = True
            self.srv_thread.start()

            print(f"Blender MCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False

        if self.srv_socket:
            try:
                self.srv_socket.close()
            except:
                pass
            self.srv_socket = None

        if self.srv_thread:
            try:
                if self.srv_thread.is_alive():
                    self.srv_thread.join(timeout=1.0)
            except:
                pass
            self.srv_thread = None

        print("Blender MCP server stopped")

    def _loop(self):
        print("Server thread started")
        self.srv_socket.settimeout(1.0)

        while self.running:
            try:
                try:
                    client, address = self.srv_socket.accept()
                    print(f"Connected to client: {address}")

                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("Server thread stopped")

    def _handle_client(self, client):
        print("Client handler started")
        client.settimeout(None)
        buffer = b''

        try:
            while self.running:
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break

                    buffer += data
                    try:
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''

                        def run_command():
                            try:
                                response = self.handle_command(command)
                                response_json = json.dumps(response)
                                try:
                                    client.sendall(response_json.encode('utf-8'))
                                except:
                                    print("Failed to send response - client disconnected")
                            except Exception as e:
                                print(f"Error executing command: {str(e)}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(e)
                                    }
                                    client.sendall(json.dumps(error_response).encode('utf-8'))
                                except:
                                    pass
                            return None

                        bpy.app.timers.register(run_command, first_interval=0.0)
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    print(f"Error receiving data: {str(e)}")
                    break
        except Exception as e:
            print(f"Error in client handler: {str(e)}")
        finally:
            try:
                client.close()
            except:
                pass
            print("Client handler stopped")

    def handle_command(self, command):
        try:
            return self._run_command(command)
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _run_command(self, command):
        cmd_type = command.get("type")
        params = command.get("params", {})

        cmd_map = {
            "ping":                    self.ping,
            "get_scene_info":          self.get_scene_info,
            "get_object_info":         self.get_object_info,
            "list_objects":            self.list_objects,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code":            self.execute_code,
        }

        handler = cmd_map.get(cmd_type)
        if handler:
            try:
                result = handler(**params)
                return {"status": "success", "result": result}
            except Exception as e:
                print(f"Error in handler: {str(e)}")
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    def ping(self):
        return {"pong": True, "blender_version": list(bpy.app.version)}

    def get_scene_info(self):
        scene = bpy.context.scene
        info = {
            "name": scene.name,
            "object_count": len(scene.objects),
            "frame_current": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "render_engine": scene.render.engine,
            "objects": [],
            "materials_count": len(bpy.data.materials),
        }

        for i, obj in enumerate(bpy.context.scene.objects):
            if i >= 50:
                break
            info["objects"].append({
                "name": obj.name,
                "type": obj.type,
                "location": [round(float(obj.location.x), 2),
                             round(float(obj.location.y), 2),
                             round(float(obj.location.z), 2)],
            })

        return info

    def list_objects(self, type_filter=None):
        items = []
        for obj in bpy.context.scene.objects:
            if type_filter and obj.type != type_filter.upper():
                continue
            items.append({
                "name": obj.name,
                "type": obj.type,
                "visible": obj.visible_get(),
                "location": [round(v, 4) for v in obj.location],
            })
        return {"objects": items, "count": len(items)}

    def get_object_info(self, name):
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        info = {
            "name": obj.name,
            "type": obj.type,
            "location": [obj.location.x, obj.location.y, obj.location.z],
            "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible": obj.visible_get(),
            "materials": [],
        }

        for slot in obj.material_slots:
            if slot.material:
                info["materials"].append(slot.material.name)

        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }
            info["world_bounding_box"] = self._calc_aabb(obj)

        return info

    def get_viewport_screenshot(self, max_size=800, filepath=None, format="png"):
        try:
            if not filepath:
                return {"error": "No filepath provided"}

            viewport = None
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    viewport = area
                    break

            if not viewport:
                return {"error": "No 3D viewport found"}

            with bpy.context.temp_override(area=viewport):
                bpy.ops.screen.screenshot_area(filepath=filepath)

            img = bpy.data.images.load(filepath)
            width, height = img.size

            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.scale(new_width, new_height)
                img.file_format = format.upper()
                img.save()
                width, height = new_width, new_height

            bpy.data.images.remove(img)

            return {
                "success": True,
                "width": width,
                "height": height,
                "filepath": filepath
            }

        except Exception as e:
            return {"error": str(e)}

    def execute_code(self, code):
        try:
            ns = {"bpy": bpy, "mathutils": mathutils}
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                exec(code, ns)
            return {"executed": True, "result": output_buffer.getvalue()}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    @staticmethod
    def _calc_aabb(obj):
        local_corners = [mathutils.Vector(corner) for corner in obj.bound_box]
        world_corners = [obj.matrix_world @ corner for corner in local_corners]
        mn = mathutils.Vector(map(min, zip(*world_corners)))
        mx = mathutils.Vector(map(max, zip(*world_corners)))
        return [[*mn], [*mx]]


class JJ_PT_BlenderMCPPanel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "JJ_PT_BlenderMCPPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderMCP'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "jj_mcp_port")

        layout.separator()

        if not scene.jj_mcp_running:
            layout.operator("jj.mcp_connect", text="Connect to MCP Server")
        else:
            layout.operator("jj.mcp_disconnect", text="Disconnect from MCP Server")
            layout.label(text=f"Running on port {scene.jj_mcp_port}")


class JJ_OT_MCPConnect(bpy.types.Operator):
    bl_idname = "jj.mcp_connect"
    bl_label = "Connect to MCP Server"
    bl_description = "Start the Blender MCP server"

    def execute(self, context):
        scene = context.scene

        if not hasattr(bpy.types, "jj_mcp_server") or not bpy.types.jj_mcp_server:
            bpy.types.jj_mcp_server = JJBlenderMCPServer(port=scene.jj_mcp_port)

        bpy.types.jj_mcp_server.start()
        scene.jj_mcp_running = True

        return {'FINISHED'}


class JJ_OT_MCPDisconnect(bpy.types.Operator):
    bl_idname = "jj.mcp_disconnect"
    bl_label = "Disconnect from MCP Server"
    bl_description = "Stop the Blender MCP server"

    def execute(self, context):
        scene = context.scene

        if hasattr(bpy.types, "jj_mcp_server") and bpy.types.jj_mcp_server:
            bpy.types.jj_mcp_server.stop()
            del bpy.types.jj_mcp_server

        scene.jj_mcp_running = False

        return {'FINISHED'}


def register():
    bpy.types.Scene.jj_mcp_port = IntProperty(
        name="Port",
        description="Port for the Blender MCP server",
        default=9876,
        min=1024,
        max=65535
    )

    bpy.types.Scene.jj_mcp_running = bpy.props.BoolProperty(
        name="Server Running",
        default=False
    )

    bpy.utils.register_class(JJ_PT_BlenderMCPPanel)
    bpy.utils.register_class(JJ_OT_MCPConnect)
    bpy.utils.register_class(JJ_OT_MCPDisconnect)

    print("Blender MCP addon registered")


def unregister():
    if hasattr(bpy.types, "jj_mcp_server") and bpy.types.jj_mcp_server:
        bpy.types.jj_mcp_server.stop()
        del bpy.types.jj_mcp_server

    bpy.utils.unregister_class(JJ_PT_BlenderMCPPanel)
    bpy.utils.unregister_class(JJ_OT_MCPConnect)
    bpy.utils.unregister_class(JJ_OT_MCPDisconnect)

    del bpy.types.Scene.jj_mcp_port
    del bpy.types.Scene.jj_mcp_running

    print("Blender MCP addon unregistered")


if __name__ == "__main__":
    register()
