from PyInstaller.utils.hooks import collect_submodules, collect_data_files

datas = collect_data_files("reports", include_py_files=True, subdir="migrations")
