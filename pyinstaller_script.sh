#!/bin/bash
EXPLOREASLROOT="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
MEDIA="${EXPLOREASLROOT}/media"


echo "Using Pyinstaller Version: $(pyinstaller -v)"

pyinstaller --noconfirm --onedir --console --icon "/home/mpasternak/PycharmProjects/ExploreASL_GUI/media/ExploreASL_logo.ico" --name "ExploreASL_GUI_Linux" --add-data "/home/mpasternak/PycharmProjects/ExploreASL_GUI/media:media/" --add-data "/home/mpasternak/PycharmProjects/ExploreASL_GUI/JSON_LOGIC:JSON_LOGIC/" --add-data "/home/mpasternak/PycharmProjects/ExploreASL_GUI/External:External/" --paths "/home/mpasternak/PycharmProjects/ExploreASL_GUI/venv/lib/python3.8/site-packages" --additional-hooks-dir "/home/mpasternak/PycharmProjects/ExploreASL_GUI/hooks"  "/home/mpasternak/PycharmProjects/ExploreASL_GUI/xASL_GUI_run.py"
