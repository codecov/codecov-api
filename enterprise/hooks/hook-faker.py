import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, get_package_paths

hiddenimports = collect_submodules('faker.providers')
datas = (collect_data_files('text_unidecode') +
         collect_data_files('faker.providers', include_py_files=True))

package_path = get_package_paths("text_unidecode")
data_bin_path = os.path.join(package_path[1], "data.bin")

if os.path.exists(data_bin_path):
    datas += (data_bin_path, 'text_unidecode')
