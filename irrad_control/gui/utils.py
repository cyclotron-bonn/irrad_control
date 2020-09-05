import subprocess


def fill_combobox_items(cbx, fill_dict):
    """
    Helper function to fill items of a combo box from dictionary

    Parameters
    ----------
    cbx: QComboBox
        Combobox to fill
    fill_dict: dict
        dictionary which will fill combobox with keys
    """

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


def check_unique_input(edits, ignore=''):
    """
    Function which checks whether or not a selection of PyQt5.QLineEdits has only unique inputs

    Parameters
    ----------
    edits: iterable
        iterable of QLineEdits
    ignore: str
        string which is allowed to appear multiple times

    Returns
    -------
    bool: whether only unique input is in edits
    """
    # Number of edits to check
    n_edits = len(edits)

    # Loop over edits and compare input
    for i in range(n_edits):
        name_i = edits[i].text() or edits[i].placeholderText()
        if name_i == ignore:
            continue
        for j in range(i+1, n_edits):
            name_j = edits[j].text() or edits[j].placeholderText()
            if name_i == name_j:
                return False
    return True
