import logging
import asyncio
import datetime
from assistant import delete_history

class SocketManager: 
    def __init__(self, loop:asyncio.AbstractEventLoop, interval=3, life_seconds=10):
        self.loop = loop
        self.sid_param_map: dict[str, ParamManager] = {}
        self.delete_task = asyncio.create_task(self.check_delete(interval=interval, life_seconds=life_seconds))

    def create_one(self, sid):
        self.sid_param_map[sid] = ParamManager()
    
    async def async_receive(self, sid):
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
        if sid in self.sid_param_map:
            await self.sid_param_map[sid].release_sockets()

    async def async_delete(self, sid):
        if sid in self.sid_param_map:
            delete_history(sid, self.sid_param_map[sid].linked_server)
            await self.sid_param_map[sid].release()
            del self.sid_param_map[sid]

    async def check_delete(self, interval, life_seconds):

        while True:
            await asyncio.sleep(interval)

            sids_to_delete = []
            current_time = datetime.datetime.now()

            for sid, param_manager in self.sid_param_map.items():
                if isinstance(param_manager, ParamManager):
                    if (current_time - param_manager.history_life).total_seconds() > life_seconds:
                        sids_to_delete.append(sid)
                else:
                    sids_to_delete.append(sid)
            
            for sid in sids_to_delete:
                await self.async_delete(sid)

    def __getitem__(self, sid):
        if self.sid_param_map.get(sid, None) is None:
            self.create_one(sid)
        return self.sid_param_map[sid]

    

class ParamManager:
    def __init__(self):
        self._sockets_res = None
        self._sockets_req = None
        self._linked_server = None
        self._wf_info = None
        self._ws_connection_status = None
        self._execution_info = None
        self._comfyui_prompt_id = None
        self._history_life = datetime.datetime.now()

    async def release_sockets(self):
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
        await self.release_sockets()
        self.execution_info = None
        self._life = None
    
    def update_life(self):
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
        self._ws_connection_status = value
        self.update_life()
    @execution_info.setter
    def execution_info(self, value):
        self._execution_info = value
        self.update_life()
    @comfyui_prompt_id.setter
    def comfyui_prompt_id(self, value):
        self._comfyui_prompt_id = value
