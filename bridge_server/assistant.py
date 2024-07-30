import os, json
import urllib.error
import aiofiles
import json
from asyncio import Lock
import urllib
from requests_toolbelt import MultipartEncoder
from security import FileValidator

# Manage json file
class AsyncJsonWrapper:
    def __init__(self, filename):
        # 파일 이름과 비동기 작업을 위한 lock을 초기화
        self.filename = filename
        self.contents = None
        self.lock = Lock()

    async def load(self):
        # 파일에서 JSON 데이터를 비동기로 로드
        async with self.lock:
            async with aiofiles.open(self.filename, 'r') as f:
                data = await f.read()
                self.contents = json.loads(data)

    async def update(self):
        # 현재 내용을 파일에 비동기로 업데이트
        async with self.lock:
            async with aiofiles.open(self.filename, 'w') as f:
                await f.write(json.dumps(self.contents, indent=4))

    def __getattr__(self, name):
        # contents에서 속성을 가져옴 (존재할 경우)
        if self.contents and name in self.contents:
            return self.contents[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        # 미리 정의된 속성이 아닌 경우 contents에 속성을 설정
        if name in ('filename', 'contents', 'lock'):
            super().__setattr__(name, value)
        else:
            if self.contents is None:
                self.contents = {}
            self.contents[name] = value

def make_workflow_alias_list_and_map(wf_dir, wf_alias_fn) -> dict:
    # wf_alias_fn 파일을 열어 JSON 데이터를 로드
    with open(wf_alias_fn, mode="r") as f:
        jsonlike = json.load(f)
    
    wf_alias_list_with_desc = jsonlike
    wf_fns = [cur["fn"] for cur in jsonlike]
    wf_alias_map = {cur["alias"]:cur["fn"] for cur in jsonlike}
    
    # wf_dir 디렉토리 내의 파일 목록을 순회
    for cur in os.listdir(wf_dir):
        # 파일이 jsonlike 값에 없고 .json으로 끝나는 경우
        if cur not in wf_fns and cur.endswith(".json"):
            wf_alias_info = {
                "alias":cur,
                "fn":cur,
                "description":""
            }
            wf_alias_list_with_desc.append(wf_alias_info) # wf_alias_list에 추가  
            wf_alias_map[cur] = cur # wf_alias_map에 추가
        else:
            continue  # 조건에 맞지 않으면 넘어감

    return wf_alias_list_with_desc, wf_alias_map  # 최종적으로 리스트와 맵 반환

# API
def queue_prompt(prompt, client_id, server_address):
    """
    ComfyUI 서버의 queue에 요청을 보냅니다.
    
    Args:
        prompt (dict): ComfyUI에서 요구하는 prompt dictionary
        client_id (str): 클라이언트 ID
        server_address (str): Bridge server에서 할당한 ComfyUI 서버주소
    
    Returns:
        dict: 서버의 응답을 JSON 형식으로 반환
    """
    p = {"prompt": prompt, "client_id": client_id}
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data, headers=headers)
    return json.loads(urllib.request.urlopen(req).read())

def get_queue_state(server_address):
    """
    ComfyUI 서버에서 현재 큐 상태를 가져옵니다.
    
    Args:
        server_address (str): 확인할 ComfyUI 서버주소
    
    Returns:
        dict: 큐 상태를 JSON 형식으로 반환
    """
    with urllib.request.urlopen(f"http://{server_address}/queue") as response:
        return json.loads(response.read())

def get_history(prompt_id, server_address):
    """
    특정 ComfyUI의 prompt_id 대한 history를 가져옵니다.
    prompt_id는 ComfyUI에서 내부적으로 client_id와 1대1 맵핑됩니다.

    Args:
        prompt_id (str): ComfyUI의 prompt_id
        server_address (str): Bridge server에서 할당한 ComfyUI 서버주소
    
    Returns:
        dict: 요청 이력을 JSON 형식으로 반환
    """
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

def delete_history(prompt_id, server_address):
    """
    특정 ComfyUI의 prompt_id대한 history를 삭제합니다.
    
    Args:
        prompt_id (str): ComfyUI의 prompt_id
        server_address (str): Bridge server에서 할당한 ComfyUI 서버주소
    
    Returns:
        int: 서버 응답 상태 코드 (예: 200은 성공)
    """
    url = f"http://{server_address}/history"
    data = json.dumps({"delete": prompt_id}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json'
    }
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(request) as response:
        return response.status

