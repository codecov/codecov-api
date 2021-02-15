from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# This collects all dynamically imported scrapy modules and data files.
datas = collect_data_files('codecov_auth', include_py_files=True, subdir="migrations")