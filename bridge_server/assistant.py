import os, json
import urllib.error
import aiofiles
import json
from asyncio import Lock
import urllib
from requests_toolbelt import MultipartEncoder

# Manage json file
class AsyncJsonWrapper:
    def __init__(self, filename):
        self.filename = filename
        self.contents = None
        self.lock = Lock()

    async def load(self):
        async with self.lock:
            async with aiofiles.open(self.filename, 'r') as f:
                data = await f.read()
                self.contents = json.loads(data)

    async def update(self):
        async with self.lock:
            async with aiofiles.open(self.filename, 'w') as f:
                await f.write(json.dumps(self.contents, indent=4))

    def __getattr__(self, name):
        if self.contents and name in self.contents:
            return self.contents[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name in ('filename', 'contents', 'lock'):
            super().__setattr__(name, value)
        else:
            if self.contents is None:
                self.contents = {}
            self.contents[name] = value

def make_workflow_alias_map(wf_dir, wf_alias_fn) -> dict:
    with open(wf_alias_fn, mode="r") as f:
        jsonlike = json.load(f)
    
    wf_alias_map = jsonlike
    for cur in os.listdir(wf_dir):
        if cur not in jsonlike.values() and cur.endswith(".json"):
            wf_alias_map[cur] = cur
        else:
            continue
    return wf_alias_map
    

# API
def queue_prompt(prompt, client_id, server_address):
    p = {"prompt": prompt, "client_id": client_id}
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data, headers=headers)
    return json.loads(urllib.request.urlopen(req).read())

def get_queue_state(server_address):
    with urllib.request.urlopen(f"http://{server_address}/queue") as response:
        return json.loads(response.read())

def get_history(client_id, server_address):
    with urllib.request.urlopen(f"http://{server_address}/history/{client_id}") as response:
        return json.loads(response.read())

def delete_history(client_id, server_address):
    url = f"http://{server_address}/history"
    data = json.dumps({"delete": client_id}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json'
    }
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(request) as response:
        return response.status

def post_free_memory(server_address):
    url = f"http://{server_address}/free/"
    data = json.dumps({"unload_models": True, "free_memory":True}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json'
    }
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())

def post_interrupt(server_address):
    url = f"http://{server_address}/interrupt/"
    request = urllib.request.Request(url, method='POST')
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())

def get_image(filename, server_address, image_type="output", subfolder=None, preview_format=None, quality=None, channel=None):
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

    query_string = urllib.parse.urlencode(query_params)
    request = urllib.request.Request(f"http://{server_address}/view?{query_string}")

    with urllib.request.urlopen(request) as response:
        if response.status == 200:
            image_data = response.read()
            return image_data
        else:
            raise urllib.error.HTTPError(msg="Bad request on get image")

def upload_image(input_path, file_name, server_address, image_type="input", overwrite=False):
  with open(input_path, 'rb') as file:
    multipart_data = MultipartEncoder(
      fields= {
        'image': (file_name, file, 'image/png'),
        'type': image_type,
        'overwrite': str(overwrite).lower()
      }
    )

    data = multipart_data
    headers = { 'Content-Type': multipart_data.content_type }
    request = urllib.request.Request("http://{}/upload/image".format(server_address), data=data, headers=headers)
    with urllib.request.urlopen(request) as response:
        if response.status == 200:
            return json.loads(response.read())
        else:
            raise urllib.error.HTTPError(msg="Bad request on upload image")

# Parsing text
def get_parsed_input_nodes(workflow_json):
    if isinstance(workflow_json, str):
        with open(workflow_json, mode="r") as f:
            workflow_json = json.load(f)

    parsed_input_nodes = {}

    for node_number in workflow_json:
        api_inputs = []

        cur_node = workflow_json[node_number]
        meta_data = cur_node["_meta"].get("apiinput", None)
        if meta_data is not None: api_inputs.extend(meta_data.split(","))
        
        for api_input in api_inputs:
            if api_input is not None:
                input_value = cur_node["inputs"].get(api_input, None)
                input_type = type(input_value)

                if (input_type == None) or (input_value == ''):
                    raise ValueError(f"{node_number}:{api_input}, is wrong data('{input_type}', '{input_value}')")
                
                parsed_input_nodes[f"{node_number}/{api_input}"] = {
                    "type":input_type.__name__, 
                    "title":cur_node["_meta"]["title"], 
                    "class":cur_node["class_type"],
                    "default":cur_node["inputs"][api_input]
                }
    return parsed_input_nodes
    
def parse_workflow_prompt(workflow_path, **kwargs):

    with open(workflow_path, mode="r") as f:
        workflow_json = json.load(f)
    
    parsed_input_nodes = get_parsed_input_nodes(workflow_json)
    prompt = workflow_json

    for node_id_and_key, node_info in parsed_input_nodes.items():
        node_id, input_key = node_id_and_key.split("/")
        
        input_value = kwargs.get(node_id_and_key, None)
        if input_value is not None:
            if type(input_value).__name__ != node_info["type"]:
                raise ValueError(f"'{node_id_and_key}' need to have type of {node_info["type"]} but got {type(input_value)} from {input_value})")
        else:
            input_value = node_info.get("default", None)
        prompt[node_id]["inputs"][input_key] = input_value
 
    return prompt

def process_outputs(outputs:dict, server_address):
    file_names, file_contents = [], []

    output_nodes = list(outputs.values())
    for output_node in output_nodes:
        for _, values in output_node.items():
            for value in values:
                if not isinstance(value, dict): continue
                if value.get("type") != "output": continue
                file_name = value.get("filename", None)
                if file_name == None: continue

                file_content = get_image(file_name, server_address, channel="RGB")

                file_names.append(file_name)
                file_contents.append(file_content)

    return file_names, file_contents
