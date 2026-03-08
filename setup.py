#!/usr/bin/env python
import os
import sys
import configparser

from setuptools import setup


def get_version_attr_from_file(file_):
    version = "unknown"
    v_attr = "__version__"
    with open(file_) as f:
        content = f.read()
        version_idx = 0
        while version == "unknown":
            version_idx = content[version_idx:].find(v_attr)
            if version_idx == -1:
                break
            else:
                version_str = content[version_idx:].splitlines()[0]
                if "=" in version_str:
                    version = version_str.split("=")[-1].strip()
    return version


def generate_desktop_file():
    # Generate .dektop file
    ic_dir = os.path.join(os.path.dirname(__file__), "irrad_control")
    irrad_control_bin = os.path.join(os.path.dirname(sys.executable), "irrad_control")
    desktop_file = configparser.ConfigParser()
    desktop_file.optionxform = str  # Case sensitive
    desktop_file.read(os.path.join(ic_dir, "assets", "irrad_control.desktop"))
    version = get_version_attr_from_file(file_=os.path.join(ic_dir, "__init__.py"))
    desktop_file["Desktop Entry"]["Version"] = version
    desktop_file["Desktop Entry"]["Exec"] = irrad_control_bin
    desktop_file["Desktop Entry"]["Icon"] = os.path.join(ic_dir, "assets", "icon.png")
    desktop_file["Desktop Action control-window"]["Exec"] = f"{irrad_control_bin} --gui"
    desktop_file["Desktop Action monitor-window"]["Exec"] = f"{irrad_control_bin} --monitor"
    return desktop_file


def register_desktop_file(conf_parser):
    target_path = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    with open(os.path.join(target_path, "irrad_control.desktop"), "w") as dsktpfl:
        conf_parser.write(dsktpfl, space_around_delimiters=False)
    st = os.stat(os.path.join(os.path.expanduser("~"), ".local", "share", "applications", "irrad_control.desktop"))
    os.chmod(
        os.path.join(os.path.expanduser("~"), ".local", "share", "applications", "irrad_control.desktop"),
        st.st_mode | 0o111,
    )  # Make executable for everyone


def make_desktop_entry():
    register_desktop_file(conf_parser=generate_desktop_file())


# Call setup
setup()

# Create desktop file
make_desktop_entry()
