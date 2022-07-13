import os
from glob import glob
from modulefinder import ModuleFinder
from pathlib import Path

import celery

finder = ModuleFinder()

so_extension = ".cpython-39-x86_64-linux-gnu.so"


def get_relevant_paths(path):
    p = Path(path)
    init_files = list(p.glob("**/__init__.py"))
    extensions = list()
    for filepath in init_files:
        dir_path = os.path.dirname(filepath)
        extensions.append("{}/{}".format(dir_path, "*.py"))
        extensions.append("{}/**/{}".format(dir_path, "*.py"))
    return extensions


def get_relevant_dirs(path):
    extensions = list()
    for it in os.scandir(path):
        if it.is_dir() and "tests" not in it.path:
            extensions.append(it.path)
            extensions + get_relevant_dirs(it)
    return extensions


def find_imported_modules(filename):
    try:
        finder.run_script(filename)
        for name, mod in finder.modules.items():
            yield name
    except AttributeError:
        pass


def generate_files_to_be_cythonized():
    files_to_exclude = []
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


def main():
    hidden_imports = {
        "billing.migrations",
        "celery_config",
        "codecov.graphs",
        "core.migrations",
        "reports.migrations",
        "codecov_auth.migrations",
        "compare.migrations",
        "corsheaders",
        "corsheaders.apps",
        "corsheaders.middleware",
        "dataclasses",
        "hooks",
        "profiling.migrations",
        "pythonjsonlogger",
        "pythonjsonlogger.jsonlogger",
        "rest_framework",
        "rest_framework.apps",
        "rest_framework.metadata",
        "rest_framework.mixins",
        "rest_framework.filters",
        "rest_framework.status",
        "utils",
        "utils.config",
        "utils.encryption",
        "utils.logging_configuration",
        "ariadne_django.apps",
        "whitenoise",
        "whitenoise.middleware",
        "graphql_api",
        "legacy_migrations",
        "legacy_migrations.migrations",
        "shared.celery_config",
        "kombu.transport.pyamqp",
        "gunicorn",
        "gunicorn.glogging",
        "gunicorn.workers.sync",
        "gunicorn.instrument",
        "gunicorn.instrument.statsd",
    }

    base = celery.__file__.rsplit("/", 1)[0]
    hidden_imports.update(
        [
            "celery" + file.replace(base, "").replace(".py", "").replace("/", ".")
            for file in (glob(base + "/*.py") + glob(base + "/**/*.py"))
        ]
    )

    module_dirs = get_relevant_dirs(".")
    hidden_imports.update([x.replace("/", ".") for x in module_dirs])
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
    args.extend([f"--runtime-hook=/pyinstaller/pyi_rth_django.py"])
    args.extend([f"--additional-hooks-dir /hooks"])

    print(" ".join(args))


if __name__ == "__main__":
    main()
