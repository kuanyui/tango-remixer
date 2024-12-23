from pathlib import Path
import urllib.request
import tarfile
import shutil
import os
# from typing import Optional

def download_file(file_url: str, dst_file_path: Path) -> bool:
    try:
        dst_file_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(file_url) as response:
            with open(dst_file_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"Download failed: {str(e)}")
        return False

def extract_tarball(tarball_path: Path, dst_dir_path: Path) -> bool:
    try:
        dst_dir_path.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tarball_path) as tar:
            def is_within_directory(directory: Path, target: Path) -> bool:
                abs_directory = directory.resolve()
                abs_target = target.resolve()
                prefix = os.path.commonpath([abs_directory, abs_target])
                return prefix == str(abs_directory)

            def safe_extract(tar: tarfile.TarFile, path: Path) -> None:
                for member in tar.getmembers():
                    member_path = path / member.name
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted to extract outside target directory")
                    tar.extract(member, path)

            safe_extract(tar, dst_dir_path)
        return True
    except Exception as e:
        print(f"Extraction failed: {str(e)}")
        return False

URL_HUMANITY: str = "https://launchpad.net/humanity/0.4/0.4/+download/humanity_0.4.6.tar.gz"
URL_TANGO: str = "http://tango.freedesktop.org/releases/tango-icon-theme-0.8.90.tar.bz2"

def ensure_thirdparty_files(thirdparty_folder_path: Path) -> None:
    thirdparty_folder_path.mkdir(parents=True, exist_ok=True)
    for url in [URL_HUMANITY, URL_TANGO]:
        tarball_name: str = url.split("/")[-1]
        tarball_path: Path = thirdparty_folder_path / tarball_name
        extracted_folder_path = tarball_path.with_suffix("").with_suffix("")
        if not extracted_folder_path.exists():
            if not tarball_path.exists():
                print(f"Downloading {tarball_name}...")
                download_file(url, tarball_path)
            print(f"Extracting {tarball_name}...")
            extract_tarball(tarball_path, thirdparty_folder_path)

