from aiohttp import web

def setup_routes(app:web.Application, server):
    app.add_routes([
        web.get("/", server.main_page),
        web.get("/ws", lambda request: server.websocket_connection(request, mode="PROXY")),
        web.get("/history", server.get_history),
        web.get("/workflow-list", server.get_workflow_list),
        web.get("/generation-count", server.get_generation_count),
        web.get("/execution-info", server.get_execution_info),
        web.get("/workflow-info", server.get_workflow_info),
        web.post("/free", server.free_memory),
        web.post("/interrupt", server.interrupt_generation),
        web.post("/generate-based-workflow", server.generate_based_workflow),
        web.post("/upload/image", server.upload_image),
    ])
