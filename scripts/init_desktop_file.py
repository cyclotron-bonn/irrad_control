import os
import sys
import configparser


def generate_desktop_file(version):
    # Generate .dektop file
    abs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    print(abs_dir)
    desktop_file = configparser.ConfigParser()
    desktop_file.optionxform = str  # Case sensitive
    desktop_file.read(os.path.join(abs_dir, 'assets', 'irrad_control.desktop'))
    desktop_file['Desktop Entry']['Version'] = version
    desktop_file['Desktop Entry']['Exec'] = ' '.join([sys.executable, os.path.join(abs_dir, 'irrad_control', 'main.py')])
    desktop_file['Desktop Entry']['Icon'] = os.path.join(abs_dir, 'assets', 'icon.png')
    desktop_file['Desktop Action control-window']['Exec'] = ' '.join([sys.executable, os.path.join(abs_dir, 'irrad_control', 'main.py'), '--gui'])
    desktop_file['Desktop Action monitor-window']['Exec'] = ' '.join([sys.executable, os.path.join(abs_dir, 'irrad_control', 'main.py'), '--monitor'])


def register_desktop_file(conf_parser):
    with open(os.path.join(os.path.expanduser('~'), '.local', 'share', 'applications', 'irrad_control.desktop'), 'w') as dsktpfl:
        conf_parser.write(dsktpfl, space_around_delimiters=False)
    st = os.stat(os.path.join(os.path.expanduser('~'), '.local', 'share', 'applications', 'irrad_control.desktop'))
    os.chmod(os.path.join(os.path.expanduser('~'), '.local', 'share', 'applications', 'irrad_control.desktop'), st.st_mode | 0o111)  # Make executable for everyone


def make_desktop_entry(version):
    register_desktop_file(conf_parser=generate_desktop_file(version=version))
