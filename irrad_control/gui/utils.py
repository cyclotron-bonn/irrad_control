import subprocess
from PyQt5 import QtWidgets


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

    # Clear initially
    cbx.clear()

    # Add entire Info to tooltip e.g. date of measured constant, sigma, etc.
    for i, k in enumerate(fill_dict.keys()):
        tool_tip = ""

        if isinstance(fill_dict[k], dict):
            if "nominal" in fill_dict[k]:
                cbx.insertItem(
                    i,
                    f"{fill_dict[k]['nominal']}"
                    + "\u00b1"
                    + f"{fill_dict[k]['sigma']}"
                    + f" ({fill_dict[k]['energy']} MeV)",
                )

            else:
                cbx.insertItem(i, k)

            for itm in fill_dict[k]:
                tool_tip += "{}: {}\n".format(itm, fill_dict[k][itm])
        else:
            cbx.insertItem(i, k)
            tool_tip += "{}: {}\n".format(k, fill_dict[k])
        cbx.model().item(i).setToolTip(tool_tip)


def get_host_ip():
    """Returns the host IP address on UNIX systems. If not UNIX, returns None"""

    try:
        host_ip = str(subprocess.check_output(["hostname", "-I"]))
    except (OSError, subprocess.CalledProcessError):
        host_ip = None

    return host_ip


def check_unique_input(edits, ignore=""):
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
        for j in range(i + 1, n_edits):
            name_j = edits[j].text() or edits[j].placeholderText()
            if name_i == name_j:
                return False
    return True


def remove_widget(widget, layout, replace_with=None):
    """
    Removes *widget* from *layout* by looping over layout contents. Optionally replaces *widget* with replace_with*

    Parameters
    ----------
    widget:
        QtWidget
    layout:
        QLayout
    replace_with:
        QtWidget
    """

    if not isinstance(widget, QtWidgets.QWidget):
        raise TypeError("*widget* must be QWidget, is {}".format(type(widget)))

    if not isinstance(layout, QtWidgets.QLayout):
        raise TypeError("*layout* must be QLayout, is {}".format(type(layout)))

    if replace_with:
        if not isinstance(replace_with, QtWidgets.QWidget):
            raise TypeError("*replace_with* must be QWidget, is {}".format(type(replace_with)))

    # Loop over layout count
    for i in reversed(range(layout.count())):
        current_item = layout.takeAt(i)

        # We found the widget to remove
        if current_item.widget() == widget:
            # Remove
            layout.removeWidget(widget)
            current_item.widget().deleteLater()

            # Replace
            if replace_with:
                layout.insertWidget(i, replace_with)

            break
    else:
        raise AttributeError("*layout* does not contain *widget*")
