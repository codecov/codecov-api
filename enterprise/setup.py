import os
from glob import glob
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup


def get_relevant_paths(path):
    p = Path(path)
    init_files = list(p.glob("**/__init__.py"))
    extensions = list()
    for filepath in init_files:
        dir_path = os.path.dirname(filepath)
        if "migrations" not in dir_path:
            extensions.append("{}/{}".format(dir_path, "*.py"))
    return extensions


def generate_files_to_be_cythonized():
    files_to_exclude = [
        "codecov_auth/migrations/*.py",
        "reports/migrations/*.py",
        "core/migrations/*.py",
    ]
    locations = get_relevant_paths(".")
    files = []
    for loc in locations:
        files.extend(
            [
                fn
                for fn in glob(loc, recursive=True)
                if not os.path.basename(fn).endswith("__init__.py")
            ]
        )
    return [f for f in files if f not in files_to_exclude]


files = generate_files_to_be_cythonized()
extensions = [
    Extension(name=f.replace(".py", "").replace("/", "."), sources=[f]) for f in files
]

setup(ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}))

for file in files:
    os.remove(file)
    os.remove(file.replace(".py", ".c"))
