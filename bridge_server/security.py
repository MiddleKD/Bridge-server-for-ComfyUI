import os
import magic
import tempfile
import hashlib
import mimetypes

class FileValidator:
    def __init__(self, aloowed_mime_extension_map):
        self.mime_extension_map = aloowed_mime_extension_map
        self.ALLOWED_MIME_TYPES = list(aloowed_mime_extension_map.keys())

    def get_mime_type_from_file(self, file_path):
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        return mime_type or 'application/octet-stream'

    def get_mime_type_from_filename(self, file_name):
        mime_type, _ = mimetypes.guess_type(file_name)
        return mime_type or 'application/octet-stream'
        
    def get_mime_type_from_binary(self, binary_data):
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(binary_data)
        return mime_type or 'application/octet-stream'

    def is_safe_filename(self, filename):
        return not (filename.startswith('/') or '..' in filename)

    def is_valid_extension(self, filename, mime_type):
        extension = os.path.splitext(filename)[1].lower()
        return any(mime_type == allowed_type and extension == allowed_ext
                   for allowed_type, allowed_ext in self.mime_extension_map.items())

    def is_suspicious_file(self, file_path):
        with open(file_path, 'rb') as f:
            content = f.read()
        
        suspicious_patterns = [
            b'<script', b'<?php', b'#!/', b'import ',
            b'eval(', b'exec(', b'system(',
        ]
        
        for pattern in suspicious_patterns:
            if pattern in content:
                return True

        return False

    def get_file_hash(self, file_data):
        file_hash = hashlib.sha256(file_data).hexdigest()
        return file_hash

    async def validate_and_sanitize_file(self, file_data, filename, return_tmp_path=False):

        if not self.is_safe_filename(filename):
            return False, "Invalid filename"

        with tempfile.NamedTemporaryFile(prefix="bridge_server_comfyui_", delete=False) as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name

        mime_type = self.get_mime_type_from_file(tmp_file_path)
        if mime_type not in self.ALLOWED_MIME_TYPES:
            return False, f"Unsupported MIME type: {mime_type}"

        if not self.is_valid_extension(filename, mime_type):
            return False, "File extension does not match MIME type"

        if self.is_suspicious_file(tmp_file_path):
            return False, "File is detected as suspicious"
        
        if return_tmp_path == True:
            return True, mime_type, tmp_file_path
        else:
            os.remove(tmp_file_path)
            return True, mime_type, None