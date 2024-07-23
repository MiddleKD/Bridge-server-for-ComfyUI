import json, os
import tempfile
import asyncio
import aiohttp
import base64
import logging
from aiohttp import web
from security import FileValidator
from socket_manager import SocketManager
from urls import setup_routes
from assistant import (queue_prompt,
                    get_history,
                    get_queue_state,
                    get_parsed_input_nodes,
                    upload_image,
                    post_free_memory,
                    parse_workflow_prompt,
                    process_outputs,
                    make_workflow_alias_list_and_map,
                    AsyncJsonWrapper)

@web.middleware
async def error_middleware(request, handler):
    """
    전체적인 예외를 처리하는 미들웨어 함수입니다. 요청을 처리하고 발생할 수 있는 예외를 잡습니다.

    Args:
        request (web.Request): 웹 요청 객체입니다.
        handler (Callable): 요청을 처리할 핸들러 함수입니다.

    Returns:
        response (web.Response): 요청 처리 결과를 포함한 HTTP 응답 객체입니다.
    """
    try:
        response = await handler(request)
        return response
    except Exception as e:
        logging.error(f"[MIDDLEWARE] INTERNAL ERROR / {e}")
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
                 wf_dir:str, 
                 server_address:list, 
                 limit_timeout_count:int,
                 timeout_interval:int,
                 allowed_mime_type_extension_map:dict,
                 upload_max_size:int=1024**2*100
                 ) -> None:
        """
        생성자 입니다.

        Args:
            loop (asyncio.AbstractEventLoop): asyncio 이벤트 루프 객체입니다.
            state_fn (str): 상태 파일의 경로입니다. ex: curent_state.json
            wf_alias_fn (str): 워크플로우 별칭 파일 경로입니다. ex: workflow_alias.json
            wf_dir (str): 워크플로우가 저장되어 있는 폴더 경로입니다.
            server_address (list): 접근 가능한 ComfyUI서버 주소 목록입니다.
            limit_timeout_count (int): 타임아웃 횟수 제한입니다.
            timeout_interval (int): 타임아웃 간격(초)입니다.
            allowed_mime_type_extension_map (dict): 허용된 MIME 타입 확장자 매핑입니다.
            upload_max_size (int, optional): 업로드 최대 크기입니다. 기본값은 100MB입니다.

        Returns:
            None
        """
        self.loop = loop
        self.wf_dir = wf_dir
        self.server_address = server_address
        self.limit_timeout_count = limit_timeout_count
        self.timeout_interval = timeout_interval
        self.upload_max_size = upload_max_size

        self.state_obj = AsyncJsonWrapper(state_fn)
        self.validator = FileValidator(allowed_mime_type_extension_map)
        self.wf_alias_list_with_desc, self.wf_alias_map = make_workflow_alias_list_and_map(wf_dir, wf_alias_fn)

    async def init_app(self):
        """
        웹 애플리케이션을 초기화합니다.

        Returns:
            app (web.Application): 초기화된 웹 애플리케이션 객체입니다.
        """
        # app = web.Application(middlewares=[error_middleware], client_max_size=self.upload_max_size)
        app = web.Application(client_max_size=self.upload_max_size)

        # bridge_server.urls.py에 따라 초기화
        setup_routes(app, self)

        # socket manager와 state 객체 생성
        self.socket_manager = SocketManager(loop=self.loop, interval=self.timeout_interval, life_seconds=self.limit_timeout_count*self.timeout_interval)
        await self.state_obj.load()
        
        return app
        
    async def track_progress(self, sid):
        """
        할당된 ComfyUI 서버의 작업 진행 상태를 추적합니다.

        Args:
            sid (str): 소켓 ID입니다.

        Returns:
            None
        """
        total_progress = 0
        cur_progress = 0

        logging.info(f"[WS REQ] TRACING START / {sid}")
        while True:
            # ComfyUI 서버와 연결된 request websocket으로 부터 메시지를 받음
            out = await self.socket_manager.async_receive(sid)
            out = out.data

            if self.socket_manager[sid].ws_connection_status in ["closed", "error"]:
                # 메시지 상태가 closed 또는 error일 때 추적 종료
                break

            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'execution_start':
                    # process가 시작됨
                    logging.info(f"[WS REQ] EXECUTION START / {sid}")

                    wf_info = self.socket_manager[sid].wf_info
                    inputs_infos = [cur.get("inputs", None) for cur in wf_info.values()]
                    steps_list = [value for inputs_info in inputs_infos
                        for key, value in inputs_info.items()
                        if "steps" in key]
                    total_progress += (len(wf_info) + sum(steps_list))
                    progress_message = {
                        'status': 'progress',
                        'detail': f'{cur_progress/total_progress*100:.2f}%'
                    }
                    await self.socket_manager.async_send_json(sid, progress_message)
                
                if message['type'] in ('progress', 'executing'):
                    data = message['data']

                    if data['node'] is None:
                        # process가 성공적으로 종료됨
                        progress_message = {
                            'status': 'closed',
                            'detail': 'Execution is done'
                        }
                        self.socket_manager[sid].comfyui_prompt_id = data['prompt_id']
                        logging.debug(f"[WS REQ] EXECUTION DONE / {sid}")
                    else:
                        # process가 성공적으로 진행 중
                        cur_progress += 1
                        progress_message = {
                            'status': 'progress',
                            'detail': f'{cur_progress/total_progress*100:.2f}%'
                        }
                    await self.socket_manager.async_send_json(sid, progress_message)
                    
                if message['type'] == 'execution_cached':
                    # process의 일부가 캐시되어 있음. 더 빠른 연산을 기대.
                    cached_nodes = message['data']['nodes']
                    cur_progress += len(cached_nodes)
                    progress_message = {
                        'status': 'progress',
                        'detail': f'{cur_progress/total_progress*100:.2f}%'
                    }
                    await self.socket_manager.async_send_json(sid, progress_message)

                if message['type'] == "prompt_outputs_failed_validation":
                    # prompt가 ComfyUI에서 기대하는 형태가 아님. 에러 발생. 
                    progress_message = {
                            'status': 'error',
                            'detail': 'prompt is not validated'
                        }
                    await self.socket_manager.async_send_json(sid, progress_message)
            else:
                continue
        logging.info(f"[WS REQ] TRACING DONE / {sid}")

    async def websocket_connection(self, request, mode):
        """
        웹소켓 통신을 관리하고 적절한 에러를 발생시킵니다.

        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다.
            mode (str): 연결 모드입니다. 'PROXY' 또는 'REST'여야 합니다. 'PROXY'는 bridge를 의미합니다.

        Returns:
            web.Response: HTTP 응답 객체입니다.
        """
        sid = request.rel_url.query.get('clientId', None)
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
            await self.socket_manager.async_send_json(sid, {"status":"connected", "detail":"server connected"})

            task = asyncio.create_task(self.track_progress(sid))
            if mode == "PROXY":
                # clinet와 통신 중단이 지속되면 timeout에러가 발생합니다.
                timeout_count = 0
                while True:
                    if self.socket_manager[sid].ws_connection_status in ["closed", "error"]:
                        break
                    else:
                        await self.socket_manager.async_send_json(sid, {"status":"listening", "detail":"server is listening"}, update_life=False)
                        if timeout_count >= self.limit_timeout_count:
                            raise TimeoutError(f"timeout count: {timeout_count}")
                        timeout_count += 1

                    await asyncio.sleep(self.timeout_interval)
            await task

        except aiohttp.ServerDisconnectedError as e:
            # clinet와 통신 에러
            logging.warning(f"[WS RES] SERVER DISCONNECTED ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "detail":"server disconnected"})
        except TimeoutError as e:
            # clinet와 타임 아웃 에러
            logging.warning(f"[WS RES] TIMEOUT ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "detail":f"time out error: exceed {self.limit_timeout_count * self.timeout_interval}s"})
        except aiohttp.ServerConnectionError as e:
            # ComfyUI 서버와 통신 에러
            logging.error(f"[WS REQ] SERVER CONNECTION ERROR / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "detail":"server connection error"})
        except Exception as e:
            # 알 수 없는 에러
            logging.error(f"[WS] UNKNOWN ERROR / {e} / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"error", "detail":"internal server error"})
        finally:
            # 최종적으로 웹소켓을 닫고 웹소켓 관련 리소스를 release
            logging.info(f"[WS] CLOSING / {sid}")
            await self.socket_manager.async_send_json(sid, {"status":"closed", "detail":"connection will be closed"}, update_life=False)
            asyncio.create_task(self.socket_manager.async_release_sockets(sid))
     
            if session is not None:
                await session.close()

        return web.Response(text="Dummy response")
    
    async def _ws_res_connection(self, request, sid):
        """
        client와 웹소켓 응답(WebSocket Response) 연결을 처리합니다.
        해당 sid는 ws_res와 ws_req 모두 공유해야 합니다.

        Args:
            request (Request): HTTP 요청 객체입니다.
            sid (str): 소켓 ID입니다.

        Returns:
            None
        """
        ws_res = web.WebSocketResponse()
        await ws_res.prepare(request)
        self.socket_manager[sid].sockets_res = ws_res
        logging.info(f"[WS RES] HANDSHAKE / {sid}")

    async def _ws_req_connection(self, sid):
        """
        ComfyUI서버와 소켓 요청(WebSocket Request) 연결을 처리합니다.
        해당 sid는 ws_res와 ws_req 모두 공유해야 합니다.

        Args:
            sid (str): 소켓 ID입니다.

        Returns:
            aiohttp.ClientSession: 클라이언트 세션 객체입니다.
        """
        # 이미 해당 sid에 할당된 서버가 있는지 확인
        if self.socket_manager[sid].linked_server is None:
            server_address = await self.get_not_busy_server_address()
            self.socket_manager[sid].linked_server = server_address
            logging.debug(f"[WS REQ] server allocated to {server_address} / {sid}")
        else:
            server_address = self.socket_manager[sid].linked_server

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
        """
        가장 대기열이 적은 ComfyUI 서버의 주소를 가져옵니다.

        Returns:
            str: ComfyUI 서버 주소입니다.
        """
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
        """
        bridge server에 저장된 워크플로우와 client가 추가한 custom input을 기반으로 ComfyUI 서버에 작업을 요청합니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받으며, JSON 형식의 custom input 양식 데이터를 본문으로 받습니다.
            
        Returns:
            web.Response: HTTP 응답 객체입니다. 작업이 성공적으로 큐에 추가되었음을 나타내는 JSON 응답을 반환합니다.
        """
        data = await request.json()
        sid = request.rel_url.query.get('clientId', None)
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")

        workflow = data.pop("workflow", None)
        if not isinstance(workflow, str): raise TypeError(f"workflow is required and must be and str, but got {type(sid).__str__()}")
        workflow = self.wf_alias_map[workflow]

        if self.socket_manager[sid].sockets_res is None:
            # 소켓이 생성된 적이 없다면, REST 통신입니다. 여기서 소켓을 생성하여 ComfyUI와 통신합니다.
            asyncio.create_task(self.websocket_connection(request, mode="REST"))
        
        # ComfyUI서버가 할당될 때까지 기다립니다. 지속될 경우 타임아웃에러를 발생합니다.
        await asyncio.sleep(0.5)
        timeout_count = 0
        while self.socket_manager[sid].linked_server is None:
            await asyncio.sleep(self.timeout_interval)
            if timeout_count >= self.limit_timeout_count:
                raise TimeoutError(f"timeout count: {timeout_count}")
            timeout_count += 1
        
        kwargs = {}
        for key, value in data.items():
            # client가 보낸 custom input의 파일명을 /tmp/에서 탐색합니다.
            if isinstance(value, str) and value.startswith("bridge_server_comfyui_"):
                tmp_path = os.path.join(tempfile.gettempdir(), value)
                mime_type = self.validator.get_mime_type_from_file(file_path=tmp_path)
                extension = self.validator.mime_extension_map[mime_type]
                
                if os.path.exists(tmp_path):
                    # 존재할 경우 할당된 ComfyUI서버에 업로드합니다.
                    upload_result = upload_image(input_path=tmp_path,
                                                file_name=os.path.basename(tmp_path)+extension,
                                                server_address=self.socket_manager[sid].linked_server)
                    kwargs[key] = os.path.join(upload_result["subfolder"], upload_result["name"])
                    # 업로드 후 임시 파일을 삭제합니다.
                    os.remove(tmp_path)
                else:
                    raise ValueError(f"'{value}' file is not exist in server.")
            else:
                kwargs[key] = value

        # ComfyUI 서버의 prompt 양식에 맞게끔 파싱합니다.     
        prompt = parse_workflow_prompt(os.path.join(self.wf_dir, workflow), 
                                       tracing_mime_types=self.validator.ALLOWED_MIME_TYPES, 
                                       **kwargs)
        self.socket_manager[sid].wf_info = prompt
        # 할당된 ComfyUI 서버에 prompt를 등록합니다. 
        prompt = queue_prompt(prompt, sid, self.socket_manager[sid].linked_server)

        # generation count 업데이트 
        self.state_obj.generation_count += 1
        await self.state_obj.update()

        # 할당된 ComfyUI 서버의 현재 대기열을 반환합니다.
        queue_state = get_queue_state(self.socket_manager[sid].linked_server)
        queue_length = sum([len(cur) for cur in queue_state.values()])
        
        return web.Response(
            status=200,
            body=json.dumps({"detail":f"queued / {queue_length}"}),
            headers={"Content-Type": "application/json"}
        )
    
    async def upload(self, request):
        """
        파일을 bridge server의 /temp/경로에 임시로 업로드합니다.
        임시 저장된 파일은 안전성 검사를 거칩니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다.
            
        Returns:
            web.Response: HTTP 응답 객체입니다. 업로드된 파일의 이름을 포함하는 JSON 응답을 반환합니다.
        """
        sid = request.rel_url.query.get('clientId', None)
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")

        if self.socket_manager[sid].linked_server is None:
            # sid가 제출된 적이 없다면, REST 통신. 여기서 ComfyUI 서버 할당
            server_address = await self.get_not_busy_server_address()
            self.socket_manager[sid].linked_server = server_address
        
        reader= await request.multipart()
        logging.info(f"[POST] '{request.path}'")

        fns={}
        async for part in reader:

            try:
                file_identifier = part.name
                file_name = os.path.basename(part.filename)
                file_data = await part.read()

                # 바이트 파일이 안전한지 검사
                is_valid, detail_about, tmp_path = await self.validator.validate_and_sanitize_file(file_data, file_name, return_tmp_path=True)

                if is_valid == True:
                    if "image" in detail_about:
                        # 이미지 일 때 valid TODO: 저 많은 타입을 허락해야 함
                        pass
                    else:
                        # 그 외 금지
                        os.remove(tmp_path)
                        raise TypeError(f"{detail_about} is not allowed type / {file_name}")
                else:
                    # 안전하지 않다면 삭제, 에러발생
                    if tmp_path is not None:
                        os.remove(tmp_path)
                    raise TypeError(f"{detail_about} / {file_name}")
                
                fns[file_identifier] = os.path.basename(tmp_path)
                logging.debug(f"[POST] '{request.path}' / {file_name} saved / {sid}")
        
            except Exception as e:
                logging.error(f"[POST] '{request.path}' / {file_name} can't save / {e} / {sid}")

                return web.Response(
                    status=400,
                    body=json.dumps({"detail":f"{file_name} can't save / {e}"}),
                    headers={"Content-Type": "application/json"}
                )

        return web.Response(
            status=200,
            body=json.dumps(fns),
            headers={"Content-Type": "application/json"}
        )
        
    async def get_history(self, request):
        """
        client id에 할당된 ComfyUI 서버의 history를 가져옵니다.
        ComfyUI가 보낸 파일을 안전성 검사합니다.
        실행이 끝난 후, 해당 client id의 life cycle이 끝났다고 판단하여 모든 리소스를 해제합니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다.
            
        Returns:
            web.Response: HTTP 응답 객체입니다. ComfyUI 서버의 히스토리를 포함하는 멀티파트 HTTP 응답을 반환합니다.
        """
        
        sid = request.rel_url.query.get('clientId', None)
        res_type = request.rel_url.query.get('resType', "multipart")
        if not isinstance(sid, str): raise TypeError(f"clientId is must be str, but got {type(sid).__str__()}")
        
        server_address = self.socket_manager[sid].linked_server
        if server_address is None:
            return web.Response(
                status=204,
                body=json.dumps({"detail":f"The client ID has not been submitted to the server before. It is not recognized. / {sid}"}),
                headers={"Content-Type": "application/json"}
            )
        
        prompt_id = self.socket_manager[sid].comfyui_prompt_id
        history = get_history(prompt_id, server_address)
        history = history.get(prompt_id, None)
        logging.debug(f"[GET] '{request.path}' / GET HISTORY / {sid}")
        
        if history is not None:
            output = history["outputs"]
            if isinstance(output, tuple):
                output = output[0]

            file_names, file_contents = process_outputs(output, server_address)

            if res_type == "multipart":
                data = aiohttp.FormData()
            elif res_type == "base64":
                encoded_files = []
            else:
                raise ValueError(f"resType is must be [multipart, base64] but got {res_type}")
            
            for idx, (file_name, file_content) in enumerate(zip(file_names, file_contents)):
                # 바이트 파일이 안전한지 검사
                is_valid, detail_about, _ = await self.validator.validate_and_sanitize_file(file_content, file_name)

                if is_valid:
                    if res_type == "multipart":
                        data.add_field(
                            f'result_{idx}',
                            file_content,
                            content_type=detail_about,
                            filename=file_name,
                        )
                    elif res_type == "base64":
                        encoded_file = base64.b64encode(file_content).decode('utf-8')
                        encoded_files.append({
                            'file_name': file_name,
                            'content_type': detail_about,
                            'content': encoded_file,
                        })
                    else:
                        raise ValueError(f"resType is must be [multipart, base64] but got {res_type}")
                else:
                    logging.debug(f"{detail_about} / {file_name} / {sid}")
                    continue

            # client id life cycle is over. release all resources
            asyncio.create_task(self.socket_manager.async_delete(sid))
            logging.debug(f"[GET] '{request.path}' / DELETE HISTORY / {sid}")

            if res_type == "multipart":
                multipart = data()
                headers = {"Content-Type": multipart.content_type}
                return web.Response(
                    status=200,
                    body=multipart,
                    headers=headers
                )
            elif res_type == "base64":
                headers = {"Content-Type": "application/json"}
                return web.Response(
                    status=200,
                    body=json.dumps({'files': encoded_files}),
                    headers=headers
                )
            else:
                raise ValueError(f"resType is must be [multipart, base64] but got {res_type}")

    async def free_memory(self, request):
        """
        ComfyUI서버의 RAM, GPU 메모리를 해제합니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다. 
            주어지지 않을 경우 모든 ComfyUI서버의 메모리를 해제합니다.
            각 ComfyUI서버 동작에는 큰 영향은 없습니다.
            
        Returns:
            web.Response: HTTP 응답 객체입니다. 서버 메모리 해제 완료 메시지를 반환합니다.
        """
        sid = request.rel_url.query.get('clientId', None)
        if sid is not None:
            post_free_memory(self.socket_manager[sid].linked_server)
        else:
            for address in self.server_address:
                try:
                    post_free_memory(address)
                except Exception as e:
                    continue
        return web.Response(status=200, body=json.dumps({"detail":f"server memory free now / {sid if sid else "ALL"}"}), content_type="application/json")
    
    async def interrupt_generation(self, request):
        """
        client id에 해당하는 ComfyUI 서버의 작업 중단 요청을 처리합니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 중단 요청의 처리결과를 나타내는 JSON 응답을 반환합니다.
        """
        sid = request.rel_url.query.get('clientId', None)
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be str, but got {type(sid).__str__()}")

        await self.socket_manager.async_delete(sid)
        return web.Response(status=200, body=json.dumps({"detail":f"interrupted that clientId will be ignored. / {sid}"}), content_type="application/json")

    async def get_generation_count(self, _):
        """
        실행 횟수를 가져오는 메서드입니다. bridge server가 AI 작업 요청 전체 처리 횟수를 반환합니다.
        
        Args:
            _ (Any): 인자를 받지 않습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 실행 횟수를 나타내는 JSON 응답을 반환합니다.
        """
        generation_count = self.state_obj.generation_count
        return web.Response(status=200, body=json.dumps(generation_count), content_type="application/json")
    
    async def get_execution_info(self, request):
        """
        client id에 해당하는 작업의 실행 정보를 가져오는 메서드입니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 소켓 ID를 'clientId' 쿼리 파라미터로 받습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 실행 정보를 나타내는 JSON 응답을 반환합니다.
        """
        sid = request.rel_url.query.get('clientId', None)
        if not isinstance(sid, str): raise TypeError(f"clientId is required and must be and str, but got {type(sid).__str__()}")
        execution_info = self.socket_manager[sid].execution_info
        return web.Response(status=200, body=json.dumps(execution_info), content_type="application/json")

    async def get_workflow_list(self, _):
        """
        bridge_server/workflows의 목록을 가져오는 메서드입니다.
        workflow alias를 반환합니다. alias가 지정되지 않았을 경우, workflow file name을 반환합니다.
        
        Args:
            _ (Any): 인자를 받지 않습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 워크플로우 목록을 나타내는 JSON 응답을 반환합니다.
        """
        wf_alias_list_with_desc = self.wf_alias_list_with_desc
        return web.Response(status=200, body=json.dumps(wf_alias_list_with_desc), content_type="application/json")
    
    async def get_workflow_info(self, request):
        """
        워크플로우의 custom input 정보를 가져오는 메서드입니다.
        
        Args:
            request (Request): HTTP 요청 객체입니다. 'workflow' 쿼리 파라미터로 워크플로우의 이름을 받습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 워크플로우의 custom input 정보를 나타내는 JSON 응답을 반환합니다.
        """
        workflow = request.rel_url.query.get('workflow', '')
        if not isinstance(workflow, str): raise TypeError(f"workflow is required and must be and str, but got {type(workflow).__str__()}")
        workflow = self.wf_alias_map[workflow]
        node_info = get_parsed_input_nodes(os.path.join(self.wf_dir, workflow),
                                           tracing_mime_types=self.validator.ALLOWED_MIME_TYPES)
        return web.Response(status=200, body=json.dumps(node_info), content_type="application/json")
    
    async def main_page(self, _):
        """
        메인 페이지를 반환하는 메서드입니다.
        
        Args:
            _ (Any): 인자를 받지 않습니다.
        
        Returns:
            web.Response: HTTP 응답 객체입니다. 간단한 환영 메시지를 텍스트로 반환합니다.
        """
        return web.Response(text="Hello, this is bridge server for comfyui! (made by middlek)")