def post_free_memory(server_address):
    """
    ComfyUI 서버에 RAM, GPU 메모리 해제를 요청합니다.
    
    Args:
        server_address (str): 해제할 ComfyUI 주소
    
    Returns:
        dict: 서버의 응답을 JSON 형식으로 반환
    """
    url = f"http://{server_address}/free"
    data = json.dumps({"unload_models": True, "free_memory": True}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json'
    }
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())

def post_interrupt(server_address):
    """
    ComfyUI 서버에서 진행 중인 작업 중단을 요청합니다.
    
    Args:
        server_address (str): 작업 중단할 ComfyUI 주소
    
    Returns:
        dict: 서버의 응답을 JSON 형식으로 반환
    """
    url = f"http://{server_address}/interrupt/"
    request = urllib.request.Request(url, method='POST')
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())

def get_image(filename, server_address, image_type="output", subfolder=None, preview_format=None, quality=None, channel=None):
    """
    ComfyUI서버의 image_type에 해당하는 폴더에서 이미지를 가져옵니다.
    
    Args:
        filename (str): 이미지 파일 이름
        server_address (str): ComfyUI 서버 주소
        image_type (str): 이미지 타입 (기본값: "output")
        subfolder (str, optional): 하위 폴더 (기본값: None)
        preview_format (str, optional): 미리보기 포맷 (기본값: None)
        quality (str, optional): 이미지 품질 (기본값: None)
        channel (str, optional): 이미지 채널 (기본값: None)
    
    Returns:
        bytes: 이미지 데이터
    
    Raises:
        urllib.error.HTTPError: 이미지 가져오기 실패 시 발생
    """
    # 쿼리 파라미터 구성
    query_params = {
        'filename': filename,
        'type': image_type
    }

    if subfolder:
        query_params['subfolder'] = subfolder

    if preview_format:
        preview_value = preview_format
        if quality:
            preview_value += f";{quality}"
        query_params['preview'] = preview_value

    if channel:
        query_params['channel'] = channel

    # 쿼리 문자열 생성
    query_string = urllib.parse.urlencode(query_params)
    request = urllib.request.Request(f"http://{server_address}/view?{query_string}")

    # 요청 보내고 응답 받기
    with urllib.request.urlopen(request) as response:
        if response.status == 200:
            image_data = response.read()
            return image_data
        else:
            raise urllib.error.HTTPError(msg="Bad request on get image")

def upload_image(input_path, file_name, server_address, image_type="input", overwrite=False):
    """
    ComfyUI서버에 image_type에 해당하는 폴더에 이미지를 업로드합니다.
    
    Args:
        input_path (str): 업로드할 이미지 파일의 경로
        file_name (str): 업로드할 이미지 파일 이름
        server_address (str): ComfyUI 서버 주소
        image_type (str): 이미지 타입 (기본값: "input")
        overwrite (bool): 덮어쓰기 여부 (기본값: False)
    
    Returns:
        dict: 서버의 응답을 JSON 형식으로 반환
    
    Raises:
        urllib.error.HTTPError: 이미지 업로드 실패 시 발생
    """

    # 임시로 저장한 파일을 open
    with open(input_path, 'rb') as file:
        # 멀티파트 데이터 구성
        multipart_data = MultipartEncoder(
            fields={
                'image': (file_name, file, 'image/png'),
                'type': image_type,
                'overwrite': str(overwrite).lower()
            }
        )

        data = multipart_data
        headers = {'Content-Type': multipart_data.content_type}
        request = urllib.request.Request(f"http://{server_address}/upload/image", data=data, headers=headers)
        
        # 요청 보내고 응답 받기
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                return json.loads(response.read())
            else:
                raise urllib.error.HTTPError(msg="Bad request on upload image")

