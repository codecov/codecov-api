from PyInstaller.utils.hooks import collect_submodules, collect_data_files, get_package_paths
import os

package_path = get_package_paths("text_unidecode")
data_bin_path = os.path.join(package_path[1], "data.bin")
datas = (collect_data_files('codecov_auth', include_py_files=True, subdir="migrations") +
         collect_data_files('text_unidecode') +
         (data_bin_path, 'text_unidecode'))



