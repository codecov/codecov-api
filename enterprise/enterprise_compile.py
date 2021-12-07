# Something more robust -- inspired by: https://bucharjan.cz/blog/using-cython-to-protect-a-python-codebase.html
import os.path
import shutil
from pathlib import Path

from Cython.Build import cythonize
from Cython.Distutils import build_ext
from setuptools import setup
from setuptools.extension import Extension


class MyBuildExt(build_ext):
    def run(self):
        build_ext.run(self)

        build_dir = Path(self.build_lib)
        root_dir = Path(__file__).parent

        target_dir = build_dir if not self.inplace else root_dir

        # To get the imports right, we need all the __init__.py's.
        # Ideally we'll do this using some kind of recursive search so
        # we don't have to maintain a list.
        p = Path(".")
        init_files = list(p.glob("**/__init__.py"))

        for init_file in init_files:
            if "tests" not in os.path.dirname(
                init_file
            ) and "migrations" not in os.path.dirname(init_file):
                self.copy_file(init_file, root_dir, target_dir)

    def copy_file(self, path, source_dir, destination_dir):
        if not (source_dir / path).exists():
            return

        shutil.copyfile(str(source_dir / path), str(destination_dir / path))


def get_extensions(path):
    p = Path(path)
    init_files = list(p.glob("**/__init__.py"))
    extensions = list()
    for filepath in init_files:
        dir_path = os.path.dirname(filepath)
        if "tests" not in dir_path and "migrations" not in dir_path:
            dot_name = "{}.*".format(str.replace(dir_path, "/", "."))
            new_ext = Extension(dot_name, ["{}/*.py".format(dir_path)])
            extensions.append(new_ext)
    # return an array of extensions
    print(extensions)
    return extensions


setup(
    name="mypkg",
    ext_modules=cythonize(
        get_extensions("."),
        build_dir="build",
        compiler_directives=dict(always_allow_keywords=True),
    ),
    cmdclass=dict(build_ext=MyBuildExt),
    packages=[],
)
