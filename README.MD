# 🎨 API specification
ComfyUI의 workflow를 API로 제공하는 **bridge server for comfyui(proxy server)의 API 명세서**입니다. 이 서버는 웹소켓 통신과 REST 통신을 모두 지원하고, 자동으로 리소스를 관리하며 로드밸런싱 기능 또한 제공합니다. 하나의 bridge server만으로 여러 ComfyUI 서버를 통합해보세요!

# 📌 Index
Core API:
- [**[WS]** websocket connection](#ws-websocket-connection)
- [**[GET]** workflow info](#get-workflow-info)
- [**[POST]** upload](#post-upload)
- [**[POST]** generate based workflow](#post-generate-based-workflow)
- [**[GET]** history](#get-history)

Util API:
- [**[GET]** workflow list](#get-workflow-list)
- [**[GET]** execution info](#get-execution-info)
- [**[GET]** generation count](#get-generation-count)
- [**[POST]** free](#post-free)
- [**[POST]** interrupt](#post-interrupt)
---

# 💡 Core API

## [WS] websocket connection
서버와 클라이언트를 웹소켓 연결합니다.
### endpoint
`WS /ws`
### describe
서버에서 보내는 메시지를 실시간으로 반환합니다. 연결, 실행, 결과 상태 정보를 포함합니다. 만약 **AI 프로세스 중에 클라이언트에서 연결을 끊는다면, 서버는 리소스와 대기열을 자동으로 최적화합니다.**
### query
| key   | required | description |
|--------|------|------|
| clientId  | yes | 해당 AI 요청 맥락에서 공유하는 고유 식별값(uuid 추천) |
### response
- success response
    - **상태 코드:** x(웹소켓 연결)
    - **status 종류** 

      모든 웹소켓 메시지는 `{"status":"text", "details":"text"}`형태로 전송됩니다.
      
      | status | description |
      |--------|------|
      | connected | 웹소켓 연결이 성공적으로 연결됨(hand shake) |
      | listening | 웹소켓 연결 유지 중 |
      | progress | 요청한 프로세스를 실행 중 |
      | closed | 웹소켓 연결이 닫힘 |
      | error | 오류가 발생, 웹소켓 연결이 끊어질 것 |

    - **Content-Type:** websocket text
      ```bash
      < {"status": "connected", "details": "server connected"}
      < {"status": "listening", "details": "server is listening"}
      < {"status": "listening", "details": "server is listening"}
      < {"status": "listening", "details": "server is listening"}
      < {"status": "listening", "details": "server is listening"}
      ...
      ```
- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
sudo apt install nodejs
sudo npm install -g wscat
wscat -c ws://{your_server_adress}/ws?clientId={test_client_id}
```

## [GET] workflow info
workflow 실행에 필요한 input 정보를 가져옵니다.
### endpoint
`GET /workflow-info`
### describe
comfyui의 workflow에서 관리자가 직접 지정한 input정보를 불러옵니다. comfyui wokrflow에는 많은 수의 input parameter가 있습니다. 일반 사용자는 모든 parameter를 이해하기 어렵기 때문에, bridge server에서는 **핵심적인 parameter(ex: text, image, seed etc.)를 관리자가 직접 지정**합니다. 이 엔드포인트는 해당 정보를 반환합니다.  
### query
| key   | required | description |
|--------|------|------|
| workflow  | yes | input 정보를 받고자 하는 workflow의 alias |
### response
- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {
        "6/text": 
          {
            "type": "str", 
            "title": "CLIP Text Encode (Prompt)", 
            "class": "CLIPTextEncode", 
            "default": "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
          },
        "10/image": 
          {
            "type": "str", 
            "title": "Load Image", 
            "class": "LoadImage", 
            "default": "i2i_example.jpg"
          }
      }
      ```
- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X GET "http://{your_server_address}/workflow-info?workflow={your_workflow_alias}"
```

## [POST] upload
이미지를 서버에 업로드하고 저장합니다.
### endpoint
`POST /upload`
### describe
클라이언트가 이미지를 업로드하면 서버가 지정된 디렉토리에 이미지를 저장합니다. 각 파일은 고유한 파일명으로 저장되며, 참조용으로 원본 파일 식별자를 제공합니다. 클라이언트는 원본 파일 식별자를 통해, 서버에 어떤 이름으로 이미지를 저장했는지 확인해야 합니다.
### paramter
- **Content-Type:** multipart/form-data; boundary=----{your_boundary}
- **body:**
  |  key  | type | required | description |
  |--------|------|------|------|
  | name  | str | no | 업로드할 파일의 고유 식별자. 기본값: file |
  | filename | str  | yes | 원래 파일명 |
  | value | byte  | yes | 파일의 바이트 형태 |
  | content_type | mime_type | no | 파일의 content type |
  
### response
- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {
        "identifier_1": "saved_path_1.png",
        "identifier_2": "saved_path_2.png",
        "identifier_3": "saved_path_3.png"
      }
      ```
- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X POST "http://localhost:8000/upload" \ 
-H "Content-Type: multipart/form-data" \
-F "{your_identifier_1}=@{your_file_path_1};filename={your_file_name_1}" \
-F "{your_identifier_2}=@{your_file_path_2};filename={your_file_name_2}" \
-F "{your_identifier_3}=@{your_file_path_3};filename={your_file_name_3}" \
...
```
## [POST] generate based workflow
AI 프로세스를 요청합니다.
### endpoint
`POST /generate-based-workflow`
### describe
여러 정보를 통합하여 prompt를 파싱한 후 comfyui의 AI 대기열에 등록합니다.

이 엔드포인트를 실행하기 전에 선행해야할 작업이 있습니다.

0. **[WS] websocket connection(Optional)** 실행 상황을 웹소켓 메시지로 통신합니다. 사용을 권장합니다. 
1. **[GET] workflow info:** workflow를 실행시키기 위해 필요한 input 정보를 가져옵니다.
2. **[POST] upload:** 1번에서 가져온 input 정보에 따라, 필요한 추가 파일을 업로드합니다.
3. **Parsing Prompt:** 2번에 사져온 식별자와 파일 경로를 기반으로 prompt를 파싱합니다.

더 자세한 내용은 `root/client/*_example.py`를 참고해주시기 바랍니다.
### query
| key   | required | description |
|--------|------|------|
| clientId  | yes | 해당 AI 요청 맥락에서 공유하는 고유 식별값(uuid 추천), 웹소켓이 열려있다면 열 때 사용한 client id |
### paramter
- **Content-Type:** application/json
- **body:**
  |  key  | type | required | description |
  |--------|------|------|------|
  | workflow  | str | yes | 실행할 workflow의 alias |
  | {workflow_input_int} | int | no | [GET] workflow info로 가져온 필요 정보 |
  | {workflow_input_float} | float | no | [GET] workflow info로 가져온 필요 정보 |
  | {workflow_input_info} | str | no | [GET] workflow info로 가져온 필요 정보(**파일명 포함**) |
- **example**
  ```json
  {
    "workflow": "image-to-image", 
    "6/text": "the awesome cat", 
    "10/image": "a_photo_of_my_face.png",
    "15/seed": 1234
  }
  ```

### response
- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {
        "detail": "queued / {current queue length}"
      }
      ```
- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X POST "http://{your_server_address}/generate-based-workflow?clientId={your_client_id}" \ 
-H "Content-Type: application/json" \
-d '{
  "workflow": "{your_workflow_alias}", 
  "{workflow_input_text}": "{your_prompt}", 
  "{workflow_input_file}": "{saved_path_on_server}"
  }'
```
## [Get] history

서버의 생성 기록을 조회하고 결과물을 가져옵니다.

### endpoint

`GET /history`

### describe

서버에서 수행된 프로세스의 결과물을 Multipart로 반환합니다. 결과물을 가져온 이후에 해당 history는 삭제됩니다. **프로세스 life cycle의 마지막을 담당**합니다.

### query
| key   | required | description |
|--------|------|------|
| clientId  | yes | [POST] generate based workflow에서 사용했던 client_id |

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** multipart/form-data; boundary=----{your_boundary}
    </br></br>
    - **상태 코드:** 204 No Content 
    - **Content-Type:** application/json
      ```json
      {"detail": "The client ID has not been submitted to the server before. It is not recognized. / {client_id}"}
      ```
      ```json
      {"detail": "No contents with that client id / {client_id}"}
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X GET "http://{your_server_address}/history?clientId={your_client_id_submitted_before}"
```
---
# 🛠 Util API
## [GET] workflow list

현재 서버에 저장된 workflow의 목록을 불러옵니다.

### endpoint

`GET /workflow-list`

### describe

현재 bridge_server의 `.env`에 지정된 **workflow 디렉토리에서 json파일의 alias**를 반환합니다. alias는 `root/bridge_server/workflow_alias.json`에서 설정할 수 있습니다.

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      ["text-to-image", "image-to-image", "image-to-video", "..."]
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X GET "http://{your_server_address}/workflow-list"
```
## [GET] execution info

프로세스의 진행 상태를 불러옵니다.

### endpoint

`GET /execution-info`

### describe

특정 client_id에 할당된 프로세스의 현재 진행 상태를 반환합니다. 이는 웹소켓 통신이 아닌, **REST 통신을 지원하기 위해 개발된 API**입니다. 일정 시간마다 반복 호출하여 사용하세요.

### query
| key   | required | description |
|--------|------|------|
| clientId  | yes | 추적하고자 하는 프로세스의 client_id |

### response

- success response
    - **상태 코드:** 200 OK
    - **status 종류** 

      모든 response는 `{"status":"text", "details":"text"}`형태로 전송됩니다.(웹소켓과 동일)
      | status | description |
      |--------|------|
      | connected | comfy 서버와 성공적으로 연결됨(proxy connection) |
      | progress | 요청한 프로세스를 실행 중 |
      | closed | comfy 서버와 연결이 닫힘 |
      | error | 오류가 발생, comfy 서버와 연결이 끊어질 것 |
    - **Content-Type:** application/json
      ```json
      {"status": "connected", "detail": "server connected"}
      ```
      ```json
      {"status": "progress", "detail": "12.62%"}
      ```
      ```json
      {"status": "closed", "detail": "Execution is done"}
      ```
      ```json
      {"status": "error", "detail": "time out error: exceed 60s"}
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X GET "http://{your_server_address}/execution-info?clientId={your_client_id_to_track}"
```
## [GET] generation count

API로 프로세스를 실행한 횟수를 반환합니다.

### endpoint

`GET /generation-count`

### describe

현재까지 프로세스를 실행한 총 횟수를 반환합니다. 총 횟수는 서버가 꺼져도 계속 누적되어 이어집니다. 해당 정보는 `root/bridge_server/current_state.json`에 실시간으로 저장됩니다. 실행 횟수에 따라서 적절하게 리소스를 관리해보세요.

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      315
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X GET "http://{your_server_address}/generation-count"
```
## [POST] free

comfyui 서버의 리소스를 초기화합니다.

### endpoint

`POST /free`

### describe

comfyui 서버의 GPU, RAM 메모리를 초기화, garbage collection을 실행합니다. **서버 운용 중에 사용해도 문제없습니다. 안심하고 사용하세요.** generation count가 너무 많이 쌓였거나, OOM(Out of memory)가 발생했을 때 실행해보세요.

### query
| key   | required | description |
|--------|------|------|
| clientId  | no | 추적하고자 하는 프로세스의 client_id |

bridge_server는 로드밸런서 역할을 수행할 수 있습니다. **쿼리로 client_id를 제공하면 해당 client_id가 할당된 comfyui 서버만 초기화**합니다.

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {"detail": "server memory free now / ALL"}
      or
      {"detail": "server memory free now / {client_id}"}
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X POST "http://{your_server_address}/free"
```
```bash
curl -X POST "http://{your_server_address}/free?clientId={your_client_id}"
```
## [POST] interrupt

queue된 프로세스를 취소합니다. 

### endpoint

`POST /interrupt`

### describe
[POST] generate based workflow로 대기열에 등록된 프로세스를 취소합니다. **해당 엔드포인트가 실행된 후 대상 프로세스의 실행 순서가 되었을 경우, 작업을 건너뛰고 다음 프로세스를 진행**합니다. 만약 웹소켓을 이용하여 통신하고 있다면, 이 엔드포인트를 사용할 필요가 없습니다. 웹소켓 통신의 경우 클라이언트에서 통신을 끊으면 자동으로 프로세스가 취소됩니다.

**REST 통신을 지원하기 위해 개발된 API**입니다. 클라이언트가 작업을 기다리지 않는다면 이 엔드포인트를 사용하여 리소스를 절약하세요.

### query
| key   | required | description |
|--------|------|------|
| clientId  | yes | 취소하고자 하는 프로세스의 client_id |

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {"detail": "interrupted that clientId will be ignored. / {your_client_id}"}
      ```

- error response
    - **상태 코드:** 400 Bad Request
    - **Content-Type:** application/json
      ```json
      {
        "detail": "상세 오류 설명"
      }
      ```
### tutorial commands
```bash
curl -X POST "http://{your_server_address}/interrupt?clientId={your_client_id}"
```
