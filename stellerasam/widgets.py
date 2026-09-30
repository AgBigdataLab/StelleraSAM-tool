from PyQt5 import QtCore, QtWidgets


class SectionPanel(QtWidgets.QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet(
            """
            QFrame#sectionPanel {
                background:#f8faf9;
                border:1px solid #d4ddda;
                border-radius:6px;
            }
            QLabel#sectionHeader {
                background:#edf3f1;
                color:#273a3b;
                border:0px;
                border-bottom:1px solid #d4ddda;
                border-top-left-radius:5px;
                border-top-right-radius:5px;
                padding:7px 10px;
                font-size:14px;
                font-weight:700;
            }
            QWidget#sectionBody {
                background:transparent;
                border:0px;
            }
            """
        )

        panel_layout = QtWidgets.QVBoxLayout(self)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self._title_label = QtWidgets.QLabel(title, self)
        self._title_label.setObjectName("sectionHeader")
        self._title_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        panel_layout.addWidget(self._title_label)

        self._body = QtWidgets.QWidget(self)
        self._body.setObjectName("sectionBody")
        self._body_layout = QtWidgets.QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(10, 10, 10, 10)
        self._body_layout.setSpacing(8)
        panel_layout.addWidget(self._body, 1)

    def setTitle(self, title):
        self._title_label.setText(title)

    def title(self):
        return self._title_label.text()

    def content_layout(self):
        return self._body_layout


class CategoryRowWidget(QtWidgets.QWidget):
    rowClicked = QtCore.pyqtSignal()
    colorClicked = QtCore.pyqtSignal()

    def __init__(self, name, color_hex, shortcut_text="", parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setMinimumHeight(34)
        self._selected = False
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 2, 0, 2)
        outer_layout.setSpacing(0)

        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName("categoryCard")
        self.card.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer_layout.addWidget(self.card)

        layout = QtWidgets.QHBoxLayout(self.card)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(9)

        self.color_button = QtWidgets.QToolButton(self.card)
        self.color_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.color_button.setFixedSize(16, 16)
        self.color_button.setToolTip("")
        self.color_button.clicked.connect(self.colorClicked.emit)

        self.label = QtWidgets.QLabel(name, self.card)
        self.label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.label.setStyleSheet(
            "background:transparent;border:none;padding:0;margin:0;font-size:12px;"
        )
        self.label.setToolTip("")

        self.shortcut_label = QtWidgets.QLabel(shortcut_text, self.card)
        self.shortcut_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.shortcut_label.setAlignment(QtCore.Qt.AlignCenter)
        self.shortcut_label.setFixedWidth(18)
        self.shortcut_label.setStyleSheet(
            "background:transparent;border:none;padding:0;margin:0;font-size:11px;color:#6f7d7f;"
        )
        self.shortcut_label.setVisible(bool(shortcut_text))

        layout.addWidget(self.color_button, 0, QtCore.Qt.AlignVCenter)
        layout.addWidget(self.label, 1, QtCore.Qt.AlignVCenter)
        layout.addWidget(self.shortcut_label, 0, QtCore.Qt.AlignVCenter)
        self.set_color(color_hex)
        self.set_selected(False)

    def set_color(self, color_hex):
        self.color_button.setStyleSheet(
            f"""
            QToolButton {{
                background:{color_hex};
                border:1px solid #657476;
                border-radius:3px;
                padding:0;
            }}
            QToolButton:hover {{
                border:1px solid #233638;
            }}
            """
        )

    def set_selected(self, selected):
        self._selected = bool(selected)
        if selected:
            self.card.setStyleSheet(
                "QFrame#categoryCard{background:#e2efeb;border:1px solid #87ada5;border-radius:5px;}"
                " QLabel{color:#204640;font-size:12px;font-weight:600;background:transparent;border:none;}"
                " QToolButton{border-radius:3px;}"
            )
            self.shortcut_label.setStyleSheet(
                "background:transparent;border:none;padding:0;margin:0;font-size:11px;color:#2f766d;font-weight:600;"
            )
        else:
            self.card.setStyleSheet(
                "QFrame#categoryCard{background:#ffffff;border:1px solid #dde5e2;border-radius:5px;}"
                " QLabel{color:#29383a;font-size:12px;font-weight:500;background:transparent;border:none;}"
                " QToolButton{border-radius:3px;}"
            )
            self.shortcut_label.setStyleSheet(
                "background:transparent;border:none;padding:0;margin:0;font-size:11px;color:#6f7d7f;font-weight:500;"
            )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.rowClicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
