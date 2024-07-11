import server

class BridgeServer(server.PromptServer):
    def __init__(self, loop):
        super().__init__(loop)

    async def send_json(self, event, data, sid=None):
        message = {"type": event, "data": data}

        if sid is None:
            sockets = list(self.sockets.values())
            for ws in sockets:
                await server.send_socket_catch_exception(ws.send_json, message)
        elif sid in self.sockets:
            await server.send_socket_catch_exception(self.sockets[sid].send_json, message)
        elif sid not in self.sockets:
            server.nodes.interrupt_processing() # comfyui_bridge_server (middlek)