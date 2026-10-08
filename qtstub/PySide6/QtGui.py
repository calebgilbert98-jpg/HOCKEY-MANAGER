"""Minimal QtGui stub for headless UI logic tests."""

from .QtCore import _Signal, QPoint  # noqa: F401  (re-export)


class QColor:
    def __init__(self, *args):
        self._args = args

    def name(self):
        return str(self._args[0]) if self._args else ""


class QFont:
    def __init__(self, *args):
        self._args = args
        self._point_size = 10
        self._bold = False

    def setPointSize(self, n):
        self._point_size = int(n)

    def setBold(self, b):
        self._bold = bool(b)

    def pointSize(self):
        return self._point_size

    def bold(self):
        return self._bold


class QIntValidator:
    def __init__(self, *args):
        self._args = args


class QPen:
    def __init__(self, *args):
        self._args = args

    def setWidth(self, w):
        pass


class QBrush:
    def __init__(self, *args):
        self._args = args


class QPolygon:
    def __init__(self, points=()):
        self._points = list(points)


class QAction:
    def __init__(self, text="", parent=None):
        self._text = str(text)
        self._parent = parent
        self.triggered = _Signal()

    def setText(self, t):
        self._text = str(t)


class QPainter:
    """Records paint ops so tests can assert markers were drawn."""

    Antialiasing = 1

    def __init__(self, widget=None):
        self._widget = widget
        self.ops = []

    def setRenderHint(self, *a):
        pass

    def setPen(self, pen):
        self.ops.append(("pen", pen))

    def setBrush(self, brush):
        self.ops.append(("brush", brush))

    def fillRect(self, *a):
        self.ops.append(("fillRect", a))

    def drawRoundedRect(self, *a):
        self.ops.append(("roundedRect", a))

    def drawRect(self, *a):
        self.ops.append(("rect", a))

    def drawLine(self, *a):
        self.ops.append(("line", a))

    def drawEllipse(self, *a):
        self.ops.append(("ellipse", a))

    def drawPolygon(self, poly):
        self.ops.append(("polygon", poly))

    def end(self):
        self.ops.append(("end",))
