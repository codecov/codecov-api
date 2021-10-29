import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    get_package_paths,
)

package_path = get_package_paths("text_unidecode")
data_bin_path = os.path.join(package_path[1], "data.bin")
datas = (
    collect_data_files("codecov_auth", include_py_files=True, subdir="migrations")
    + collect_data_files("text_unidecode")
    + [(data_bin_path, "text_unidecode")]
)
