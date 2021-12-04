from PyQt5 import QtWidgets, QtGui, QtCore
from collections.abc import Iterable


class GridContainer(QtWidgets.QGroupBox):
    """Container widget for grouping widgets together in a grid layout."""

    def __init__(self, name, x_space=20, y_space=10, parent=None):
        super(GridContainer, self).__init__(parent)

        # Store name of container
        self.name = name

        # Contain all widgets
        self.widgets = {}

        # Set name
        self.setTitle(self.name)

        # Make grid layout
        self.grid = QtWidgets.QGridLayout()
        self.grid.setVerticalSpacing(y_space)
        self.grid.setHorizontalSpacing(x_space)
        self.setLayout(self.grid)

        self._allowed_items = [QtWidgets.QWidget, QtWidgets.QLayout]

    def add_allowed_item(self, item):

        if self._valid_item(item):
            pass
        else:
            self._allowed_items.append(item)

    def _valid_item(self, item):
        """Check whether an item ca be added to the grid; only QWidgets and QLayouts default"""

        def _check(x): return any(isinstance(x, allowed) for allowed in self._allowed_items)

        return all(_check(x) for x in item) if isinstance(item, Iterable) else _check(item)

    def _prepare_item(self, item):
        """Generator which yields all items contained in *item*"""

        # Make individual items iterable so we can yield them
        if not isinstance(item, Iterable):
            item = [item]

        for itm in item:
            yield itm

    def add_layout(self, layout):
        self.add_item(layout)

    def add_widget(self, widget):
        self.add_item(widget)

    def add_item(self, item):
        """Adds *widget* to container where *widget* can be any QWidget or an iterable of QWidgets."""

        row_count = self.grid.rowCount()

        if not self._valid_item(item):
            raise TypeError("Only QWidgets and QLayouts can be added to layout!")
        else:
            # Loop over all items and add to grid
            for i, itm in enumerate(self._prepare_item(item)):
                self._add_to_grid(itm, row_count, i)

    def _add_to_grid(self, item, row, col):

        if isinstance(item, QtWidgets.QLayout):
            self.grid.addLayout(item, row, col)
        else:
            self.grid.addWidget(item, row, col)

    def remove_widget(self, widget):
        self.remove_item(widget)

    def remove_layout(self, layout):
        self.remove_item(layout)

    def remove_item(self, item):

        """Removes *item* from container where *item* can be any QWidget or an iterable of QWidgets or a QLayout."""
        if not self._valid_item(item):
            raise TypeError("Only QWidgets and QLayouts can be removed!")
        else:
            for itm in self._prepare_item(item):
                self._remove_from_grid(itm)

    def _remove_from_grid(self, item):

        # Loop over grid and find item to remove
        for i in range(self.grid.count()):

            # Get item in grid at index i
            grid_item = self.grid.itemAt(i)

            # If grid_item is None, continue
            if isinstance(grid_item, type(None)):
                continue

            # We're trying to remove a QLayout from the grid
            elif isinstance(item, QtWidgets.QLayout):

                if grid_item.layout() == item:
                    # Remove entire layout
                    self._delete_layout_content(grid_item.layout())
                    self.grid.removeItem(grid_item)

            # We're trying to remove a QWidget from the grid
            elif isinstance(item, QtWidgets.QWidget):
                if grid_item.widget() == item:
                    self.grid.removeWidget(item)
                    item.deleteLater()

    def _delete_layout_content(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
                else:
                    self._delete_layout_content(item.layout())

    def set_read_only(self, read_only=True, omit=None):
        """Sets all widgets to read only. If they don't have a readOnly-method, they're disabled"""

        omit = omit if isinstance(omit, Iterable) else [omit]

        # Loop over entire grid
        for idx in range(self.grid.count()):
            # Get item at row, col
            item = self.grid.itemAt(idx)

            # Item is QSpacerItem or 0 (no item)
            if isinstance(item, QtWidgets.QSpacerItem) or item == 0:
                pass

            # Check whether its QLayoutItem or QWidgetItem
            elif isinstance(item, QtWidgets.QWidgetItem):
                # Extract widget and set read_only
                _widget = item.widget()
                if type(_widget) not in omit:
                    self.set_widget_read_only(widget=_widget, read_only=read_only)

            elif isinstance(item, QtWidgets.QLayoutItem):
                # Loop over layout and disable widgets
                _layout = item.layout()
                for i in reversed(range(_layout.count())):
                    # Check whether its a QWidgetItem and not a Spacer etc
                    if isinstance(_layout.itemAt(i), QtWidgets.QWidgetItem):
                        _widget = _layout.itemAt(i).widget()
                        if type(_widget) not in omit:
                            self.set_widget_read_only(widget=_widget, read_only=read_only)
            else:
                raise TypeError('Item must be either QWidgetItem or QLayoutItem. Found {}'.format(type(item)))

    @staticmethod
    def set_widget_read_only(widget, read_only=True):
        """Set widget to read only. Use widgets setReadOnly-method else just disable"""

        # We don't have to do anything with labels
        if not isinstance(widget, QtWidgets.QLabel):
            # Check if we have readOnly method
            if hasattr(widget, 'setReadOnly'):
                widget.setReadOnly(read_only)
            # If not, just disable
            else:
                widget.setEnabled(not read_only)

        # Set color palette to indicate status
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, QtCore.Qt.gray if read_only else QtCore.Qt.white)
        palette.setColor(QtGui.QPalette.Text, QtCore.Qt.darkGray if read_only else QtCore.Qt.black)
        widget.setPalette(palette)


class NoBackgroundScrollArea(QtWidgets.QScrollArea):
    """Scroll area which conserves the background color of its content and is frameless"""

    def __init__(self, parent=None):
        super(NoBackgroundScrollArea, self).__init__(parent)
        # Set resizeable
        self.setWidgetResizable(True)
        # Set scroll bars
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        # Palette and background role
        self._p, self._b, = self.palette(), self.backgroundRole()
        self.setAutoFillBackground(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

    def setWidget(self, QWidget):
        self._p.setColor(self._b, QWidget.palette().color(QtGui.QPalette.AlternateBase))
        self.setPalette(self._p)
        super(NoBackgroundScrollArea, self).setWidget(QWidget)
