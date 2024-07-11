import os
import shutil
import argparse

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
    parser = argparse.ArgumentParser(description='Recursively move files from src to dest, overwriting existing files.')
    parser.add_argument('--src', type=str, help='Source directory from where files will be moved.', default="./comfyui_patch")
    parser.add_argument('--dest', type=str, help='Destination directory where files will be moved.')

    args = parser.parse_args()
    
    patch(args.src, args.dest)
