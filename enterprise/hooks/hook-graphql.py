from PyInstaller.utils.hooks import collect_submodules, collect_data_files

datas = collect_data_files("graphql_api", include_py_files=True, subdir="types")