# Parsing text
def get_parsed_input_nodes(workflow_json, tracing_mime_types:list=[]):
    """
    ComfyUI의 워크플로우를 파싱하여 Custom input 정보를 가져옵니다.
    
    Args:
        workflow_json (str or dict): 워크플로우 JSON 파일 경로 또는 JSON 데이터
        tracing_mime_types (list): 워크플로우 제공 정보에서 str을 mime type으로 변환할 수 있을 때, 추적하는 mimetype입니다.
    
    Returns:
        dict: 파싱된 Custom input 정보를 담은 dictionary
    
    Raises:
        ValueError: 잘못된 데이터가 있는 경우 발생
    """
    # 입력이 문자열인 경우 파일로 간주하고 JSON 로드
    if isinstance(workflow_json, str):
        with open(workflow_json, mode="r") as f:
            workflow_json = json.load(f)

    parsed_input_nodes = {}

    # 각 노드 번호에 대해 순회
    for node_number in workflow_json:
        api_inputs = []
        cur_node = workflow_json[node_number]
        # apiinput meta데이터가 있으면 Custom input으로 판단
        meta_data = cur_node["_meta"].get("apiinput", None)

        # meta_data가 있는 경우 api_inputs에 추가
        if meta_data is not None:
            api_inputs.extend(meta_data.split(","))
        
        for api_input in api_inputs:
            if api_input is not None:
                input_value = cur_node["inputs"].get(api_input, None)
                input_type = type(input_value).__name__

                # 입력 값이 None이거나 빈 문자열인 경우 오류 발생
                if input_value is None or input_value == '':
                    raise ValueError(f"{node_number}:{api_input}, is wrong data('{input_type}', '{input_value}')")
                
                # input type이 string일 경우 파일 데이터인지 확인
                if input_type == "str":
                    mime_type = FileValidator.get_mime_type_from_filename(input_value)
                    if mime_type in tracing_mime_types:
                        input_type = mime_type
                        
                # 파싱된 입력 노드 정보를 사전에 추가
                parsed_input_nodes[f"{node_number}/{api_input}"] = {
                    "type": input_type,    # default input값의 data type
                    "title": cur_node["_meta"]["title"],    # 해당 노드의 title
                    "default": cur_node["inputs"][api_input]    # 해당 노드의 default input
                }

    return parsed_input_nodes

def parse_workflow_prompt(workflow_path, tracing_mime_types:list=[], **kwargs):
    """
    'get_parsed_input_nodes로 불러온 양식을 채운 client의 custom input을 기반으로
    ComfyUI 워크플로우 프롬프트를 파싱하여 입력 값을 교체합니다.
    
    Args:
        workflow_path (str): 워크플로우 JSON 파일 경로
        tracing_mime_types (list): 워크플로우 제공 정보에서 str을 mime type으로 변환할 수 있을 때, 추적하는 mimetype입니다.
        **kwargs: 노드 ID와 키를 결합한 문자열을 키로, custom input 입력 값을 값으로 받는 인자들
    
    Returns:
        dict: 입력 값이 채워진 ComfyUI에서 실행 가능한 JSON 데이터
    
    Raises:
        ValueError: 입력 값의 타입이 예상된 타입과 다른 경우 발생
    """
    with open(workflow_path, mode="r") as f:
        workflow_json = json.load(f)
    
    parsed_input_nodes = get_parsed_input_nodes(workflow_json)
    prompt = workflow_json

    for node_id_and_key, node_info in parsed_input_nodes.items():
        node_id, input_key = node_id_and_key.split("/")

        input_value = kwargs.get(node_id_and_key, None)
        input_type = type(input_value).__name__
        node_info_type = node_info["type"]

        if input_value is not None:
            if node_info_type in tracing_mime_types:
                pass
            elif node_info_type != input_type:
                raise ValueError(f"'{node_id_and_key}' need to have type of {node_info_type} but got {type(input_value)} from {input_value})")
        else:
            input_value = node_info.get("default", None)
            Warning(f"'{node_id_and_key}' is None. It will be set default values.")
        prompt[node_id]["inputs"][input_key] = input_value

    return prompt

def process_outputs(outputs: dict, server_address):
    """
    ComfyUI의 history를 처리하여 파일 이름과 파일 내용을 반환합니다.
    
    Args:
        outputs (dict): 출력 노드 정보가 담긴 사전
        server_address (str): 서버 주소
    
    Returns:
        tuple: 파일 이름 리스트와 파일 내용 리스트
    
    Notes:
        출력 노드에서 'type'이 'output'인 값들을 서버에서 가져와 처리합니다.
    """
    file_names, file_contents = [], []

    output_nodes = list(outputs.values())
    for output_node in output_nodes:
        for _, values in output_node.items():
            for value in values:
                if not isinstance(value, dict):
                    continue
                if value.get("type") != "output":
                    continue
                file_name = value.get("filename", None)
                if file_name is None:
                    continue
                
                # history에 담긴 filename을 ComfyUI 서버로 요청합니다.
                file_content = get_image(file_name, server_address, channel="RGB")

                file_names.append(file_name)
                file_contents.append(file_content)

    return file_names, file_contents
