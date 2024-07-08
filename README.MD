# API specification

# Index
Core API:
- [**[WS]** websocket connection](#-get-websocket-connection)
- [**[GET]** workflow info]()
- [**[GET]** history](#-features)
- [**[POST]** upload image](#-approach)
- [**[POST]** generate based workflow](#-approach)

Util API:
- [**[GET]** workflow list](#️-application)
- [**[GET]** execution info](#-approach)
- [**[GET]** generation count](#-approach)
- [**[POST]** free]()
- [**[POST]** interrupt]()
---

# Core API

## [WS] websocket connection
서버와 클라이언트를 웹소켓 연결합니다.
### endpoint
`WS /ws`
### describe
서버에서 보내는 메시지를 실시간으로 반환합니다. 연결, 실행, 결과 상태 정보를 포함합니다.
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
      | closed | 웹소켓 연결이 끊김 |
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

## [POST] upload image
이미지를 서버에 업로드하고 저장합니다.
### endpoint
`GET /workflow-info`
### describe
클라이언트가 이미지를 업로드하면 서버가 지정된 디렉토리에 이미지를 저장합니다. 각 파일은 고유한 파일명으로 저장되며, 참조용으로 원본 파일 식별자를 제공합니다. 클라이언트는 원본 파일 식별자를 통해, 서버에 어떤 이름으로 이미지를 저장했는지 확인해야 합니다.
### paramter
- **Content-Type:** multipart/form-data
- **body:**
  |  index  | type | required | description |
  |--------|------|------|------|
  | file_name  | int  | yes | 반환할 기록 항목의 최대 수. 기본값: 10 |
  | file_data | int  | yes | 건너뛸 항목의 수. 페이지네이션에 사용. 기본값: 0 |
  | mime_type | int  | no | 건너뛸 항목의 수. 페이지네이션에 사용. 기본값: 0 |
  | part_header | dict  | yes | 건너뛸 항목의 수. 페이지네이션에 사용. 기본값: 0 |
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

## Get History

서버의 생성 기록을 조회합니다.

### endpoint

`GET /history`

### describe

이 엔드포인트는 서버에서 수행된 이전 생성 작업의 목록을 반환합니다. 생성 시간, 사용된 워크플로우, 결과 상태 등의 정보를 포함합니다.

### parameter

| 이름   | 타입 | 필수 | 설명 |
|--------|------|------|------|
| limit  | int  | 아니오 | 반환할 기록 항목의 최대 수. 기본값: 10 |
| offset | int  | 아니오 | 건너뛸 항목의 수. 페이지네이션에 사용. 기본값: 0 |

### response

- success response
    - **상태 코드:** 200 OK
    - **Content-Type:** application/json
      ```json
      {
        "history": [
          {
            "id": "gen_123456",
            "timestamp": "2023-07-07T15:30:00Z",
            "workflow": "text-to-image",
            "status": "completed",
            "result_url": "https://example.com/results/gen_123456.png"
          },
          {
            "id": "gen_123457",
            "timestamp": "2023-07-07T15:35:00Z",
            "workflow": "image-to-image",
            "status": "failed",
            "error_message": "Input image not found"
          }
        ],
        "total_count": 100,
        "page": 3,
        "page_size": 5
      }
      ```

- error response
    - **상태 코드:** 400 Bad Request 또는 500 Internal Server Error
    - **Content-Type:** application/json
      ```json
      {
        "error": "오류 메시지",
        "detail": "상세 오류 설명"
      }
      ```