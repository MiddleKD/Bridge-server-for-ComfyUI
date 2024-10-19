import os
import shutil
import argparse
import re

def open_file(file_path:str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.read()
    return file_content

def save_file(file_path:str, file_content) -> str:
    with open(file_path, mode='w', encoding='utf-8') as file:
        file.write(file_content)
    return file_path

def find_pattern_from_file_content(file_content:str, pattern:str) -> str:
    match = re.search(pattern, file_content)

    if match:
        extracted_filename = match.group(1)
        return extracted_filename
    else:
        raise ValueError(f"'{pattern}' is not detected from '{file_content[:50]}...'")

def insert_string_to_content(file_content: str, insert_loc_pattern: str, insert_string: str, dynamic_group_pattern:bool=None) -> str:
    match = re.search(insert_loc_pattern, file_content)

    if match is None:
        raise ValueError(f"Does not exist, '{insert_loc_pattern[:50]}' in contents")
    
    if dynamic_group_pattern is not None:
        if dynamic_group_pattern not in insert_loc_pattern:
            raise ValueError(f"Does not exist, '{dynamic_group_pattern}'.\nAre you sure need 'dynamic_group_pattern'?")
        
        replace_group = match.group(1)
        replace_group_match = re.search(dynamic_group_pattern, insert_string)
        
        if replace_group_match is None:
            Warning(f"'{replace_group}' does not exist on 'insert_string': {insert_string}")
        else:
            insert_string = insert_string.replace(replace_group_match.group(0), replace_group)
    
    pos_end = match.end()
    inserted_content = file_content[:pos_end] + insert_string + file_content[pos_end:]
    
    return inserted_content

def update_patch_file(
        src,
        dest,
        index_file_pattern,
        insert_string,
        insert_loc_pattern,
        dynamic_group_pattern=None,
        skip_pattern=None
    ):

    index_file_content = open_file(os.path.join(dest, "web", "index.html"))
    core_file_name = find_pattern_from_file_content(index_file_content, pattern=index_file_pattern)
    core_file_content = open_file(os.path.join(dest, "web", "assets", core_file_name))

    


    inserted_content = insert_string_to_content(
        core_file_content,
        insert_loc_pattern=insert_loc_pattern,
        insert_string=insert_string,
        dynamic_group_pattern = dynamic_group_pattern
    )

    assets_dir = os.path.join(src, "web", "assets")

    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        
    for file in os.listdir(assets_dir):
        os.remove(os.path.join(assets_dir, file))

    if (skip_pattern is not None) and (re.search(skip_pattern, core_file_content) is not None):
        Warning(f"Already patched ComfyUI. Some process will be skipped.")
        return "{skipped because already patched}"
    
    saved_fn = save_file(os.path.join(assets_dir, core_file_name), inserted_content)
    return saved_fn

def patch(src, dest):
    """
    Recursively move files from src to dest, overwriting existing files.
    
    :param src: Source directory from where files will be moved.
    :param dest: Destination directory where files will be moved.
    """
    if not os.path.exists(dest):
        os.makedirs(dest)
    
    for root, dirs, files in os.walk(src):
        relative_path = os.path.relpath(root, src)
        dest_path = os.path.join(dest, relative_path)

        if not os.path.exists(dest_path):
            os.makedirs(dest_path)
        
        for file in files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(dest_path, file)
            shutil.copy(src_file_path, dest_file_path)

        for dir in dirs:
            dest_dir_path = os.path.join(dest_path, dir)
            if not os.path.exists(dest_dir_path):
                os.makedirs(dest_dir_path)

if __name__ == "__main__":
    default_src = os.path.join(os.path.dirname(__file__), "comfyui_patch")
    
    parser = argparse.ArgumentParser(description='Recursively move files from src to dest, overwriting existing files.')
    parser.add_argument('--src', type=str, help='Source directory from where files will be moved.', default=default_src)
    parser.add_argument('--dest', type=str, help='Destination directory where files will be moved.')

    args = parser.parse_args()
    

    index_file_pattern = r'<script type="module" crossorigin src="\./assets/(.*?)">'
    insert_string = """
// apiinput이 존재하고 길이가 0이 아닌 경우 추가
if (node3.apiinput && node3.apiinput.length > 0) {
  node_data["_meta"].apiinput = node3.apiinput; // comfyui_bridge_server (middlek)
}
"""
    insert_loc_pattern = r'node_data\["_meta"\]\s*=\s*{\s*title:\s*(node\d*)\.title\s*};'
    dynamic_group_pattern = r'node\d*'
    skip_pattern = r'.apiinput.length'


    saved_fn = update_patch_file(
        args.src,
        args.dest,
        index_file_pattern=index_file_pattern,
        insert_string=insert_string,
        insert_loc_pattern=insert_loc_pattern,
        dynamic_group_pattern=dynamic_group_pattern,
        skip_pattern=skip_pattern
    )
    print(f"Update patch file generated on {saved_fn}")
    patch(args.src, args.dest)
    print(f"Patch is done on {args.dest}")