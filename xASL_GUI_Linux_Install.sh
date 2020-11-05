#!/bin/bash
EXPLOREASLROOT="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
echo "Installing dependencies..."
sudo apt-get install -y python3.8 libpq-dev python3-dev python3-pip python3-venv python3-wheel pkg-config libfreetype6-dev >/dev/null 2>&1 || exit 1

echo "Setting up virtual environment..."
mkdir "${EXPLOREASLROOT}/venv" -p
python3.8 -m venv "${EXPLOREASLROOT}/venv" || exit 1

echo "Activating virtual environment..."
source "${EXPLOREASLROOT}/venv/bin/activate" && pip3 install wheel && pip3 install -r "${EXPLOREASLROOT}/requirements.txt" || exit 1

echo "Generating bash script launcher..."
cat > "${EXPLOREASLROOT}/xASL_GUI_run.sh" << EOM
#!/bin/bash
source ${EXPLOREASLROOT}/venv/bin/activate
cd ${EXPLOREASLROOT}
python3.8 ${EXPLOREASLROOT}/xASL_GUI_run.py
EOM
chmod +x "${EXPLOREASLROOT}/xASL_GUI_run.sh"

echo "Generating .desktop link"
cat > "${EXPLOREASLROOT}/ExploreASL_GUI.desktop" << EOM
[Desktop Entry]
Version=0.2.5
Name=ExploreASL_GUI
Comment=ExploreASL_GUI is an accompanying graphical user interface for ExploreASL workflows
Exec=${EXPLOREASLROOT}/xASL_GUI_run.sh
Icon=${EXPLOREASLROOT}/media/ExploreASL_logo.png
Terminal=false
Type=Application
Categories=Utility;Development;
EOM
sudo mv "${EXPLOREASLROOT}/ExploreASL_GUI.desktop" /usr/share/applications/ExploreASL_GUI.desktop || exit 1
echo "ExploreASL_GUI has been installed."
