from glob import glob
import celery
from modulefinder import ModuleFinder
import os
from pathlib import Path

finder = ModuleFinder()

so_extension = ".cpython-37m-x86_64-linux-gnu.so"


def get_relevant_paths(path):
    p = Path(path)
    init_files = list(p.glob('**/__init__.py'))
    extensions = list()
    for filepath in init_files:
        dir_path = os.path.dirname(filepath)
        if "migrations" not in dir_path:
            extensions.append("{}/{}".format(dir_path, "*.py"))
    return extensions

def find_imported_modules(filename):
    finder.run_script(filename)
    for name, mod in finder.modules.items():
        yield name


def generate_files_to_be_cythonized():
    files_to_exclude = [
        "codecov_auth/migrations/*.py",
        "core/migrations/*.py"
    ]
    locations = get_relevant_paths('.')
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


def main():
    hidden_imports = set(
        []
    )

    base = celery.__file__.rsplit("/", 1)[0]
    hidden_imports.update(
        [
            "celery" + file.replace(base, "").replace(".py",
                                                      "").replace("/", ".")
            for file in (glob(base + "/*.py") + glob(base + "/**/*.py"))
        ]
    )

    cythonized_files = generate_files_to_be_cythonized()
    hidden_imports.update(
        [x.replace(".py", "").replace("/", ".") for x in cythonized_files]
    )

    for f in cythonized_files:
        a = list(find_imported_modules(f))
        hidden_imports.update(a)

    args = []
    args.extend(
        [
            f'-r {x.replace(".py", so_extension)},dll,{x.replace("/", ".").replace(".py", so_extension)}'
            for x in cythonized_files
        ]
    )
    args.extend(
        [
            f"--hiddenimport {x}"
            for x in sorted(hidden_imports, key=lambda x: (len(x.split(".")), x))
        ]
    )

    print(" ".join(args))


if __name__ == "__main__":
    main()
