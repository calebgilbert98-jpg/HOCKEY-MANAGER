"""Minimal QtCore stub: Qt enum namespace + QTimer placeholder."""


class QPoint:
    def __init__(self, x=0, y=0):
        self._x = int(x)
        self._y = int(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class Qt:
    NoBrush = 0
    Horizontal = 1
    Vertical = 2
    AlignLeft = 0x01
    AlignRight = 0x82
    AlignHCenter = 0x04
    AlignTop = 0x20
    AlignBottom = 0x40
    AlignVCenter = 0x80
    AlignCenter = 0x84
    UserRole = 0x0100
    DisplayRole = 0x00


class QTimer:
    def __init__(self, parent=None):
        self._parent = parent
        self.timeout = _Signal()

    def setSingleShot(self, b):
        pass

    def setInterval(self, ms):
        self._interval = ms

    def interval(self):
        return getattr(self, "_interval", 0)

    def start(self, ms=0):
        self._active = True

    def stop(self):
        self._active = False

    def isActive(self):
        return getattr(self, "_active", False)

    @staticmethod
    def singleShot(ms, cb):
        pass


class Signal:
    """Descriptor-style signal factory (class-level use)."""

    def __init__(self, *types):
        self._types = types
        self._name = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        key = f"_sig_{self._name}"
        sig = obj.__dict__.get(key)
        if sig is None:
            sig = _Signal()
            obj.__dict__[key] = sig
        return sig


class _Signal:
    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        self._cbs.append(cb)

    def emit(self, *a):
        for cb in list(self._cbs):
            cb(*a)
