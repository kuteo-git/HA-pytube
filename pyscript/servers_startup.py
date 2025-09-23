import subprocess
import sys
import os
import time
import glob

__BASE_PATH = '/config/pyscript/servers'
__INSTALL_REQUIREMENTS_FILE = 'requirements.txt'

__PYTUBE_SERVER_PATH = f'{__BASE_PATH}/pytube'
__PYTUBE_SERVER_FILE = 'pytube_server.py'

def __install_ffmpeg_with_update():
    try:
        # Update package list first
        subprocess.run(['apk', 'update'], check=True, capture_output=True)
        log.info("Package list updated")
        
        # Install ffmpeg
        result = subprocess.run(
            ['apk', 'add', 'ffmpeg'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        log.info(f"FFmpeg installed successfully: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: {e}")
        return False

def __install_requirements(
    requirements_file:str, 
    upgrade=False, 
    user=False
):
    try:
        # Check if requirements file exists
        if not os.path.exists(requirements_file):
            log.error(f"Error: {requirements_file} not found!")
            return False
        
        # Build the pip command
        cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
        
        # Add optional flags
        if upgrade:
            cmd.append("--upgrade")
        if user:
            cmd.append("--user")
        
        log.info(f"Running: {' '.join(cmd)}")
        
        # Execute the command
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        log.info("Installation completed successfully!")
        log.info(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        log.error(f"Error during installation: {e}")
        log.error(f"Return code: {e.returncode}")
        log.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return False


def __install_requirements_simple(
    requirements_file:str
):
    try:
        cmd = f"{sys.executable} -m pip install -r {requirements_file}"
        return os.system(cmd)
    except Exception as e:
        print(f"Unexpected error: {e}")


def __clean_files_in_folder(
    folder: str
):
    """Clean all files from the pytube download folder at midnight daily"""
    try:
        files = glob.glob(os.path.join(folder, "*"))
        removed_count = 0
        for file_path in files:
            if os.path.isfile(file_path):
                os.remove(file_path)
                removed_count += 1
        log.info(f"Successfully removed {removed_count} files from {folder}")
    except Exception as e:
        log.error(f"Error cleaning pytube download folder: {e}")


def __start_server(
    path:str,
    file:str
):  
    try:
        # Kill any existing instances
        subprocess.run(['pkill', '-f', file], check=False)
        time.sleep(3)
        
        # Start new instance
        subprocess.Popen([
            'python3', 
            f'{path}/{file}'
        ], cwd='/config/pyscript')
        
        log.info(f"`{file}` server started via Pyscript")
        
    except Exception as e:
        log.error(f"Failed to start {file} server: {e}")


@time_trigger("cron(0 0 */2 * *)")
def clean_downloads():
    """Clean all files from the pytube download folder every 2 days at midnight"""
    __clean_files_in_folder(f"{__PYTUBE_SERVER_PATH}/download")


@time_trigger("startup")
def start_servers_on_boot():
    # Wait for HA to fully start
    time.sleep(15)

    # Install requirements
    __install_ffmpeg_with_update()
    __install_requirements(
        requirements_file = f"{__PYTUBE_SERVER_PATH}/{__INSTALL_REQUIREMENTS_FILE}"
    )

    # Start servers
    __start_server(
        path = __PYTUBE_SERVER_PATH,
        file = __PYTUBE_SERVER_FILE
    )