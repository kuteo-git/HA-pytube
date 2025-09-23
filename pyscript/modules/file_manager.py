import json
import os

@pyscript_executor
def read_file_as_dict(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as file_desc:
            return json.load(file_desc)
    except Exception as e:
        logger.error(f"[read_file_as_dict] Failed: {str(e)}")
        return {}

@pyscript_executor
def write_dict_to_file(file_name, data, mode="w"):
    try:
        with open(file_name, mode, encoding="utf-8") as file_desc:
            json.dump(data, file_desc, indent=4)
            return True
    except Exception as e:
        logger.error(f"[write_dict_to_file] Failed: {str(e)}")
        return False

@pyscript_executor
def write_file(data, output_path):
    try:
        with open(output_path, "wb") as f:
            f.write(data)
    except Exception as e:
        logger.error(f"[write_file] Failed: {str(e)}")
        return None

@pyscript_executor
def remove_file(file_path):
    try:
        os.remove(file_path)
        return True
    except Exception as e:
        logger.error(f"[remove_file] Failed: {str(e)}")
        return False

@pyscript_executor
def create_folder(folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"[create_folder] Failed: {str(e)}")
        return False