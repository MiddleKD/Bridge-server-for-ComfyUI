import os, json
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
    root_dir = os.path.dirname(__file__)

    host = os.getenv("HOST")
    port = os.getenv("PORT")
    servers_str = os.getenv('COMFYUI_SERVERS')
    config_fn = os.path.join(root_dir, os.getenv("CONFIG"))
    
    with open(config_fn, mode="r") as f:
        configs = json.load(f)
    
    state_fn = os.path.join(root_dir, configs.get("CURRENT_STATE"))
    wf_alias_fn = os.path.join(root_dir, configs.get("WORKFLOW_ALIAS"))
    wf_dir = os.path.join(root_dir, configs.get("WORKFLOW_DIR"))

    logging_level = configs.get("LOGGING_LEVEL", "WARN").upper()
    logging.basicConfig(level=getattr(logging, logging_level, logging.INFO),
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])
    
    server_list = servers_str.split(',') if servers_str else []

    loop = asyncio.get_event_loop()
    server = BridgeServer(loop=loop, 
                          state_fn=state_fn,
                          wf_alias_fn=wf_alias_fn,
                          wf_dir=wf_dir,
                          server_address=server_list,
                          limit_timeout_count=configs.get("LIMIT_TIMEOUT_COUNT"),
                          timeout_interval=configs.get("TIMEOUT_INTERVAL"),
                          allowed_mime_type_extension_map=configs.get("ALLOWED_MIME_TYPE_EXTENSION_MAP"),
                          upload_max_size=int(configs.get("UPLOAD_MAX_SIZE"))*1024**2)
    
    app = await server.init_app()
    await run_app(app, host, int(port))

if __name__ == '__main__':
    asyncio.run(main())
