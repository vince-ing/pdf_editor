import os


def save_bytes_to_file(data: bytes, output_path: str):
    """Saves raw byte data to a file, creating parent directories as needed."""
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)


def ensure_directory_exists(directory_path: str):
    """Ensures a directory exists, creating it if necessary."""
    if directory_path:
        os.makedirs(directory_path, exist_ok=True)