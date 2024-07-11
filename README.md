# 🎨 Bridge-server-for-ComfyUI
여러 ComfyUI를 통합할 수 있는 브릿지(프록시) 서버입니다.

## 📌 Index

- [Introduction](#-introduction)
- [Install](#-install)
- [How to use](#-how-to-use)
- [API specification](#-api-specification)
- [Configuration guide](#-configuration-guide)
- [Test from client](#-test-from-client)

## 🚀 Introduction
Bridge-server-for-ComfyUI는 IP 공유를 동의한 PC들에 설치된 ComfyUI와 함께 작동하여 자원 제약을 극복합니다. 보다 편하고 효율적인 AI 워크플로우를 제공하는 브릿지 서버입니다.

## 📥 Install
1. Conda 환경 생성 및 활성화:
    ```bash
    conda create -n comfyui-bridge-server
    conda activate comfyui-bridge-server
    ```
2. 리포지토리 클론 및 의존성 설치:
    ```bash
    git clone {this_repository}
    cd bridge-server-for-ComfyUI
    pip install -r requirements.txt
    ```
3. 환경 설정:
    - `bridge_server/.env` 파일을 열고 다음 줄을 수정하세요:
    - `.env`와 `config.json`의 자세한 설정 방법은 [여기](#-configuration-guide)에서 확인하세요.
    ```bash
    COMFYUI_SERVERS={ADD_YOUR_COMFYUI_ADDRESS}
    ```
4. Nginx 설치 및 설정:
    - nginx가 아닌 다른 웹서버도 가능하지만, template은 nginx만 제공됩니다.
    ```bash
    sudo apt install nginx
    # nginx_config 파일을 pc상황에 맞게 수정해주세요.
    sudo cp bridge-server-for-ComfyUI/nginx_config /etc/nginx/sites-available/default
    service nginx start
    ```
## 🖥 How to use
1. 브릿지 서버 실행:
    ```bash
    cd bridge-server-for-ComfyUI
    python3 bridge_server/main.py
    ```
   
2. ComfyUI 실행:
    
    Bridge server와 ComfyUI가 동일 PC에서 실행되는지 여부에 따라 추가 설정이 필요합니다.

    - 동일 PC에서 실행 시:
        ```bash
        # 패치 스크립트 실행:
        python3 bridge-server-for-ComfyUI/patch.py --dest {your_comfyui_path}
        
        # ComfyUI 실행:
        cd {your_comfyui_path}
        conda activate {your_comfyui_env}
        python3 main_adapted.py
        ``````
    - 다른 PC에서 실행 시:
        
        1. ComfyUI PC에서 리포지토리를 다시 클론합니다.
            ```bash
            git clone {this_repository}
            ```
        2. 패치 스크립트 실행.
            ```bash
            python3 bridge-server-for-ComfyUI/patch.py --dest {your_comfyui_path}
            ```
        3. Nginx 설정 및 실행 (위의 설치 단계 참조)
        4. ComfyUI 실행:
            ```bash
            cd {your_comfyui_path}
            conda activate {your_comfyui_env}
            python3 main_adapted.py
            ```
## 📚 API specification
API 명세서는 [여기](bridge_server/README.md)서 확인할 수 있습니다.

## 🛠 Configuration guide
1. `.env`
    ```python
    HOST=127.0.0.1  # Bridge server의 HOST 주소입니다.
    PORT=8000   # Bridge server의 포트번호입니다.
    COMFYUI_SERVERS=127.0.0.1:8188,127.0.0.1:8189 # ComfyUI 서버 제공에 동의한 PC들의 IP와 포트번호입니다. ','로 구분하여 여러개 설정할 수 있습니다. 매우 민감한 정보니 보안에 유의하세요!!! 
    CONFIG=config.json # Bridge server의 설정파일입니다.
    ```
2. `bridge_server/config.json`
    ```python
    {   
        "LOGGING_LEVEL":"DEBUG",    # 서버의 로깅 레벨입니다. WARN을 추천합니다.
        "CURRENT_STATE":"current_state.json", # 실시간으로 변하는 state를 저장하는 파일입니다.
        "WORKFLOW_ALIAS":"workflow_alias.json", # workflow의 별명을 지정하는 파일입니다.
        "WORKFLOW_DIR":"workflows", # workflow를 저장하는 디렉토리입니다.
        "LIMIT_TIMEOUT_COUNT":60,   # timeout exception을 발생시키기 위해 사용되는 변수입니다.
        "TIMEOUT_INTERVAL":1,   # timeout exception을 발생시키기 위해 사용되는 변수입니다.(초단위)
        "UPLOAD_MAX_SIZE":100,  # 업로드 파일 크기 제한입니다. (MB단위)
        "ALLOWED_MIME_TYPE_EXTENSION_MAP":{
            "image/png": ".png",
            "image/jpeg": ".jpg",
        }   # 업로드를 허용하는 파일의 mime type과 타입에 해당하는 확장자 맵핑입니다. 설정된 타입의 파일만 업로드 가능합니다.
    }
    ```
3. `bridge_server/workflow_alias.json`
    ```python
    # workflow 별명:workflow 파일 이름의 맵핑입니다. workflow파일은 bridge_server/workflows에 저장되어야 합니다.
    {
        "image-to-image":"I2I_basic_api.json",
        "text-to-image":"T2I_basic_api.json",
        "image-expansion":"I2I_expand_api.json",
        "image-shift":"I2I_shift_api.json",
    }
    ```
4. `nginx_config`
    ```text
    listen 8200;	# 포트포워딩하여 들어오는 내부 포트입니다.
    listen [::]:8200;	# 포트포워딩하여 들어오는 내부 포트입니다.
    client_max_body_size 100M;	# nginx에서 어용하는 upload 파일 사이즈입니다.

    server_name 00.00.000.000;	# 해당 서버(PC)의 IP 주소입니다. 보안에 유의하세요!!!!

    location / {
        proxy_pass http:#127.0.0.1:8000;	# 내부 Bridge server 혹은 ComfyUI의 address입니다.
    ...
    ```
## 🧑‍💻 Test from client
Bridge server의 API를 이용하는 client의 예시는 [여기](client/README.md)서 확인할 수 있습니다.