import os
import asyncio
import logging
from dotenv import load_dotenv
from aiohttp import web
from server import BridgeServer

async def run_app(app, host, port):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Server started at http://{host}:{port}")
    await asyncio.Event().wait()

async def main():
    load_dotenv()
    
    servers_str = os.getenv('COMFYUI_SERVERS')
    host = os.getenv("HOST")
    port = os.getenv("PORT")
    state_fn = os.getenv("CURRENT_STATE")
    wf_alias_fn = os.getenv("WORKFLOW_ALIAS")
    comfyui_dir = os.getenv("COMFYUI_DIR")
    wf_dir = os.getenv("WORKFLOW_DIR")
    limit_timeout_count = int(os.getenv("LIMIT_TIMEOUT_COUNT"))
    timeout_interval = int(os.getenv("TIMEOUT_INTERVAL"))
    upload_max_size = 1024**2 * int(os.getenv("UPLOAD_MAX_SIZE"))
    logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()

    logging.basicConfig(level=getattr(logging, logging_level, logging.INFO),
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])
    
    server_list = servers_str.split(',') if servers_str else []

    loop = asyncio.get_event_loop()
    server = BridgeServer(loop=loop, 
                          state_fn=state_fn,
                          wf_alias_fn=wf_alias_fn,
                          comfyui_dir=comfyui_dir,
                          wf_dir=wf_dir,
                          server_address=server_list,
                          limit_timeout_count=limit_timeout_count,
                          timeout_interval=timeout_interval,
                          upload_max_size=upload_max_size)
    
    app = await server.init_app()
    await run_app(app, host, int(port))

if __name__ == '__main__':
    asyncio.run(main())
