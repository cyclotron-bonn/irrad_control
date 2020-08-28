import subprocess


def fill_combobox_items(cbx, fill_dict):
    """Helper function to fill items of a combo box from dictionary"""

    default_idx = 0
    _all = fill_dict if 'all' not in fill_dict else fill_dict['all']

    # Clear initially
    cbx.clear()

    # Add entire Info to tooltip e.g. date of measured constant, sigma, etc.
    for i, k in enumerate(sorted(_all.keys())):
        if 'hv_sem' in _all[k]:
            cbx.insertItem(i, '{} ({}, HV: {})'.format(_all[k]['nominal'], k, _all[k]['hv_sem']))
        elif 'nominal' in _all[k]:
            cbx.insertItem(i, '{} ({})'.format(_all[k]['nominal'], k))
        else:
            cbx.insertItem(i, k)
        tool_tip = ''
        for l in _all[k]:
            tool_tip += '{}: {}\n'.format(l, _all[k][l])
        cbx.model().item(i).setToolTip(tool_tip)

        default_idx = default_idx if 'default' not in fill_dict else default_idx if k != fill_dict['default'] else i

    cbx.setCurrentIndex(default_idx)


def get_host_ip():
    """Returns the host IP address on UNIX systems. If not UNIX, returns None"""

    try:
        host_ip = subprocess.check_output(['hostname', '-I'])
    except (OSError, subprocess.CalledProcessError):
        host_ip = None

    return host_ip
