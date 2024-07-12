import logging
import asyncio
import datetime
from assistant import delete_history

class SocketManager: 
    def __init__(self, loop:asyncio.AbstractEventLoop, interval=3, life_seconds=10):
        """
        SocketManager 클래스를 초기화합니다.

        Args:
            loop (asyncio.AbstractEventLoop): asyncio 이벤트 루프
            interval (int, optional): 삭제 확인 간격(초). 기본값은 3초입니다.
            life_seconds (int, optional): 인스턴스 생존 시간(초). 기본값은 10초입니다.
        """
        self.loop = loop
        self.sid_param_map: dict[str, ParamManager] = {}
        self.delete_task = asyncio.create_task(self.check_delete(interval=interval, life_seconds=life_seconds))

    def create_one(self, sid):
        """
        새로운 ParamManager 인스턴스를 생성합니다.

        Args:
            sid (str): 소켓 ID
        """
        self.sid_param_map[sid] = ParamManager()
    
    async def async_receive(self, sid):
        """
        WebSocket을 통해 메시지를 비동기적으로 수신합니다.

        Args:
            sid (str): 소켓 ID

        Returns:
            WebSocketMessage: 수신된 WebSocket 메시지
        """
        param_manager = self.sid_param_map.get(sid, None)

        if isinstance(param_manager, ParamManager):
            try:
                if hasattr(param_manager.sockets_req, "receive"):
                    return await param_manager.sockets_req.receive()
            except Exception as err:
                param_manager.ws_connection_status = "error"
                logging.debug(f"[WS REQ] RECEIVE FAILED / {err} / {sid}")
        else:
            raise ValueError(f"Wrong type({type(param_manager)}) to execute in {sid} of SocketManager")
    
    async def async_send_json(self, sid, message, update_life=True):
        """
        WebSocket을 통해 JSON 메시지를 비동기적으로 전송합니다.

        Args:
            sid (str): 소켓 ID
            message (dict): 전송할 JSON 메시지
            update_life (bool, optional): ParamManager의 생명 주기를 업데이트할지 여부. 기본값은 True입니다.
        """
        param_manager = self.sid_param_map.get(sid, None)

        if isinstance(param_manager, ParamManager):
            try:
                if hasattr(param_manager.sockets_res, "send_json"):
                    await param_manager.sockets_res.send_json(message)
                    logging.debug(f"[WS RES] SEND OK / {message} / {sid}")
            except Exception as err:
                param_manager.ws_connection_status = "error"
                logging.debug(f"[WS RES] SEND FAILED / {err} / {message} / {sid}")
            if update_life == True:
                if isinstance(message, dict):
                    param_manager.ws_connection_status = message.get("status", "error")
                param_manager.execution_info = message
        else:
            logging.error(f"[WS RES] SEND FAILED / Wrong type({type(param_manager)}) to execute in sid of SocketManager / {message} / {sid}")

    async def async_release_sockets(self, sid):
        """
        소켓 리소스를 비동기적으로 해제합니다.

        Args:
            sid (str): 소켓 ID
        """
        if sid in self.sid_param_map:
            await self.sid_param_map[sid].release_sockets()

    async def async_delete(self, sid):
        """
        인스턴스를 비동기적으로 삭제하고 관련된 history ComfyUI서버에서 삭제합니다.

        Args:
            sid (str): 소켓 ID
        """
        if sid in self.sid_param_map:
            delete_history(self.sid_param_map[sid].comfyui_prompt_id, self.sid_param_map[sid].linked_server)
            await self.sid_param_map[sid].release()
            del self.sid_param_map[sid]

    async def check_delete(self, interval, life_seconds):
        """
        주기적으로 인스턴스의 수명을 확인하고, 만료된 인스턴스를 삭제합니다.

        Args:
            interval (int): 확인 간격(초)
            life_seconds (int): 인스턴스 생존 시간(초)
        """

        while True:
            await asyncio.sleep(interval)

            sids_to_delete = []
            current_time = datetime.datetime.now()

            for sid, param_manager in self.sid_param_map.items():
                if isinstance(param_manager, ParamManager):
                    # life_seconds보다 업데이트가 발생하지 않았다면 삭제 리스트에 추가
                    if (current_time - param_manager.history_life).total_seconds() > life_seconds:
                        sids_to_delete.append(sid)
                else:
                    sids_to_delete.append(sid)
            
            # 리스트에 있는 소켓 ID에 해당하는 인스턴스 삭제
            for sid in sids_to_delete:
                await self.async_delete(sid)

    def __getitem__(self, sid):
        """
        특정 소켓 ID에 대한 ParamManager를 가져옵니다.
        만약 존재하지 않는다면 생성합니다.

        Args:
            sid (str): 소켓 ID
        
        Returns:
            ParamManager: 해당 소켓 ID에 대한 ParamManager 인스턴스
        """
        if self.sid_param_map.get(sid, None) is None:
            self.create_one(sid)
        return self.sid_param_map[sid]

    

class ParamManager:
    def __init__(self):
        self._sockets_res = None    # client와 통신하는 웹소켓
        self._sockets_req = None    # ComfyUI 서버와 통신하는 웹소켓
        self._linked_server = None  # 할당된 ComfyUI 주소
        self._wf_info = None    # 할당된 workflow 정보
        self._ws_connection_status = None   # 현재 웹소켓 연결 상태
        self._execution_info = None # 현재 작업 진행 상황
        self._comfyui_prompt_id = None  # ComfyUI에서 내부적으로 할당한 prompt_id
        self._history_life = datetime.datetime.now()    # history를 얼마나 보존할지에 대한 생명 주기

    async def release_sockets(self):
        """
        소켓 리소스를 해제하고 관련 의존성을 삭제합니다.
        """
        if self._sockets_res is not None:
            await self.sockets_res.close()
        if self.sockets_req is not None:
            await self.sockets_req.close()
        self.sockets_res = None
        self.sockets_req = None
        self.ws_connection_status = None
        self.wf_info = None
        self.comfyui_prompt_id = None

    async def release(self):
        """
        모든 리소스를 해제합니다.
        """
        await self.release_sockets()
        self.execution_info = None
        self._life = None
    
    def update_life(self):
        """
        history 생명 주기를 현재 시간으로 업데이트합니다.
        """
        self._history_life = datetime.datetime.now()
    
    @property
    def sockets_res(self):
        return self._sockets_res
    @property
    def sockets_req(self):
        return self._sockets_req
    @property
    def linked_server(self):
        return self._linked_server
    @property
    def wf_info(self):
        return self._wf_info
    @property
    def ws_connection_status(self):
        return self._ws_connection_status
    @property
    def execution_info(self):
        return self._execution_info
    @property
    def comfyui_prompt_id(self):
        return self._comfyui_prompt_id
    @property
    def history_life(self):
        return self._history_life
    
    @sockets_res.setter
    def sockets_res(self, value):
        self._sockets_res = value  
    @sockets_req.setter
    def sockets_req(self, value):
        self._sockets_req = value
    @linked_server.setter
    def linked_server(self, value):
        self._linked_server = value
    @wf_info.setter
    def wf_info(self, value):
        self._wf_info = value
    @ws_connection_status.setter
    def ws_connection_status(self, value):
        # connection status 업데이트시 생명주기 업데이트
        self._ws_connection_status = value
        self.update_life()
    @execution_info.setter
    def execution_info(self, value):
        # execution info 업데이트시 생명주기 업데이트
        self._execution_info = value
        self.update_life()
    @comfyui_prompt_id.setter
    def comfyui_prompt_id(self, value):
        self._comfyui_prompt_id = value
