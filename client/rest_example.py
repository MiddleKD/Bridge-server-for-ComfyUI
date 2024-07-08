import os
import asyncio
import aiofiles
import requests
import aiohttp
import magic

server_address = "localhost:8000"

# Assume mime type
def get_mime_type(file_path):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    return mime_type

def get_mime_type_from_binary(binary_data):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_buffer(binary_data)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    return mime_type

def get_request(api, query = {}):
    headers = {"Content-Type": "application/json"}
    query_string = "&".join([f"{key}={value}" for key, value in query.items()])
    try:
        response = requests.get(
            url=f'http://{server_address}/{api}?{query_string}',
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        else:
            None
    except requests.RequestException as e:
        print(e)

def post_request(api, data, client_id=None):
    headers = {"Content-Type": "application/json"}
    try:
        url = f'http://{server_address}/{api}'
        if client_id is not None:
            url += f"?clientId={client_id}"
        response = requests.post(
            url=url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(e)

async def get_history(client_id, download=True):
    await asyncio.sleep(1)
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                url=f'http://{server_address}/history?clientId={client_id}')

            if download == True and response.status == 200:
                
                reader = aiohttp.MultipartReader.from_response(response)
                async for part in reader:
                    await save_file_from_part(part)
                await reader.release()
            
            return response

    except aiohttp.ServerDisconnectedError as e:
        print(e)
    finally:
        await session.close()

async def upload_file(file_paths):
    url = f"http://{server_address}/upload"

    if not isinstance(file_paths, list):
        file_paths = [file_paths]

    async with aiohttp.ClientSession() as session:

        data = aiohttp.FormData()
        file_path_identifier_map = {}
        for idx, file_path in enumerate(file_paths):
            with open(file_path, 'rb') as file:
                file_data = file.read()
                data.add_field(
                    f'upload_{idx}',
                    file_data,
                    content_type=get_mime_type_from_binary(file_data),
                    filename=os.path.basename(file_path),
                )
                file_path_identifier_map[f'upload_{idx}'] = file_path
        multipart = data()
        headers = {"Content-Type": multipart.content_type}

        async with session.post(url, data=multipart, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                return {file_path_identifier_map[key]:value for key,value in response_data.items()}
            else:
                print(f"Error uploading file: {response.status}")
                return None

async def save_file_from_part(part, default_filename='downloaded_file'):

    filename = part.filename
    
    if filename is None:
        filename = default_filename

    base_name, extension = os.path.splitext(filename)
    new_file_name = filename

    counter = 1
    while os.path.exists(new_file_name):
        new_file_name = f"{base_name} ({counter}){extension}"
        counter += 1
    
    save_path = new_file_name

    async with aiofiles.open(save_path, 'wb') as f:
        while True:
            chunk = await part.read_chunk()
            if not chunk:
                break
            await f.write(chunk)

    return save_path

async def tracing(ci):
    timeout_count = 0
    ex_info_before = None
    while True:
        await asyncio.sleep(0.5)
        ex_info = get_request("execution-info", query={"clientId": ci})
        print(ex_info)

        if ex_info_before == ex_info:
            timeout_count += 1
        else:
            ex_info_before = ex_info
            timeout_count = 0

        if timeout_count > 500:
            print("time out too long delay")
            break
        elif ex_info.get("status", None) == "closed": 
            break

async def run_client(client_id, data):
    post_request("generate-based-workflow", data, client_id)
    await tracing(client_id)
    await get_history(client_id, download=True)

async def main(ci_list, wf_list, is_test=False):
    user_inputs = []
    for wf in wf_list:
        wf_info = get_request("workflow-info", query={"workflow":wf})
        
        user_input = {"workflow":wf}

        if is_test == False:
            for key, info in wf_info.items():
                user_tipe = input(
f"""-------------------
Node:{key}
Title:{info["title"]}
Class:{info["class"]}
Input:
""") or info["default"]
                
                if info["type"] == "int":
                    user_input[key] = int(user_tipe)
                elif info["type"] == "float":
                    user_input[key] = float(user_tipe)
                else:
                    user_tipe_str = str(user_tipe)
                    if os.path.isfile(user_tipe_str):
                        response_data = await upload_file(user_tipe_str)
                        user_input[key] = response_data[user_tipe_str]
                    else:
                        user_input[key] = user_tipe_str
    
        user_inputs.append(user_input)

    tasks = [run_client(ci_list[idx], user_inputs[idx]) 
             for idx in range(len(ci_list))]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    import argparse
    import uuid

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=server_address, type=str)
    parser.add_argument("--wfs", nargs='+', default=[], type=str)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    server_address = args.url
    print(f"AI server address is '{server_address}'")

    if args.test == True:
        with open("test_wf_names.txt", mode="r") as f:
            wf_list = [cur.strip() for cur in f.readlines()]
    else:
        wf_list = args.wfs
    
    ci_list = [str(uuid.uuid4()) for _ in range(len(wf_list))]

    asyncio.run(main(ci_list, wf_list, is_test=args.test))
