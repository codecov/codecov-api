from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('faker.providers')
datas = (collect_data_files('text_unidecode') +
         collect_data_files('faker.providers', include_py_files=True))