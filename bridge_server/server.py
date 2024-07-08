import json, os
import asyncio
import aiohttp
import logging
from aiohttp import web
from socket_manager import SocketManager
from urls import setup_routes
from assistant import (queue_prompt,
                    get_history,
                    get_queue_state,
                    get_parsed_input_nodes,
                    post_free_memory,
                    parse_workflow_prompt,
                    parse_outputs,
                    save_binary_file,
                    make_workflow_alias_map,
                    AsyncJsonWrapper)

@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
        return response
    except Exception as e:
        return web.Response(
            status=400,
            body=json.dumps({"detail":f"{e}"}),
            content_type="application/json"
        )

class BridgeServer():
    
    def __init__(self, 
                 loop, 
                 state_fn:str,
                 wf_alias_fn:str,
                 comfyui_dir:str,
                 wf_dir:str, 
                 server_address:list, 
                 limit_timeout_count:int, 
                 timeout_interval:int,
                 upload_max_size:int=1024**2*100
                 ) -> None:
        self.loop = loop
        self.comfyui_dir = comfyui_dir
        self.wf_dir = wf_dir
        self.server_address = server_address
        self.limit_timeout_count = limit_timeout_count
        self.timeout_interval = timeout_interval
        self.upload_max_size = upload_max_size

        self.state_obj = AsyncJsonWrapper(state_fn)
        self.wf_alias_map = make_workflow_alias_map(wf_dir, wf_alias_fn)

    async def init_app(self):
        app = web.Application(middlewares=[error_middleware], client_max_size=self.upload_max_size)
        setup_routes(app, self)

        self.socket_manager = SocketManager(loop=self.loop, interval=self.timeout_interval, life_seconds=self.limit_timeout_count*self.timeout_interval)
        await self.state_obj.load()
        
        return app
        
    async def track_progress(self, sid):
        total_progress = 0
        cur_progress = 0

        logging.info(f"[WS REQ] TRACING START / {sid}")
        while True:
            out = await self.socket_manager.async_receive(sid)
            out = out.data

            if self.socket_manager[sid].ws_connection_status in ["closed", "error"]:
                break

            if isinstance(out, str):
                message = json.loads(out)
                
                if message['type'] == 'execution_start':
                    logging.info(f"[WS REQ] EXECUTION START / {sid}")

                    wf_info = self.socket_manager[sid].wf_info
                    inputs_infos = [cur.get("inputs", None) for cur in wf_info.values()]
                    steps_list = [value for inputs_info in inputs_infos
                        for key, value in inputs_info.items()
                        if "steps" in key]
                    total_progress += (len(wf_info) + sum(steps_list))
                    progress_message = {
                        'status': 'progress',
                        'details': f'{cur_progress/total_progress*100:.2f}%'
                    }
                    await self.socket_manager.async_send_json(sid, progress_message)
                
                if message['type'] in ('progress', 'executing'):
                    data = message['data']

                    if data['node'] is None and data['prompt_id'] == sid:
                        progress_message = {
                            'status': 'closed',
                            'details': 'Execution is done'
                        }
                    else:
                        cur_progress += 1
                        progress_message = {
                            'status': 'progress',
                            'details': f'{cur_progress/total_progress*100:.2f}%'
                        }
                    await self.socket_manager.async_send_json(sid, progress_message)
                    
                if message['type'] == 'execution_cached':
                    logging.debug(f"[WS REQ] EXECUTION DONE / {sid}")
                    
                    cached_nodes = message['data']['nodes']
                    cur_progress += len(cached_nodes)
                    progress_message = {
                        'status': 'progress',
                        'details': f'{cur_progress/total_progress*100:.2f}%'
                    }
                    await self.socket_manager.async_send_json(sid, progress_message)

            else:
                continue
        logging.info(f"[WS REQ] TRACING DONE / {sid}")

    async def websocket_connection(self, request, mode):
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")
        logging.info(f"[WS RES] RECEIVED / {sid}")

        session = None
        try:
            session = await self._ws_req_connection(sid)
            if mode == "PROXY":
                await self._ws_res_connection(request, sid)
            elif mode == "REST":
                pass
            else:
                raise ValueError(f"websocket connection mode must be 'PROXY' or 'REST' but got '{mode}'")
            await self.socket_manager.async_send_json(sid, {"status":"connected", "details":"server connected"})

            task = asyncio.create_task(self.track_progress(sid))
            if mode == "PROXY":
                timeout_count = 0
                while True:
                    if self.socket_manager[sid].ws_connection_status in ["closed", "error"]:
                        break
                    else:
                        await self.socket_manager.async_send_json(sid, {"status":"listening", "details":"server is listening"}, update_life=False)
                        if timeout_count >= self.limit_timeout_count:
                            raise TimeoutError(f"timeout count: {timeout_count}")
                        timeout_count += 1

                    await asyncio.sleep(self.timeout_interval)
            await task

        except aiohttp.ServerDisconnectedError as e:
            logging.warning(f"[WS RES] SERVER DISCONNECTED ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "details":"server disconnected"})
        except TimeoutError as e:
            logging.warning(f"[WS RES] TIMEOUT ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "details":f"time out error: exceed {self.limit_timeout_count * self.timeout_interval}s"})
        except aiohttp.ServerConnectionError as e:
            logging.error(f"[WS REQ] SERVER CONNECTION ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "details":"server connection error"})
        except Exception as e:
            logging.error(f"[WS] UNKNOWN ERROR / {str(e)} / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "details":"internal server error"})
        finally:
            logging.info(f"[WS] CLOSING / {sid}")

            await self.socket_manager.async_send_json(sid, {"status":"closed", "details":"connection will be closed"}, update_life=False)
            await self.socket_manager.async_release_sockets(sid)
     
            if session is not None:
                await session.close()

        return web.Response(text="Dummy response")
    
    async def _ws_res_connection(self, request, sid):
        ws_res = web.WebSocketResponse()
        await ws_res.prepare(request)
        self.socket_manager[sid].sockets_res = ws_res
        logging.info(f"[WS RES] HANDSHAKE / {sid}")

    async def _ws_req_connection(self, sid):
        server_address = await self.get_not_busy_server_address()
        self.socket_manager[sid].linked_server = server_address
        logging.debug(f"[WS REQ] server allocated to {server_address} / {sid}")

        session = aiohttp.ClientSession()
        try: 
            ws_req = await session.ws_connect(f"ws://{server_address}/ws?clientId={sid}")
            logging.info(f"[WS REQ] HANDSHAKE / {sid}")
        except Exception as e:
            raise aiohttp.ServerConnectionError
        finally:
            self.socket_manager[sid].sockets_req = ws_req
            return session

    async def get_not_busy_server_address(self):
        queue_lenghs = []
        for server_address in self.server_address:
            try:
                queue_state = get_queue_state(server_address)
            except Exception as e:
                logging.debug(f"[NO SIGNAL] {server_address} / {e}")

            queue_length = sum([len(cur) for cur in queue_state.values()])
            queue_lenghs.append(queue_length)
        
        target_server_address = self.server_address[queue_lenghs.index(min(queue_lenghs))]
        return target_server_address
    
    async def generate_based_workflow(self, request):
        data = await request.json()
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")

        workflow = data.pop("workflow", None)
        if not isinstance(workflow, str): raise TypeError(f"workflow is required and must be and str, but got {type(sid).__str__()}")
        
        workflow = self.wf_alias_map[workflow]
        kwargs = data

        prompt = parse_workflow_prompt(os.path.join(self.wf_dir, workflow), **kwargs)
        self.socket_manager[sid].wf_info = prompt

        if self.socket_manager[sid].sockets_res is None:
            asyncio.create_task(self.websocket_connection(request, mode="REST"))
        
        asyncio.sleep(0.5)
        timeout_count = 0
        while self.socket_manager[sid].linked_server is None:
            await asyncio.sleep(self.timeout_interval)
            if timeout_count >= self.limit_timeout_count:
                raise TimeoutError(f"timeout count: {timeout_count}")
            timeout_count += 1
        prompt = queue_prompt(prompt, sid, self.socket_manager[sid].linked_server)
        
        self.state_obj.generation_count += 1
        await self.state_obj.update()

        return web.Response(status=200)
    
    async def upload_image(self, request):
        reader = await request.multipart()

        logging.info(f"[POST] '{request.path}'")

        fns={}
        async for part in reader:

            try:
                file_name = part.headers.get('Content-Disposition', '').split('filename=')[1].strip('"')
                file_name = os.path.basename(file_name)
                file_data = await part.read()
            
                fn = save_binary_file(file_data, file_name, directory=os.path.join(self.comfyui_dir, "input"))
                fns[part.headers.get("ori_file_id", None)] = fn
                logging.debug(f"[POST] '{request.path}' / {fn} saved")
        
            except Exception as e:
                logging.error(f"[POST] '{request.path}' / {file_name} can't save / {str(e)}")

                return web.Response(
                    status=400,
                    body=json.dumps({"detail":f"{file_name} can't save"}),
                    headers={"Content-Type": "application/json"}
                )

        return web.Response(
            status=200,
            body=json.dumps(fns),
            headers={"Content-Type": "application/json"}
        )
        
    async def get_history(self, request):
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is must be str, but got {type(sid).__str__()}")
        
        server_address = self.socket_manager[sid].linked_server
        if server_address is None:
            return web.Response(
                status=204,
                body=json.dumps({"detail":f"The client ID has not been submitted to the server before. It is not recognized. / {sid}"}),
                headers={"Content-Type": "application/json"}
            )
        
        history = get_history(sid, server_address)
        history = history.get(sid, None)
        logging.debug(f"[GET] '{request.path}' / GET HISTORY / {sid}")

        if history is not None:
            output = history["outputs"],
            if isinstance(output, tuple):
                output = (output)
            
            writer = aiohttp.MultipartWriter("form-data")
            
            file_paths, mime_types, file_contents = parse_outputs(output[0], root_dir=self.comfyui_dir)
            for file_path, mime_type, file_content in zip(file_paths, mime_types, file_contents):

                headers = {'Content-Type': mime_type, 'Content-Disposition': f'attachment; filename="{file_path.split("/")[-1]}"'}
                writer.append(file_content, headers)

            headers = {
                'Content-Type': writer.content_type,
            }
            
            await self.socket_manager.async_delete(sid)
            logging.debug(f"[GET] '{request.path}' / DELETE HISTORY / {sid}")

            return web.Response(
                status=200,
                body=writer,
                headers=headers
            )
        else:
            return web.Response(
                status=204,
                body=json.dumps({"detail":f"No contents with that client id / {sid}"}),
                headers={"Content-Type": "application/json"}
            )

    async def free_memory(self, request):
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be str, but got {type(sid).__str__()}")

        post_free_memory(self.socket_manager[sid].linked_server)
        return web.Response(status=200, body=json.dumps({"detail":f"server memory free now / {sid}"}), content_type="application/json")
    
    async def interrupt_generation(self, request):
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be str, but got {type(sid).__str__()}")

        await self.socket_manager.async_delete(sid)
        return web.Response(status=200, body=json.dumps({"detail":f"interrupted that clientId will be ignored. / {sid}"}), content_type="application/json")

    async def get_generation_count(self, _):
        generation_count = self.state_obj.generation_count
        return web.Response(status=200, body=json.dumps(generation_count), content_type="application/json")
    
    async def get_execution_info(self, request):
        sid = request.rel_url.query.get('clientId', '')
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")
        execution_info = self.socket_manager[sid].execution_info
        return web.Response(status=200, body=json.dumps(execution_info), content_type="application/json")

    async def get_workflow_list(self, _):
        wf_list = list(self.wf_alias_map.keys())
        return web.Response(status=200, body=json.dumps(wf_list), content_type="application/json")
    
    async def get_workflow_info(self, request):
        workflow = request.rel_url.query.get('workflow', '')
        if not isinstance(workflow, str): raise TypeError(f"workflow is required and must be and str, but got {type(workflow).__str__()}")
        workflow = self.wf_alias_map[workflow]
        node_info = get_parsed_input_nodes(os.path.join(self.wf_dir, workflow))
        return web.Response(status=200, body=json.dumps(node_info), content_type="application/json")
    
    async def main_page(self, _):
        return web.Response(text="Hello, this is ComfyUI Bridge Server! (made by middlek)")
