#!/bin/sh

set -e
#set -x

find . -wholename "**/tests**" -delete

python /pyinstaller/generate_pyinstaller_args.py > /pyinstaller/installer_args.txt

python setup.py build_ext -b .

find . -wholename "**/__pycache__**" -delete

rm -rf build

#echo $(find .)

cat /pyinstaller/installer_args.txt
