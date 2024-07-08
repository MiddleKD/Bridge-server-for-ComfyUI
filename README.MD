# API specification

# Index
Core API:
- [**[GET]** websocket connection](#-get-websocket-connection)
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