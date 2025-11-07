import os
import sys
import configparser


def generate_desktop_file(version):
    # Generate .dektop file
    abs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    irrad_control_bin = os.path.join(os.path.dirname(sys.executable), "irrad_control")
    desktop_file = configparser.ConfigParser()
    desktop_file.optionxform = str  # Case sensitive
    desktop_file.read(os.path.join(abs_dir, "assets", "irrad_control.desktop"))
    desktop_file["Desktop Entry"]["Version"] = version
    desktop_file["Desktop Entry"]["Exec"] = irrad_control_bin
    desktop_file["Desktop Entry"]["Icon"] = os.path.join(abs_dir, "assets", "icon.png")
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


def make_desktop_entry(version):
    register_desktop_file(conf_parser=generate_desktop_file(version=version))
