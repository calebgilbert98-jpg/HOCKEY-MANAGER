"""Functional-minimal QtWidgets stub for headless UI logic tests.

Widgets record their state so tests can assert on the rendered tree
(labels' text, combo items, table cells). Signals fire synchronously.
"""
from .QtCore import _Signal


class QWidget:
    def __init__(self, parent=None):
        self._parent = parent
        self._layout = None
        self._visible = True
        self._deleted = False
        self._object_name = ""
        self._stylesheet = ""
        self._min_height = 0

    def setLayout(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout

    def setVisible(self, v):
        self._visible = bool(v)

    def isVisible(self):
        return self._visible

    def deleteLater(self):
        self._deleted = True

    def setObjectName(self, n):
        self._object_name = n

    def objectName(self):
        return self._object_name

    def setStyleSheet(self, s):
        self._stylesheet = s

    def setMinimumHeight(self, h):
        self._min_height = h

    def setMinimumSize(self, w, h):
        self._min_size = (w, h)

    def width(self):
        return 640

    def height(self):
        return 320

    def update(self):
        pass

    def setFixedWidth(self, w):
        self._fixed_width = w

    def setFixedHeight(self, h):
        self._fixed_height = h

    def font(self):
        from .QtGui import QFont
        return QFont()

    def setFont(self, f):
        self._font = f

    def setProperty(self, name, value):
        if not hasattr(self, "_props"):
            self._props = {}
        self._props[name] = value
        return True

    def property(self, name):
        return getattr(self, "_props", {}).get(name)


class _BoxLayout:
    def __init__(self, parent=None):
        self._items = []
        if parent is not None and hasattr(parent, "setLayout"):
            parent.setLayout(self)

    def addWidget(self, w, *args):
        self._items.append(("widget", w))

    def addLayout(self, l, *args):
        self._items.append(("layout", l))

    def addStretch(self, *a):
        self._items.append(("stretch", None))

    def setContentsMargins(self, *a):
        pass

    def setSpacing(self, *a):
        pass

    def setAlignment(self, *a):
        pass

    def count(self):
        return len(self._items)

    def takeAt(self, i):
        kind, obj = self._items.pop(i)
        return _LayoutItem(obj)

    def widgets(self):
        return [o for k, o in self._items if k == "widget"]


class QVBoxLayout(_BoxLayout):
    pass


class QHBoxLayout(_BoxLayout):
    pass


class _LayoutItem:
    def __init__(self, obj):
        self._obj = obj

    def widget(self):
        return self._obj if isinstance(self._obj, QWidget) else None


class QLabel(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self._word_wrap = False

    def setText(self, t):
        self._text = str(t)

    def text(self):
        return self._text

    def setWordWrap(self, b):
        self._word_wrap = b

    def setAlignment(self, a):
        pass


class QComboBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._idx = -1
        self._blocked = False
        self.currentIndexChanged = _Signal()
        self.currentTextChanged = _Signal()

    def blockSignals(self, b):
        self._blocked = bool(b)
        return True

    def clear(self):
        self._items = []
        self._idx = -1

    def addItem(self, text, data=None):
        self._items.append((str(text), data))

    def count(self):
        return len(self._items)

    def setCurrentIndex(self, i):
        if i != self._idx:
            self._idx = i
            if not self._blocked:
                self.currentIndexChanged.emit(i)

    def currentIndex(self):
        return self._idx

    def currentData(self):
        if 0 <= self._idx < len(self._items):
            return self._items[self._idx][1]
        return None

    def currentText(self):
        if 0 <= self._idx < len(self._items):
            return self._items[self._idx][0]
        return ""

    def findData(self, d):
        for i, (_t, _d) in enumerate(self._items):
            if _d == d:
                return i
        return -1

    def findText(self, t):
        for i, (_t, _d) in enumerate(self._items):
            if _t == t:
                return i
        return -1

    def itemData(self, i):
        return self._items[i][1]

    def itemText(self, i):
        return self._items[i][0]


class QTableWidgetItem:
    def __init__(self, text=""):
        self._text = str(text)

    def text(self):
        return self._text

    def setData(self, *a):
        pass


class _Header:
    def setVisible(self, b):
        pass

    def setSectionResizeMode(self, *a):
        pass

    def setStretchLastSection(self, b):
        pass

    def __getattr__(self, name):
        # Tolerate any other header customization in headless tests.
        return lambda *a, **k: None


class QTableWidget(QWidget):
    NoEditTriggers = 0
    SelectRows = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = 0
        self._cols = 0
        self._labels = []
        self._cells = {}
        self.cellClicked = _Signal()
        self.itemSelectionChanged = _Signal()

    def resizeColumnsToContents(self):
        pass

    def setColumnCount(self, n):
        self._cols = n

    def setRowCount(self, n):
        self._rows = n

    def rowCount(self):
        return self._rows

    def columnCount(self):
        return self._cols

    def setHorizontalHeaderLabels(self, labels):
        self._labels = list(labels)

    def horizontalHeaderLabels(self):
        return self._labels

    def setEditTriggers(self, *a):
        pass

    def setSelectionBehavior(self, *a):
        pass

    def verticalHeader(self):
        return _Header()

    def horizontalHeader(self):
        return _Header()

    def setAlternatingRowColors(self, b):
        pass

    def setSortingEnabled(self, b):
        pass

    def setHorizontalHeaderItem(self, c, item):
        pass

    def setItem(self, r, c, item):
        self._cells[(r, c)] = item

    def item(self, r, c):
        return self._cells.get((r, c))

    def cell_text(self, r, c):
        it = self._cells.get((r, c))
        return it.text() if it is not None else ""


class QAbstractItemView:
    NoEditTriggers = 0
    SelectRows = 1


class QHeaderView:
    Stretch = 1
    ResizeToContents = 3


class QFrame(QWidget):
    HLine = 4
    NoFrame = 0
    Box = 1

    def setFrameShape(self, s):
        self._frame_shape = s


class QPushButton(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self.clicked = _Signal()
        self.toggled = _Signal()
        self._checkable = False
        self._checked = False
        self._enabled = True

    def setText(self, t):
        self._text = str(t)

    def text(self):
        return self._text

    def click(self):
        self.clicked.emit()

    def setEnabled(self, b):
        self._enabled = bool(b)

    def isEnabled(self):
        return self._enabled

    def setCheckable(self, b):
        self._checkable = bool(b)

    def isCheckable(self):
        return self._checkable

    def setChecked(self, b):
        b = bool(b)
        if b != self._checked:
            self._checked = b
            self.toggled.emit(b)

    def isChecked(self):
        return self._checked


class QTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = []
        self.currentChanged = _Signal()

    def addTab(self, widget, label):
        self._tabs.append((widget, label))
        return len(self._tabs) - 1

    def count(self):
        return len(self._tabs)

    def tabText(self, i):
        return self._tabs[i][1]


class QScrollArea(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None

    def setWidgetResizable(self, b):
        pass

    def setWidget(self, w):
        self._widget = w

    def widget(self):
        return self._widget


# Placeholders for names imported but never instantiated on tested paths.
class QLineEdit(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self.textChanged = _Signal()

    def setPlaceholderText(self, t):
        self._placeholder = str(t)

    def setText(self, t):
        self._text = str(t)
        self.textChanged.emit(self._text)

    def text(self):
        return self._text


class QListWidget(QWidget):
    pass


class QListWidgetItem:
    def __init__(self, *a):
        pass


class QSplitter(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._widgets = []

    def addWidget(self, w):
        self._widgets.append(w)

    def setStretchFactor(self, i, f):
        pass


class QGroupBox(QWidget):
    pass


class QTextEdit(QWidget):
    pass


class QStackedWidget(QWidget):
    pass


class QMessageBox:
    @staticmethod
    def information(*a):
        pass

    @staticmethod
    def warning(*a):
        pass


class QDialog(QWidget):
    Accepted = 1
    Rejected = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = self.Rejected
        self.finished = _Signal()

    def setWindowTitle(self, t):
        self._title = str(t)

    def setMinimumWidth(self, w):
        pass

    def setMinimumHeight(self, h):
        pass

    def accept(self):
        self._result = self.Accepted
        self.finished.emit(self._result)

    def reject(self):
        self._result = self.Rejected
        self.finished.emit(self._result)

    def exec(self):
        return self._result

    def result(self):
        return self._result


class QSpinBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.valueChanged = _Signal()

    def setValue(self, v):
        self._value = int(v)

    def value(self):
        return self._value

    def setRange(self, lo, hi):
        pass


class QDoubleSpinBox(QSpinBox):
    def setValue(self, v):
        self._value = float(v)


class QSlider(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._value = 0
        self.valueChanged = _Signal()

    def setValue(self, v):
        self._value = int(v)
        self.valueChanged.emit(self._value)

    def value(self):
        return self._value

    def setRange(self, lo, hi):
        pass


class QCheckBox(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self._checked = False
        self.stateChanged = _Signal()

    def setChecked(self, b):
        self._checked = bool(b)
        self.stateChanged.emit(2 if b else 0)

    def isChecked(self):
        return self._checked


class QButtonGroup:
    def __init__(self, parent=None):
        self._parent = parent
        self._buttons = []
        self._exclusive = False

    def setExclusive(self, b):
        self._exclusive = bool(b)

    def addButton(self, b):
        self._buttons.append(b)

    def buttons(self):
        return list(self._buttons)


class QGridLayout(_BoxLayout):
    def addWidget(self, w, *args):
        super().addWidget(w)


class QSizePolicy:
    Expanding = 1


class QMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions = []

    def addAction(self, text):
        self._actions.append(text)
        return text

    def exec(self, *a):
        return None
