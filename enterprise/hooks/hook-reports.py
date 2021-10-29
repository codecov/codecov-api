from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("reports", include_py_files=True, subdir="migrations")
