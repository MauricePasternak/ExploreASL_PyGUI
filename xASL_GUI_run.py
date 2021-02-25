from src.xASL_GUI_Startup import startup
import platform
import os

# TODO Discuss with the group about the GUI deprecating compatibility with ExploreASL versions <1.5.0

if __name__ == '__main__':
    if platform.system() == "Darwin":
        release, _, machine_info = platform.mac_ver()
        try:
            release_as_float = float(".".join(release.split(".")[:2]))
            if release_as_float >= 10.16:
                os.environ['QT_MAC_WANTS_LAYER'] = '1'
        except IndexError:
            print(f"MacOS Warning in {__name__}. The version of this Mac was attempted to be found but could not be "
                  f"properly parsed. This is the value that was found: {release}.\n"
                  f"If the GUI freezes after this message, you need to edit your .zprofile file: set the variable "
                  f"QT_MAC_WANTS_LAYER equal to 1 (no spaces), export the variable, and restart your computer.")

    startup()
