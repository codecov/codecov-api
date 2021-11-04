from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files(
    "core", include_py_files=True, subdir="migrations"
) + collect_data_files("legacy_migrations", include_py_files=True, subdir="migrations")
