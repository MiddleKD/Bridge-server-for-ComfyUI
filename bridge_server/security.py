import os
import magic
import tempfile
import hashlib
import mimetypes

class FileValidator:
    def __init__(self, allowed_mime_extension_map):
        """
        파일 유효성 검사 클래스를 초기화합니다.
        
        Args:
            allowed_mime_extension_map (dict): 허용된 MIME 타입 및 확장자 매핑이 담긴 사전
        """
        self.mime_extension_map = allowed_mime_extension_map
        self.ALLOWED_MIME_TYPES = list(allowed_mime_extension_map.keys())

    def get_mime_type_from_file(self, file_path):
        """
        파일로부터 MIME 타입을 가져옵니다.
        
        Args:
            file_path (str): 파일 경로
        
        Returns:
            str: 추정된 MIME 타입 문자열 또는 'application/octet-stream'
        """
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        return mime_type or 'application/octet-stream'

    def get_mime_type_from_filename(self, file_name):
        """
        파일 이름에서 MIME 타입을 추정합니다.
        
        Args:
            file_name (str): 파일 이름
        
        Returns:
            str: 추정된 MIME 타입 문자열 또는 'application/octet-stream'
        """
        mime_type, _ = mimetypes.guess_type(file_name)
        return mime_type or 'application/octet-stream'
        
    def get_mime_type_from_binary(self, binary_data):
        """
        이진 데이터에서 MIME 타입을 가져옵니다.
        
        Args:
            binary_data (bytes): 이진 데이터
        
        Returns:
            str: 추정된 MIME 타입 문자열 또는 'application/octet-stream'
        """
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(binary_data)
        return mime_type or 'application/octet-stream'

    def is_safe_filename(self, filename):
        """
        파일 이름이 안전한지 검사합니다.
        
        Args:
            filename (str): 파일 이름
        
        Returns:
            bool: 안전한 파일 이름 여부
        """
        return not (filename.startswith('/') or '..' in filename)

    def is_valid_extension(self, filename, mime_type):
        """
        주어진 파일 이름과 MIME 타입이 허용된 확장자 매핑과 일치하는지 확인합니다.
        
        Args:
            filename (str): 파일 이름
            mime_type (str): MIME 타입 문자열
        
        Returns:
            bool: 유효한 확장자 여부
        """
        extension = os.path.splitext(filename)[1].lower()
        return any(mime_type == allowed_type and extension == allowed_ext
                   for allowed_type, allowed_ext in self.mime_extension_map.items())

    def is_suspicious_file(self, file_path):
        """
        파일이 의심스러운 패턴을 포함하고 있는지 검사합니다.
        
        Args:
            file_path (str): 파일 경로
        
        Returns:
            bool: 의심스러운 파일 여부
        """
        suspicious_patterns = [
            b'<script', b'<?php', b'#!/', b'import ',
            b'eval(', b'exec(', b'system(',
        ]
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        for pattern in suspicious_patterns:
            if pattern in content:
                return True

        return False

    def get_file_hash(self, file_data):
        """
        파일 데이터의 SHA-256 해시 값을 계산합니다.
        
        Args:
            file_data (bytes): 파일 데이터
        
        Returns:
            str: SHA-256 해시 값 (16진수 문자열)
        """
        file_hash = hashlib.sha256(file_data).hexdigest()
        return file_hash

    async def validate_and_sanitize_file(self, file_data, filename, return_tmp_path=False):
        """
        파일을 검증하고, 필요 시 임시 파일로 저장합니다.
        
        Args:
            file_data (bytes): 파일 데이터
            filename (str): 파일 이름
            return_tmp_path (bool, optional): 임시 파일 경로를 반환할지 여부 (기본값: False)
        
        Returns:
            tuple: 검증 결과 (성공 여부, 추가 정보)
                - True/False: 파일이 유효한지 여부
                - str: 오류 메시지 또는 추가 정보
                - str or None: 임시 파일 경로 (return_tmp_path=True 일 때 반환)
        """
        if not self.is_safe_filename(filename):
            return False, "Invalid filename"

        with tempfile.NamedTemporaryFile(prefix="bridge_server_comfyui_", delete=False) as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name

        try:
            mime_type = self.get_mime_type_from_file(tmp_file_path)
            if mime_type not in self.ALLOWED_MIME_TYPES:
                return False, f"Unsupported MIME type: {mime_type}", None

            if not self.is_valid_extension(filename, mime_type):
                return False, "File extension does not match MIME type", None

            if self.is_suspicious_file(tmp_file_path):
                return False, "File is detected as suspicious", None
            
            if return_tmp_path:
                return True, mime_type, tmp_file_path
            else:
                # 임시 파일 경로를 받지 않는다면 임시 파일 삭제
                os.remove(tmp_file_path)
                return True, mime_type, None

        except Exception as e:
            # 에러 발생시 임시 파일 삭제
            os.remove(tmp_file_path)
            return False, str(e), None
