import html
import json
import sys
from pathlib import Path

from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

from .canvas import (
    Canvas,
    export_labelme_like_json,
    normalized_shape_label,
    shape_display_name,
)
from .config import (
    CATEGORY_COLOR_PALETTE,
    CATEGORY_ITEM_COLOR_ROLE,
    CATEGORY_ITEM_NAME_ROLE,
    LANGUAGE_EN,
    LANGUAGE_ZH,
    LINE_WIDTH_OPTIONS,
    SHAPE_LINE_COLOR,
    SUPPORTED_LANGUAGES,
    UI_COLOR,
    natural_sort_key,
    normalize_shape_ids,
    tr_text,
)
from .repository import Repo
from .sam_backend import (
    SamBoxSegmenter,
    default_sam_checkpoint_path,
    runtime_root_dir,
)
from .widgets import CategoryRowWidget, SectionPanel


class SimpleAnnotationMain(QtWidgets.QMainWindow):
    def __init__(
        self,
        img_dir=None,
        ann_dir=None,
        sam_checkpoint=None,
        sam_model_type="",
        language=None,
    ):
        super().__init__()
        self.app_settings = QtCore.QSettings("StelleraSAM", "StelleraSAM")
        stored_language = str(self.app_settings.value("interface/language", LANGUAGE_ZH))
        requested_language = language or stored_language
        self.ui_language = (
            requested_language if requested_language in SUPPORTED_LANGUAGES else LANGUAGE_ZH
        )
        self.repo = Repo(img_dir, ann_dir)
        self.images = []
        self.idx = -1
        self.img = None
        self.data = None
        self.dirty = False
        self.block = False
        self.auto_save_enabled = False
        self.defer_auto_save = False
        self.skip_unsaved_prompt_once = False
        self.current_sam_mode = ""
        self._sam_loaded_notice_signature = None
        self.category_names = []
        self.category_colors = {}
        self._file_status_icons = {}
        self._doc_cache = {}
        self._image_change_in_progress = False
        self._pending_row_change = None
        self._sam_rgb_cache_key = None
        self._sam_rgb_cache_image = None

        resolved_sam_checkpoint = sam_checkpoint or self._default_sam_checkpoint()
        self.sam_segmenter = SamBoxSegmenter(
            checkpoint=resolved_sam_checkpoint,
            model_type=sam_model_type or "",
        )

        self.setWindowTitle("StelleraSAM")
        self.resize(1480, 940)
        self.ui()
        self.actions()
        self.apply_language(self.ui_language, announce=False)
        self.setup_navigation_shortcuts()
        QtWidgets.QApplication.instance().installEventFilter(self)
        if self.repo.img_dir:
            self.load_dir(Path(self.repo.img_dir))

    def _default_sam_checkpoint(self):
        return default_sam_checkpoint_path()

    def _t(self, text, **values):
        return tr_text(self.ui_language, text, **values)

    def ui(self):
        self.setObjectName("annotationMainWindow")
        self.setStyleSheet(
            """
            QMainWindow#annotationMainWindow {
                background:#edf1f0;
            }
            QMenu {
                background:#ffffff;
                color:#28383a;
                border:1px solid #cfd9d6;
                border-radius:5px;
                padding:5px;
            }
            QMenu::item {
                padding:7px 24px 7px 10px;
                border-radius:3px;
            }
            QMenu::item:selected {
                background:#e3efeb;
                color:#1f514a;
            }
            QMenu::separator {
                height:1px;
                background:#e1e7e5;
                margin:5px 8px;
            }
            QStatusBar {
                background:#f7f9f8;
                color:#47585a;
                border-top:1px solid #d4ddda;
                font-size:12px;
                padding:2px 8px;
            }
            QStatusBar::item {
                border:0px;
            }
            QToolTip {
                background:#243638;
                color:#ffffff;
                border:1px solid #536b6d;
                padding:5px 7px;
            }
            QScrollBar:vertical {
                background:transparent;
                width:10px;
                margin:2px;
            }
            QScrollBar::handle:vertical {
                background:#bcc9c6;
                border-radius:4px;
                min-height:30px;
            }
            QScrollBar::handle:vertical:hover {
                background:#96aaa5;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height:0px;
            }
            QScrollBar:horizontal {
                background:transparent;
                height:10px;
                margin:2px;
            }
            QScrollBar::handle:horizontal {
                background:#bcc9c6;
                border-radius:4px;
                min-width:30px;
            }
            QScrollBar::handle:horizontal:hover {
                background:#96aaa5;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width:0px;
            }
            """
        )
        list_style = f"""
            QListWidget {{
                background:{UI_COLOR["file_list_bg"]};
                border:1px solid {UI_COLOR["file_list_border"]};
                border-radius:5px;
                outline:none;
                padding:5px;
            }}
            QListWidget::item {{
                background:transparent;
                border:1px solid transparent;
                border-radius:4px;
                padding:6px 8px;
                margin:1px;
                color:#2b3a3c;
                font-size:12px;
            }}
            QListWidget::item:selected {{
                background:{UI_COLOR["file_item_selected_bg"]};
                border:1px solid {UI_COLOR["file_item_selected_border"]};
                color:#1f514a;
            }}
        """
        self.files = QtWidgets.QListWidget()
        self.files.currentRowChanged.connect(self.request_change_row)
        self.files.setStyleSheet(list_style)
        self.files.setSpacing(4)
        self.files.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        self.left_group = SectionPanel("标注文件列表")
        self.left_group.setMinimumHeight(430)
        left_layout = self.left_group.content_layout()
        left_layout.setContentsMargins(10, 12, 10, 10)

        self.pick_dir_button = QtWidgets.QPushButton("打开标注文件夹")
        self.pick_dir_button.setFixedHeight(40)
        self.pick_dir_button.clicked.connect(self.pick_dir)
        self.pick_dir_button.setStyleSheet(
            f"""
            QPushButton {{
                font-size:13px;
                font-weight:600;
                background:#2f766d;
                border:1px solid #2f766d;
                border-radius:5px;
                color:#ffffff;
                padding:0 16px;
            }}
            QPushButton:hover {{
                background:#28665f;
                border-color:#28665f;
            }}
            QPushButton:pressed {{
                background:#225650;
                border-color:#225650;
            }}
            """
        )
        image_placeholder = QtWidgets.QWidget()
        image_placeholder.setStyleSheet(
            f"background:{UI_COLOR['left_placeholder_bg']};border:1px dashed {UI_COLOR['left_placeholder_border']};border-radius:5px;"
        )
        image_placeholder_layout = QtWidgets.QVBoxLayout(image_placeholder)
        image_placeholder_layout.setContentsMargins(0, 0, 0, 0)
        image_placeholder_layout.addStretch(1)
        image_placeholder_layout.addWidget(self.pick_dir_button, 0, QtCore.Qt.AlignCenter)
        image_placeholder_layout.addStretch(1)

        self.image_list_stack = QtWidgets.QStackedWidget()
        self.image_list_stack.addWidget(image_placeholder)
        self.image_list_stack.addWidget(self.files)
        left_layout.addWidget(self.image_list_stack)

        self.json_info_group = SectionPanel("JSON 文件保存列表")
        self.json_info_group.setMinimumHeight(260)
        json_info_layout = self.json_info_group.content_layout()
        json_info_layout.setContentsMargins(10, 12, 10, 10)
        json_info_layout.setSpacing(8)

        self.choose_json_dir_button = QtWidgets.QPushButton("指定 JSON 文件保存路径")
        self.choose_json_dir_button.setFixedHeight(40)
        self.choose_json_dir_button.clicked.connect(self.choose_json_save_dir)
        self.choose_json_dir_button.setStyleSheet(
            f"""
            QPushButton {{
                font-size:13px;
                font-weight:600;
                background:#ffffff;
                border:1px solid {UI_COLOR["json_button_border"]};
                border-radius:5px;
                color:{UI_COLOR["text_button_purple"]};
                padding:0 16px;
            }}
            QPushButton:hover {{
                background:{UI_COLOR["json_button_hover_bg"]};
                border-color:{UI_COLOR["json_button_hover_border"]};
            }}
            QPushButton:pressed {{
                background:{UI_COLOR["json_button_pressed_bg"]};
                border-color:{UI_COLOR["json_button_pressed_border"]};
            }}
            """
        )

        self.json_dir_label = QtWidgets.QLabel("未设置 JSON 保存路径")
        self.json_dir_label.setWordWrap(True)
        self.json_dir_label.setStyleSheet("QLabel{color:#647274;font-size:12px;padding:2px 1px;}")

        self.json_files = QtWidgets.QListWidget()
        self.json_files.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.json_files.setFocusPolicy(QtCore.Qt.NoFocus)
        self.json_files.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.json_files.setStyleSheet(
            f"""
            QListWidget {{
                background:{UI_COLOR["json_list_bg"]};
                border:1px solid {UI_COLOR["json_list_border"]};
                border-radius:5px;
                padding:5px;
            }}
            QListWidget::item {{
                background:transparent;
                border:0px;
                border-radius:3px;
                margin:1px;
                padding:5px 7px;
                color:#344446;
                font-size:12px;
            }}
        """
        )

        self.progress_label = QtWidgets.QLabel("已保存标注：0 / 0")
        self.progress_label.setStyleSheet("QLabel{color:#526264;font-size:12px;font-weight:600;}")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        self.progress_bar.setMinimumHeight(18)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar{
                background:#e7ecea;
                border:1px solid #cbd5d2;
                border-radius:5px;
                color:#263638;
                font-size:11px;
                font-weight:600;
                text-align:center;
                padding:0;
            }
            QProgressBar::chunk{
                background:#4a8f83;
                border-radius:4px;
                margin:0;
            }
            """
        )

        json_placeholder = QtWidgets.QWidget()
        json_placeholder.setStyleSheet(
            f"background:{UI_COLOR['json_placeholder_bg']};border:1px dashed {UI_COLOR['json_placeholder_border']};border-radius:5px;"
        )
        json_placeholder_layout = QtWidgets.QVBoxLayout(json_placeholder)
        json_placeholder_layout.setContentsMargins(0, 0, 0, 0)
        json_placeholder_layout.addStretch(1)
        json_placeholder_layout.addWidget(self.choose_json_dir_button, 0, QtCore.Qt.AlignCenter)
        json_placeholder_layout.addStretch(1)

        self.json_list_stack = QtWidgets.QStackedWidget()
        self.json_list_stack.addWidget(json_placeholder)
        self.json_list_stack.addWidget(self.json_files)
        json_info_layout.addWidget(self.json_list_stack, 1)
        json_info_layout.addWidget(self.progress_label)
        json_info_layout.addWidget(self.json_dir_label)
        json_info_layout.addWidget(self.progress_bar)

        self.canvas = Canvas()
        self.canvas.changed.connect(self.on_canvas_changed)
        self.canvas.selected.connect(self.on_canvas_selected)
        self.canvas.message.connect(self.statusBar().showMessage)
        self.canvas.shapeCreated.connect(self.on_shape_created)
        self.canvas.samBoxRequested.connect(self.on_sam_box_requested)
        self.canvas.samPointsChanged.connect(self.on_sam_points_changed)
        self.canvas.samPreviewAccepted.connect(self.on_sam_preview_accepted)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.setStyleSheet(
            "QScrollArea{background:#fcfdfd;border:1px solid #d4ddda;border-radius:6px;}"
        )

        self.regions = QtWidgets.QListWidget()
        self.regions.currentItemChanged.connect(self.on_region_list)
        self.regions.itemDoubleClicked.connect(self.on_region_item_double_clicked)
        self.regions.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.regions.customContextMenuRequested.connect(self.on_region_context_menu)
        self.regions.setStyleSheet(list_style)
        self.regions.setSpacing(4)
        self.regions.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        self.region_group = SectionPanel("已标注区域")
        self.region_group.setMinimumHeight(430)
        region_layout = self.region_group.content_layout()
        region_layout.setContentsMargins(10, 12, 10, 10)
        region_layout.addWidget(self.regions)

        self.category_name_edit = QtWidgets.QLineEdit()
        self.category_name_edit.setPlaceholderText("输入新类别名称")
        self.category_name_edit.setFixedWidth(170)
        self.category_name_edit.setFixedHeight(30)
        self.category_name_edit.setStyleSheet(
            """
            QLineEdit{
                font-size:13px;
                color:#2d3d3f;
                background:#ffffff;
                border:1px solid #c8d3d0;
                border-radius:5px;
                padding:0 10px;
            }
            QLineEdit:focus{
                border:1px solid #4a8f83;
            }
            QLineEdit::placeholder{
                color:#899597;
            }
            """
        )
        self.category_name_edit.returnPressed.connect(self.add_category)

        self.add_category_button = QtWidgets.QPushButton("添加")
        self.add_category_button.setFixedHeight(30)
        self.add_category_button.setMinimumWidth(86)
        self.add_category_button.setStyleSheet(
            """
            QPushButton{
                font-size:13px;
                font-weight:600;
                color:#ffffff;
                background:#2f766d;
                border:1px solid #2f766d;
                border-radius:5px;
                padding:0 12px;
            }
            QPushButton:hover{
                background:#28665f;
                border-color:#28665f;
            }
            QPushButton:pressed{
                background:#225650;
                border-color:#225650;
            }
            """
        )
        self.add_category_button.clicked.connect(self.add_category)

        add_row = QtWidgets.QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.setSpacing(6)
        add_row.addWidget(self.category_name_edit)
        add_row.addWidget(self.add_category_button)
        add_row.addStretch(1)

        self.category_list = QtWidgets.QListWidget()
        self.category_list.setStyleSheet(
            list_style
            + """
            QListWidget {
                font-size:12px;
                outline:none;
            }
            QListWidget::item {
                background:transparent;
                border:none;
                padding:0;
                margin:1px 0;
            }
            QListWidget::item:selected {
                background:transparent;
                border:none;
            }
            """
        )
        self.category_list.setSpacing(4)
        self.category_list.setFocusPolicy(QtCore.Qt.NoFocus)
        self.category_list.currentItemChanged.connect(self.on_category_selected)
        self.category_list.installEventFilter(self)

        self.current_category_label = QtWidgets.QLabel("当前类别：未选择")
        self.current_category_label.setTextFormat(QtCore.Qt.RichText)
        self.current_category_label.setStyleSheet(
            "QLabel{color:#3b4c4e;font-size:12px;font-weight:600;padding:3px 1px 5px 1px;}"
        )

        self.reg_label = QtWidgets.QLineEdit()
        self.reg_label.setPlaceholderText("编辑当前选中区域的标签")
        self.reg_label.setFixedWidth(220)
        self.reg_label.textEdited.connect(self.on_region_edit)

        editor_form = QtWidgets.QFormLayout()
        editor_form.setContentsMargins(0, 0, 0, 0)
        editor_form.setHorizontalSpacing(8)
        editor_form.setVerticalSpacing(8)
        editor_form.addRow("标签：", self.reg_label)

        self.detail_group = SectionPanel("标注类别")
        self.detail_group.setMinimumHeight(260)
        detail_layout = self.detail_group.content_layout()
        detail_layout.setContentsMargins(10, 12, 10, 10)
        detail_layout.setSpacing(9)
        detail_layout.addLayout(add_row)
        detail_layout.addWidget(self.current_category_label)
        detail_layout.addWidget(self.category_list, 1)
        detail_layout.addLayout(editor_form)
        label_widget = editor_form.labelForField(self.reg_label)
        if label_widget is not None:
            label_widget.hide()
        self.reg_label.hide()

        side_panel_min = 300
        side_panel_max = 360
        side_panel_default = 320
        self.side_panel_min = side_panel_min
        self.side_panel_max = side_panel_max
        self.side_panel_default = side_panel_default

        right_panel = QtWidgets.QWidget()
        right_panel.setObjectName("rightPanel")
        right_panel.setStyleSheet("QWidget#rightPanel{background:#edf1f0;}")
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(0)

        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setHandleWidth(8)
        right_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background:#d8e0de;
                border-radius:2px;
                margin:3px 8px;
            }
            QSplitter::handle:hover {
                background:#9fb7b1;
            }
            """
        )
        right_splitter.addWidget(self.region_group)
        right_splitter.addWidget(self.detail_group)
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([520, 280])
        self.right_panel_splitter = right_splitter
        right_layout.addWidget(right_splitter)
        right_panel.setMinimumWidth(side_panel_min)
        right_panel.setMaximumWidth(side_panel_max)

        left_panel = QtWidgets.QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setStyleSheet("QWidget#leftPanel{background:#edf1f0;}")
        left_panel.setMinimumWidth(side_panel_min)
        left_panel.setMaximumWidth(side_panel_max)
        left_panel_layout = QtWidgets.QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(8, 8, 8, 8)
        left_panel_layout.setSpacing(0)

        left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.setHandleWidth(8)
        left_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background:#d8e0de;
                border-radius:2px;
                margin:3px 8px;
            }
            QSplitter::handle:hover {
                background:#9fb7b1;
            }
            """
        )
        left_splitter.addWidget(self.left_group)
        left_splitter.addWidget(self.json_info_group)
        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([520, 280])
        self.left_panel_splitter = left_splitter
        left_panel_layout.addWidget(left_splitter)

        splitter = QtWidgets.QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            """
            QSplitter::handle {
                background:#d8e0de;
                margin:8px 2px;
                border-radius:2px;
            }
            QSplitter::handle:hover {
                background:#9fb7b1;
            }
            """
        )
        splitter.addWidget(left_panel)
        splitter.addWidget(self.scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([side_panel_default, 920, side_panel_default])
        self.main_splitter = splitter
        self.setCentralWidget(splitter)
        self.setContentsMargins(0, 0, 0, 0)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setMinimumHeight(26)
        self.copyright_label = QtWidgets.QLabel()
        self.copyright_label.setObjectName("copyrightLabel")
        self.copyright_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.copyright_label.setStyleSheet(
            "QLabel#copyrightLabel{color:#687779;font-size:11px;padding:0 8px 0 14px;}"
        )
        self.statusBar().addPermanentWidget(self.copyright_label)
        QtCore.QTimer.singleShot(0, self.reset_side_panel_widths)

        self.statusBar().showMessage("选择模式：可拖动区域；矩形：拖拽；多边形：左键加点")

    def actions(self):
        tb = self.addToolBar("annotation_tools")
        self.annotation_toolbar = tb
        tb.setMovable(False)
        tb.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        tb.setIconSize(QtCore.QSize(18, 18))
        tb.setStyleSheet(
            f"""
            QToolBar {{
                spacing:1px;
                padding:4px 8px;
                border:0px;
                border-bottom:1px solid {UI_COLOR["toolbar_border"]};
                background:{UI_COLOR["toolbar_bg"]};
            }}
            QToolBar::separator {{
                width:1px;
                margin:6px 7px;
                background:#587779;
            }}
            QToolButton {{
                border:1px solid transparent;
                border-radius:4px;
                background:transparent;
                padding:5px 8px;
                margin:0px 1px;
                color:#f7fafc;
                font-size:14px;
                font-weight:600;
            }}
            QToolButton:hover {{
                background:{UI_COLOR["toolbar_button_hover"]};
                border-color:{UI_COLOR["toolbar_button_hover_border"]};
            }}
            QToolButton:pressed {{
                background:{UI_COLOR["toolbar_button_pressed"]};
                border-color:{UI_COLOR["toolbar_button_pressed_border"]};
            }}
            QToolButton:checked {{
                background:#2f766d;
                border-color:#8db5ad;
                font-weight:700;
            }}
            QToolButton::menu-indicator {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 8px;
            }}
            """
        )

        self.toolbar_actions = {}
        self.file_action_specs = {}
        self.menu_shortcuts = []

        def register_menu_shortcut(sequence, callback):
            shortcut_object = QtWidgets.QShortcut(QtGui.QKeySequence(sequence), self)
            shortcut_object.setContext(QtCore.Qt.WindowShortcut)
            shortcut_object.activated.connect(callback)
            self.menu_shortcuts.append(shortcut_object)

        self.toolbar_left_spacer = QtWidgets.QWidget()
        self.toolbar_left_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        tb.addWidget(self.toolbar_left_spacer)

        self.file_menu = QtWidgets.QMenu(self)
        file_actions = [
            ("打开单张图像", self.pick_file, "Ctrl+O"),
            ("打开标注文件夹", self.pick_dir, "Ctrl+U"),
            ("JSON 保存目录", self.choose_json_save_dir, "Ctrl+R"),
        ]
        for text, fn, shortcut in file_actions:
            action = QtWidgets.QAction(f"{text} ({shortcut})", self)
            action.triggered.connect(fn)
            self.file_menu.addAction(action)
            register_menu_shortcut(shortcut, fn)
            self.toolbar_actions[text] = action
            self.file_action_specs[text] = (action, shortcut)

        self.file_button = QtWidgets.QToolButton()
        self.file_button.setText("打开文件")
        self.file_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.file_button.setMenu(self.file_menu)
        tb.addWidget(self.file_button)

        self.save_menu = QtWidgets.QMenu(self)
        self.auto_save_action = QtWidgets.QAction("自动保存", self)
        self.auto_save_action.setCheckable(True)
        self.auto_save_action.toggled.connect(self.set_auto_save_enabled)
        self.manual_save_action = QtWidgets.QAction("手动保存 (Ctrl+S)", self)
        self.manual_save_action.triggered.connect(self.save)
        self.save_menu.addAction(self.auto_save_action)
        self.save_menu.addAction(self.manual_save_action)
        register_menu_shortcut("Ctrl+S", self.save)

        self.save_button = QtWidgets.QToolButton()
        self.save_button.setText("保存方式")
        self.save_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.save_button.setMenu(self.save_menu)
        self.save_button.setMinimumWidth(96)
        tb.addWidget(self.save_button)
        tb.addSeparator()

        self.line_width_menu = QtWidgets.QMenu(self)
        self.line_width_group = QtWidgets.QActionGroup(self)
        self.line_width_group.setExclusive(True)
        for label, ratio in LINE_WIDTH_OPTIONS:
            action = QtWidgets.QAction(label, self)
            action.setCheckable(True)
            action.setData(ratio)
            action.triggered.connect(
                lambda checked=False, value=ratio, text=label: self.set_shape_line_width_ratio(value, text)
            )
            if abs(ratio - self.canvas.shape_line_ratio) < 1e-9:
                action.setChecked(True)
            self.line_width_group.addAction(action)
            self.line_width_menu.addAction(action)
        self.line_width_button = QtWidgets.QToolButton()
        self.line_width_button.setText("线粗细")
        self.line_width_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.line_width_button.setMenu(self.line_width_menu)
        self.line_width_button.setToolTip("线粗细：选择标注轮廓线粗细")
        self.line_width_button.setMinimumWidth(96)

        acts = [
            ("上一张", lambda: self.step(-1), "A"),
            ("下一张", lambda: self.step(1), "D"),
            ("矩形", lambda: self.set_mode("rectangle"), "Z"),
            ("多边形", lambda: self.set_mode("polygon"), "C"),
            ("返回上一步", self.undo_mode_step, "Ctrl+Z"),
            ("暂停标注", self.pause_annotation, "Esc"),
            ("删除区域", self.del_region, "Delete"),
            ("缩小", self.zoom_out, ""),
            ("放大", self.zoom_in, ""),
        ]
        self.annotation_action_specs = {}

        self.annotation_mode_group = QtWidgets.QActionGroup(self)
        self.annotation_mode_group.setExclusive(True)

        self.sam_mode_menu = QtWidgets.QMenu(self)
        self.sam_point_action = QtWidgets.QAction("点分割 (E)", self)
        self.sam_point_action.setCheckable(True)
        self.sam_point_action.triggered.connect(lambda checked=False: self.set_sam_submode("sam_point"))
        self.sam_box_action = QtWidgets.QAction("框分割 (Q)", self)
        self.sam_box_action.setCheckable(True)
        self.sam_box_action.triggered.connect(lambda checked=False: self.set_sam_submode("sam_box"))
        self.sam_mode_menu.addAction(self.sam_point_action)
        self.sam_mode_menu.addAction(self.sam_box_action)

        self.sam_mode_button = QtWidgets.QToolButton()
        self.sam_mode_button.setText("SAM 分割")
        self.sam_mode_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.sam_mode_button.setMenu(self.sam_mode_menu)
        self.sam_mode_button.setCheckable(True)
        self.sam_mode_button.setMinimumWidth(96)
        self.sam_mode_button.setToolTip("SAM 分割：下拉选择点分割或框分割")

        for text, fn, shortcut in acts:
            if text == "缩小":
                display_text = "缩小（Ctrl+滚轮下）"
            elif text == "放大":
                display_text = "放大（Ctrl+滚轮上）"
            else:
                display_text = f"{text} ({shortcut})" if shortcut else text
            action = QtWidgets.QAction(display_text, self)
            action.triggered.connect(fn)
            if text in {"矩形", "多边形"}:
                action.setCheckable(True)
                self.annotation_mode_group.addAction(action)
                if text == "矩形":
                    self.rectangle_action = action
                else:
                    self.polygon_action = action
            if shortcut and shortcut not in {"A", "D", "Delete", "Z", "C"}:
                register_menu_shortcut(shortcut, fn)
            self.toolbar_actions[text] = action
            self.annotation_action_specs[text] = (action, shortcut)

        for action_name in ("上一张", "下一张"):
            tb.addAction(self.toolbar_actions[action_name])
        tb.addSeparator()

        self.annotation_tools_menu = QtWidgets.QMenu(self)
        self.annotation_tools_menu.addMenu(self.line_width_menu)
        for action_name in ("矩形", "多边形"):
            self.annotation_tools_menu.addAction(self.toolbar_actions[action_name])
        self.annotation_tools_button = QtWidgets.QToolButton()
        self.annotation_tools_button.setText("标注")
        self.annotation_tools_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.annotation_tools_button.setMenu(self.annotation_tools_menu)
        tb.addWidget(self.annotation_tools_button)
        tb.addWidget(self.sam_mode_button)
        tb.addSeparator()

        self.edit_menu = QtWidgets.QMenu(self)
        for action_name in ("返回上一步", "暂停标注", "删除区域"):
            self.edit_menu.addAction(self.toolbar_actions[action_name])
        self.edit_button = QtWidgets.QToolButton()
        self.edit_button.setText("编辑")
        self.edit_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.edit_button.setMenu(self.edit_menu)
        tb.addWidget(self.edit_button)
        tb.addSeparator()

        self.view_menu = QtWidgets.QMenu(self)
        for action_name in ("缩小", "放大"):
            self.view_menu.addAction(self.toolbar_actions[action_name])
        self.view_button = QtWidgets.QToolButton()
        self.view_button.setText("视图")
        self.view_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.view_button.setMenu(self.view_menu)
        tb.addWidget(self.view_button)

        self.language_menu = QtWidgets.QMenu(self)
        self.language_group = QtWidgets.QActionGroup(self)
        self.language_group.setExclusive(True)
        self.chinese_language_action = QtWidgets.QAction("中文", self)
        self.english_language_action = QtWidgets.QAction("English", self)
        for action, language in (
            (self.chinese_language_action, LANGUAGE_ZH),
            (self.english_language_action, LANGUAGE_EN),
        ):
            action.setCheckable(True)
            action.setData(language)
            action.triggered.connect(
                lambda checked=False, selected=language: self.apply_language(selected)
            )
            self.language_group.addAction(action)
            self.language_menu.addAction(action)

        self.language_button = QtWidgets.QToolButton()
        self.language_button.setObjectName("languageButton")
        self.language_button.setText("Language")
        self.language_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.language_button.setMenu(self.language_menu)
        self.language_button.setToolTip("Language / 语言")

        tb.addSeparator()
        tb.addWidget(self.language_button)

        self.toolbar_right_spacer = QtWidgets.QWidget()
        self.toolbar_right_spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        tb.addWidget(self.toolbar_right_spacer)
        self.sync_toolbar_dropdown_widths()

    def sync_toolbutton_menu_width(self, button, menu):
        button.ensurePolished()
        menu.ensurePolished()
        button_metric = button.fontMetrics()
        menu_metric = menu.fontMetrics()
        indicator_width = 18
        frame_padding = 26
        menu_text_width = 0
        for action in menu.actions():
            menu_text_width = max(menu_text_width, menu_metric.horizontalAdvance(action.text()))
        button_text_width = button_metric.horizontalAdvance(button.text())
        button_width = max(72, button_text_width + frame_padding + indicator_width)
        button.setFixedWidth(min(button_width, 190))
        menu.setMinimumWidth(max(button.width(), menu_text_width + frame_padding))

    def sync_toolbar_dropdown_widths(self):
        self.sync_toolbutton_menu_width(self.file_button, self.file_menu)
        self.sync_toolbutton_menu_width(self.save_button, self.save_menu)
        self.sync_toolbutton_menu_width(self.annotation_tools_button, self.annotation_tools_menu)
        self.sync_toolbutton_menu_width(self.sam_mode_button, self.sam_mode_menu)
        self.sync_toolbutton_menu_width(self.edit_button, self.edit_menu)
        self.sync_toolbutton_menu_width(self.view_button, self.view_menu)
        if hasattr(self, "language_button"):
            self.sync_toolbutton_menu_width(self.language_button, self.language_menu)

    def _localized_action_text(self, canonical_text, shortcut):
        if canonical_text == "缩小":
            return self._t("缩小（Ctrl+滚轮下）")
        if canonical_text == "放大":
            return self._t("放大（Ctrl+滚轮上）")
        text = self._t(canonical_text)
        return f"{text} ({shortcut})" if shortcut else text

    def apply_language(self, language, announce=True):
        if language not in SUPPORTED_LANGUAGES:
            return
        self.ui_language = language
        self.app_settings.setValue("interface/language", language)
        self.apply_interface_font()
        self.canvas.set_ui_language(language)
        self.retranslate_ui()
        if announce:
            self.statusBar().showMessage(self._t("界面语言已切换为中文"))

    def apply_interface_font(self):
        family = "Times New Roman" if self.ui_language == LANGUAGE_EN else "Microsoft YaHei UI"
        interface_font = QtGui.QFont(family, 10)
        interface_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setFont(interface_font)
        QtWidgets.QToolTip.setFont(interface_font)
        for widget in (self, *self.findChildren(QtWidgets.QWidget)):
            widget_font = widget.font()
            widget_font.setFamily(family)
            widget_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
            widget.setFont(widget_font)
        for action in self.findChildren(QtWidgets.QAction):
            action_font = action.font()
            action_font.setFamily(family)
            action_font.setStyleStrategy(QtGui.QFont.PreferAntialias)
            action.setFont(action_font)

    def retranslate_ui(self):
        self.left_group.setTitle(self._t("标注文件列表"))
        self.pick_dir_button.setText(self._t("打开标注文件夹"))
        self.json_info_group.setTitle(self._t("JSON 文件保存列表"))
        self.choose_json_dir_button.setText(self._t("指定 JSON 文件保存路径"))
        self.region_group.setTitle(self._t("已标注区域"))
        self.detail_group.setTitle(self._t("标注类别"))
        self.category_name_edit.setPlaceholderText(self._t("输入新类别名称"))
        self.add_category_button.setText(self._t("添加"))
        self.reg_label.setPlaceholderText(self._t("编辑当前选中区域的标签"))

        for canonical_text, (action, shortcut) in self.file_action_specs.items():
            action.setText(f"{self._t(canonical_text)} ({shortcut})")
        self.file_button.setText(self._t("打开文件"))
        self.auto_save_action.setText(self._t("自动保存"))
        self.manual_save_action.setText(f"{self._t('手动保存')} (Ctrl+S)")
        self.save_button.setText(self._t("保存方式"))
        self.line_width_button.setText(self._t("线粗细"))
        self.line_width_menu.setTitle(self._t("线粗细"))
        self.line_width_button.setToolTip(self._t("线粗细：选择标注轮廓线粗细"))
        self.annotation_tools_button.setText(self._t("标注"))
        self.sam_point_action.setText(self._t("点分割 (E)"))
        self.sam_box_action.setText(self._t("框分割 (Q)"))
        self.sam_mode_button.setText(self._t("SAM 分割"))
        self.sam_mode_button.setToolTip(
            self._t("SAM 分割：下拉选择点分割或框分割")
        )
        self.edit_button.setText(self._t("编辑"))
        self.view_button.setText(self._t("视图"))
        for canonical_text, (action, shortcut) in self.annotation_action_specs.items():
            action.setText(self._localized_action_text(canonical_text, shortcut))
            if canonical_text == "缩小":
                action.setToolTip(self._t("缩小（Ctrl+滚轮下）"))
            elif canonical_text == "放大":
                action.setToolTip(self._t("放大（Ctrl+滚轮上）"))
            else:
                text = self._t(canonical_text)
                action.setToolTip(f"{text} ({shortcut})" if shortcut else text)

        self.language_button.setText("Language")
        self.chinese_language_action.setText(self._t("中文"))
        self.english_language_action.setText(self._t("English"))
        self.copyright_label.setText(
            self._t(
                "© {year} 中国农业科学院农业信息研究所",
                year=QtCore.QDate.currentDate().year(),
            )
        )
        self.chinese_language_action.setChecked(self.ui_language == LANGUAGE_ZH)
        self.english_language_action.setChecked(self.ui_language == LANGUAGE_EN)

        self.update_json_dir_info()
        self.update_current_category_display()
        self.title()
        self.sync_toolbar_dropdown_widths()
        self.canvas.update()
        if not self.img:
            self.statusBar().showMessage(
                self._t("选择模式：可拖动区域；矩形：拖拽；多边形：左键加点")
            )

    def update_current_category_display(self):
        category = self.current_category()
        prefix = html.escape(self._t("当前类别"))
        separator = "：" if self.ui_language == LANGUAGE_ZH else ": "
        if category:
            value = html.escape(category)
            self.current_category_label.setText(
                f'{prefix}{separator}<span style="color:#2f766d;font-size:12px;font-weight:700;">{value}</span>'
            )
        else:
            value = html.escape(self._t("未选择"))
            self.current_category_label.setText(
                f'{prefix}{separator}<span style="color:#7d898b;font-size:12px;font-weight:500;">{value}</span>'
            )

    def reset_side_panel_widths(self):
        if not hasattr(self, "main_splitter"):
            return
        total_width = max(self.main_splitter.size().width(), self.width(), self.side_panel_default * 2 + 600)
        center_width = max(600, total_width - self.side_panel_default * 2)
        self.main_splitter.setSizes([self.side_panel_default, center_width, self.side_panel_default])

    def set_shape_line_width_ratio(self, ratio, label=None):
        self.canvas.set_shape_line_ratio(ratio)
        self.canvas.update()
        if label:
            self.statusBar().showMessage(
                self._t("当前标注线粗细：图像长边的 {label}", label=label)
            )

    def current_category(self):
        if not hasattr(self, "category_list"):
            return ""
        item = self.category_list.currentItem()
        return str(item.data(CATEGORY_ITEM_NAME_ROLE) or "").strip() if item else ""

    def find_category_item(self, category):
        if not hasattr(self, "category_list"):
            return None
        category = str(category or "").strip()
        if not category:
            return None
        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            if str(item.data(CATEGORY_ITEM_NAME_ROLE) or "").strip() == category:
                return item
        return None

    def select_category_by_index(self, index):
        if not hasattr(self, "category_list"):
            return False
        if index < 0 or index >= self.category_list.count():
            return False
        item = self.category_list.item(index)
        if item is None:
            return False
        self.category_list.setCurrentItem(item)
        category = str(item.data(CATEGORY_ITEM_NAME_ROLE) or "").strip()
        if category:
            self.statusBar().showMessage(
                self._t(
                    "当前标注类别已切换为：{category}  快捷键：{shortcut}",
                    category=category,
                    shortcut=index + 1,
                )
            )
        return True

    def default_category_color(self, category):
        names = list(self.category_names)
        if category not in names:
            names.append(category)
        index = names.index(category)
        return CATEGORY_COLOR_PALETTE[index % len(CATEGORY_COLOR_PALETTE)]

    def ensure_category_color(self, category):
        category = str(category or "").strip()
        if not category:
            return ""
        color = self.category_colors.get(category, "")
        qcolor = QtGui.QColor(color)
        if not qcolor.isValid():
            color = self.default_category_color(category)
            self.category_colors[category] = color
        return self.category_colors[category]

    def category_color(self, category):
        color = self.ensure_category_color(category)
        qcolor = QtGui.QColor(color)
        return qcolor.name() if qcolor.isValid() else QtGui.QColor(SHAPE_LINE_COLOR).name()

    def apply_category_color_to_shape(self, shape, category=""):
        if not isinstance(shape, dict):
            return
        category = str(category or normalized_shape_label(shape) or "").strip()
        if not category:
            attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
            category = str(attrs.get("object_category", "")).strip()
        if not category:
            return
        shape["line_color"] = self.category_color(category)

    def sync_shape_colors_from_categories(self):
        if not self.data:
            return
        for shape in self.data.get("shapes", []):
            self.apply_category_color_to_shape(shape)

    def refresh_category_list(self):
        current_text = self.current_category()
        self.category_list.blockSignals(True)
        self.category_list.clear()
        for index, name in enumerate(self.category_names, start=1):
            item = QtWidgets.QListWidgetItem("")
            color_hex = self.category_color(name)
            item.setData(CATEGORY_ITEM_COLOR_ROLE, color_hex)
            item.setData(CATEGORY_ITEM_NAME_ROLE, name)
            item.setToolTip("")
            item.setSizeHint(QtCore.QSize(0, 34))
            self.category_list.addItem(item)
            shortcut_text = str(index) if index <= 9 else ""
            widget = CategoryRowWidget(name, color_hex, shortcut_text, self.category_list)
            widget.rowClicked.connect(lambda item=item: self.category_list.setCurrentItem(item))
            widget.colorClicked.connect(lambda checked=False, category=name, item=item: self._on_category_color_box_clicked(category, item))
            self.category_list.setItemWidget(item, widget)
        self.category_list.blockSignals(False)
        if current_text:
            match = self.find_category_item(current_text)
            if match is not None:
                self.category_list.setCurrentItem(match)
        elif self.category_list.count() > 0 and self.category_list.currentItem() is None:
            self.category_list.setCurrentRow(0)
        self.refresh_category_widget_selection()

    def _on_category_color_box_clicked(self, category, item):
        self.category_list.setCurrentItem(item)
        self.choose_category_color(category)

    def refresh_category_widget_selection(self):
        current_item = self.category_list.currentItem()
        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            widget = self.category_list.itemWidget(item)
            if isinstance(widget, CategoryRowWidget):
                widget.set_selected(item is current_item)
                category = str(item.data(CATEGORY_ITEM_NAME_ROLE) or "").strip()
                widget.set_color(item.data(CATEGORY_ITEM_COLOR_ROLE) or self.category_color(category))

    def add_category(self):
        name = self.category_name_edit.text().strip()
        if not name:
            return
        if name not in self.category_names:
            self.category_names.append(name)
        self.ensure_category_color(name)
        self.refresh_category_list()
        match = self.find_category_item(name)
        if match is not None:
            self.category_list.setCurrentItem(match)
        self.category_name_edit.clear()

    def sync_categories_from_shapes(self):
        extracted = []
        for shape in (self.data or {}).get("shapes", []):
            label = normalized_shape_label(shape)
            if not label:
                attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
                label = str(attrs.get("object_category", "")).strip()
            if label and label not in extracted:
                extracted.append(label)
        changed = False
        for name in extracted:
            if name not in self.category_names:
                self.category_names.append(name)
                changed = True
            self.ensure_category_color(name)
        self.sync_shape_colors_from_categories()
        if changed:
            current_text = self.current_category()
            self.refresh_category_list()
            if extracted:
                match = self.find_category_item(extracted[0])
                if match is not None:
                    self.category_list.setCurrentItem(match)
            elif current_text:
                match = self.find_category_item(current_text)
                if match is not None:
                    self.category_list.setCurrentItem(match)
        elif not self.current_category() and extracted:
            match = self.find_category_item(extracted[0])
            if match is not None:
                self.category_list.setCurrentItem(match)
            self.refresh_category_widget_selection()

    def on_category_selected(self, current, previous):
        del previous
        category = str(current.data(CATEGORY_ITEM_NAME_ROLE) or "").strip() if current else ""
        self.refresh_category_widget_selection()
        if category:
            self.canvas.set_shape_line_color(self.category_color(category))
        self.update_current_category_display()
        if category:
            self.statusBar().showMessage(
                self._t("当前标注类别已切换为：{category}", category=category)
            )

    def choose_category_color(self, category):
        category = str(category or "").strip()
        if not category:
            return
        current = QtGui.QColor(self.category_color(category))
        chosen = QtWidgets.QColorDialog.getColor(
            current, self, self._t("设置类别颜色：{category}", category=category)
        )
        if not chosen.isValid():
            return
        self.category_colors[category] = chosen.name()
        if self.data:
            changed = False
            for shape in self.data.get("shapes", []):
                label = normalized_shape_label(shape)
                attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
                object_category = str(attrs.get("object_category", "")).strip()
                if category in {label, object_category}:
                    if shape.get("line_color") != chosen.name():
                        shape["line_color"] = chosen.name()
                        changed = True
            if changed:
                self.canvas.update()
                self.refresh_regions()
                self.mark_dirty()
        self.refresh_category_list()
        match = self.find_category_item(category)
        if match is not None:
            self.category_list.setCurrentItem(match)
        if self.current_category() == category:
            self.canvas.set_shape_line_color(chosen.name())
        self.statusBar().showMessage(
            self._t(
                "类别颜色已更新：{category} -> {color}",
                category=category,
                color=chosen.name(),
            )
        )

    def delete_selected_category(self):
        item = self.category_list.currentItem()
        if item is None:
            return False
        category = str(item.data(CATEGORY_ITEM_NAME_ROLE) or "").strip()
        if not category:
            return False
        row = self.category_list.row(item)
        if category in self.category_names:
            self.category_names.remove(category)
        self.category_colors.pop(category, None)
        self.refresh_category_list()
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(min(row, self.category_list.count() - 1))
        else:
            self.update_current_category_display()
        self.statusBar().showMessage(
            self._t("已删除类别：{category}", category=category)
        )
        return True

    def normalize_loaded_shape_labels(self):
        if not self.data:
            return
        for shape in self.data.get("shapes", []):
            if normalized_shape_label(shape):
                continue
            attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
            category = str(attrs.get("object_category", "")).strip()
            if category:
                shape["label"] = category

    def ensure_shape_label(self, shape, fallback_category=""):
        if not isinstance(shape, dict):
            return ""
        label = normalized_shape_label(shape)
        if label:
            return label
        attrs = shape.setdefault("attributes", {})
        category = str(attrs.get("object_category", "")).strip()
        if not category:
            category = str(fallback_category or "").strip()
        if category:
            shape["label"] = category
            attrs["object_category"] = category
            return category
        return ""

    def _ensure_category_selected(self, show_message=True):
        category = self.current_category()
        if category:
            return category
        if show_message:
            QtWidgets.QMessageBox.warning(
                self,
                self._t("未设置标注类别"),
                self._t("请先在右侧“标注类别”中添加并选择一个类别，再开始标注。"),
            )
        return ""

    def _text_input_active(self):
        app = QtWidgets.QApplication.instance()
        if app is None:
            return False
        if app.activeModalWidget() is not None:
            return True
        focus = app.focusWidget()
        return isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox))

    def _cursor_in_widget(self, widget):
        try:
            if widget is None or not widget.isVisible():
                return False
            local_pos = widget.mapFromGlobal(QtGui.QCursor.pos())
            return widget.rect().contains(local_pos)
        except RuntimeError:
            return False

    def _nav_shortcut_allowed(self):
        if self._text_input_active():
            return False
        return (
            self._cursor_in_widget(self.files.viewport())
            or self._cursor_in_widget(self.scroll.viewport())
            or self._cursor_in_widget(self.regions.viewport())
        )

    def setup_navigation_shortcuts(self):
        self.prev_image_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("A"), self)
        self.prev_image_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self.prev_image_shortcut.activated.connect(self.trigger_prev_image_shortcut)

        self.next_image_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("D"), self)
        self.next_image_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self.next_image_shortcut.activated.connect(self.trigger_next_image_shortcut)

        self.rectangle_mode_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Z"), self)
        self.rectangle_mode_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self.rectangle_mode_shortcut.activated.connect(self.trigger_rectangle_mode_shortcut)

        self.polygon_mode_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("C"), self)
        self.polygon_mode_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self.polygon_mode_shortcut.activated.connect(self.trigger_polygon_mode_shortcut)

    def trigger_prev_image_shortcut(self):
        if self._nav_shortcut_allowed():
            self.step(-1)

    def trigger_next_image_shortcut(self):
        if self._nav_shortcut_allowed():
            self.step(1)

    def trigger_rectangle_mode_shortcut(self):
        if not self._text_input_active():
            self.set_mode("rectangle")

    def trigger_polygon_mode_shortcut(self):
        if not self._text_input_active():
            self.set_mode("polygon")

    def _doc_cache_key(self, img):
        try:
            return str(Path(img).resolve())
        except Exception:
            return str(img)

    def load_annotation_doc(self, img, width, height):
        cache_key = self._doc_cache_key(img)
        ann_path = self.repo.ann_path(img)
        if ann_path and ann_path.exists() and cache_key in self._doc_cache:
            cached = self._doc_cache.get(cache_key)
            if isinstance(cached, dict):
                data = json.loads(json.dumps(cached, ensure_ascii=False))
                data["imagePath"], data["imageWidth"], data["imageHeight"] = img.name, width, height
                normalize_shape_ids(data)
                return data
        data = self.repo.load(img, width, height)
        if ann_path and ann_path.exists():
            self._doc_cache[cache_key] = json.loads(json.dumps(data, ensure_ascii=False))
        else:
            self._doc_cache.pop(cache_key, None)
        return data

    def eventFilter(self, obj, event):
        if (
            hasattr(self, "category_list")
            and obj is self.category_list
            and event.type() == QtCore.QEvent.KeyPress
            and event.modifiers() == QtCore.Qt.NoModifier
            and event.key() == QtCore.Qt.Key_Delete
        ):
            if self.delete_selected_category():
                return True
        if (
            hasattr(self, "category_list")
            and event.type() == QtCore.QEvent.KeyPress
            and event.modifiers() == QtCore.Qt.NoModifier
            and event.key() == QtCore.Qt.Key_Delete
            and not self._text_input_active()
            and self._cursor_in_widget(self.category_list.viewport())
        ):
            if self.delete_selected_category():
                return True
        if (
            hasattr(self, "category_list")
            and event.type() == QtCore.QEvent.KeyPress
            and event.modifiers() == QtCore.Qt.NoModifier
            and not self._text_input_active()
            and QtCore.Qt.Key_1 <= event.key() <= QtCore.Qt.Key_9
        ):
            if self.select_category_by_index(event.key() - QtCore.Qt.Key_1):
                return True
        if (
            event.type() == QtCore.QEvent.Wheel
            and event.modifiers() & QtCore.Qt.ControlModifier
            and obj is self.scroll.viewport()
        ):
            if self.canvas.pix.isNull():
                return True
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            return True
        if event.type() == QtCore.QEvent.KeyPress and event.modifiers() == QtCore.Qt.NoModifier and self._nav_shortcut_allowed():
            current_mode = getattr(self.canvas, "mode", "select")
            if current_mode in {"sam_point", "sam_box"}:
                if event.key() == QtCore.Qt.Key_Q:
                    self.set_sam_submode("sam_box")
                    return True
                if event.key() == QtCore.Qt.Key_E:
                    self.set_sam_submode("sam_point")
                    return True
            elif self.sam_segmenter.is_loaded():
                if event.key() == QtCore.Qt.Key_Q:
                    self.set_sam_submode("sam_box")
                    return True
                if event.key() == QtCore.Qt.Key_E:
                    self.set_sam_submode("sam_point")
                    return True
        if event.type() == QtCore.QEvent.KeyPress and event.modifiers() == QtCore.Qt.NoModifier and event.key() == QtCore.Qt.Key_Delete:
            if self.canvas.hasFocus() or self.regions.hasFocus():
                self.del_region()
                return True
        return super().eventFilter(obj, event)

    def title(self):
        cur = self.img.name if self.img else self._t("未加载图像")
        self.setWindowTitle(
            f"StelleraSAM - {cur}{' *' if self.dirty else ''}"
        )

    def refresh_json_file_list(self):
        self.image_list_stack.setCurrentIndex(1 if self.images else 0)
        self.json_files.clear()
        total = len(self.images)
        saved = 0
        if self.repo.ann_dir is not None:
            for img in self.images:
                ann_path = self.repo.ann_path(img)
                if ann_path and ann_path.exists():
                    saved += 1
                    self.json_files.addItem(ann_path.name)
        self.update_json_progress_display(saved)

    def update_json_progress_display(self, saved=None):
        total = len(self.images)
        if saved is None:
            saved = self.json_files.count() if self.repo.ann_dir is not None else 0
        progress_value = 0 if total == 0 else int(round(saved * 100 / total))
        self.progress_label.setText(
            self._t("已保存标注：{saved} / {total}", saved=saved, total=total)
        )
        self.progress_bar.setValue(progress_value)
        self.progress_bar.setFormat("%p%")

    def upsert_json_file_list_item(self, ann_path):
        if self.repo.ann_dir is None or not ann_path:
            return
        name = Path(ann_path).name
        self.json_list_stack.setCurrentIndex(1)
        for row in range(self.json_files.count()):
            if self.json_files.item(row).text() == name:
                return
        insert_row = self.json_files.count()
        key = natural_sort_key(name)
        for row in range(self.json_files.count()):
            if natural_sort_key(self.json_files.item(row).text()) > key:
                insert_row = row
                break
        self.json_files.insertItem(insert_row, name)

    def update_json_dir_info(self):
        if self.repo.ann_dir is None:
            self.json_dir_label.setText(self._t("未设置 JSON 保存路径"))
            self.json_list_stack.setCurrentIndex(0)
        else:
            self.json_dir_label.setText(str(self.repo.ann_dir))
            self.json_list_stack.setCurrentIndex(1)
        self.refresh_json_file_list()
        self.refresh_file_list()

    def set_auto_save_enabled(self, enabled):
        self.auto_save_enabled = bool(enabled)
        mode = self._t("自动保存" if enabled else "手动保存")
        self.statusBar().showMessage(self._t("当前保存方式：{mode}", mode=mode))
        if self.auto_save_enabled and self.dirty and self.img and self.data:
            self.save()

    def mark_dirty(self):
        self.dirty = True
        self.title()
        if self.auto_save_enabled and not self.defer_auto_save and self.img and self.data:
            self.save()

    def confirm_unsaved_changes(self, action_text):
        if not self.dirty or not self.img:
            return True
        if self.auto_save_enabled and self.img and self.data:
            if self.save():
                return True
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle(self._t("存在未保存修改"))
        box.setText(
            self._t("当前图像有未保存修改，是否在{action}前保存？", action=action_text)
        )
        save_button = box.addButton(self._t("保存"), QtWidgets.QMessageBox.AcceptRole)
        discard_button = box.addButton(
            self._t("不保存"), QtWidgets.QMessageBox.DestructiveRole
        )
        box.addButton(self._t("取消"), QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(save_button)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is save_button:
            return self.save()
        if clicked is discard_button:
            return True
        return False

    def pick_dir(self):
        start_dir = str(self.repo.img_dir) if self.repo.img_dir else ""
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, self._t("选择标注文件夹"), start_dir
        )
        if d:
            self.load_dir(Path(d))

    def pick_file(self):
        start_dir = str(self.img) if self.img else (str(self.repo.img_dir) if self.repo.img_dir else "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self._t("打开单张图像"),
            start_dir,
            self._t("图像文件 (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)"),
        )
        if path:
            self.open_image_file(Path(path))

    def choose_json_save_dir(self):
        start_dir = str(self.repo.ann_dir) if self.repo.ann_dir else str(runtime_root_dir())
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, self._t("选择 JSON 保存目录"), start_dir
        )
        if not d:
            return
        self._doc_cache.clear()
        self.repo.set_dirs(self.repo.img_dir, Path(d))
        self.update_json_dir_info()
        self.statusBar().showMessage(
            self._t("JSON 保存目录已设置为：{path}", path=self.repo.ann_dir)
        )

    def reset_workspace(self, message):
        self.idx = -1
        self.img = None
        self.data = None
        self.images = []
        self._doc_cache.clear()
        self.files.clear()
        self.canvas.set_doc(QtGui.QPixmap(), None)
        self.regions.clear()
        self.clear_region()
        self.dirty = False
        self.update_json_dir_info()
        self.title()
        self.statusBar().showMessage(message)

    def load_dir(self, d):
        if not self.confirm_unsaved_changes(self._t("切换标注文件夹")):
            return
        self._doc_cache.clear()
        self.repo.set_dirs(d, self.repo.ann_dir)
        self.images = self.repo.images()
        if not self.images:
            self.reset_workspace(self._t("目录中没有图像：{path}", path=d))
            return
        self.refresh_file_list()
        self.update_json_dir_info()
        self.skip_unsaved_prompt_once = True
        self.files.setCurrentRow(0)
        self.statusBar().showMessage(
            self._t("已加载 {count} 张图像", count=len(self.images))
        )

    def open_image_file(self, path):
        path = Path(path)
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                self._t("打开失败"),
                self._t("图像文件不存在：{path}", path=path),
            )
            return
        if not self.confirm_unsaved_changes(self._t("打开图像")):
            return
        self._doc_cache.clear()
        self.repo.set_dirs(path.parent, self.repo.ann_dir)
        self.images = [path]
        self.refresh_file_list()
        self.update_json_dir_info()
        self.skip_unsaved_prompt_once = True
        self.files.setCurrentRow(0)
        self.statusBar().showMessage(self._t("已打开单张图像：{name}", name=path.name))

    def fit(self):
        if self.canvas.pix.isNull():
            return
        vp = self.scroll.viewport().size()
        sw = max(0.1, (vp.width() - 24) / self.canvas.pix.width())
        sh = max(0.1, (vp.height() - 24) / self.canvas.pix.height())
        self.canvas.set_scale(min(sw, sh, 1.0))

    def zoom_in(self):
        if self.canvas.pix.isNull():
            self.statusBar().showMessage(self._t("请先打开图像"))
            return
        self.canvas.set_scale(self.canvas.scale * 1.15)
        self.statusBar().showMessage(
            self._t("缩放比例：{scale:.2f}x", scale=self.canvas.scale)
        )

    def zoom_out(self):
        if self.canvas.pix.isNull():
            self.statusBar().showMessage(self._t("请先打开图像"))
            return
        self.canvas.set_scale(self.canvas.scale / 1.15)
        self.statusBar().showMessage(
            self._t("缩放比例：{scale:.2f}x", scale=self.canvas.scale)
        )

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.apply_native_titlebar_theme)

    def apply_native_titlebar_theme(self):
        if sys.platform != "win32":
            return
        app = QtWidgets.QApplication.instance()
        if app is None or app.platformName().lower() == "offscreen":
            return
        try:
            import ctypes
            from ctypes import wintypes

            def color_ref(hex_color):
                value = hex_color.lstrip("#")
                red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
                return red | (green << 8) | (blue << 16)

            hwnd = wintypes.HWND(int(self.winId()))
            dwmapi = ctypes.windll.dwmapi
            for attribute, color in (
                (34, "#102f32"),  # window border
                (35, "#193f43"),  # caption background
                (36, "#ffffff"),  # caption text
            ):
                color_value = ctypes.c_int(color_ref(color))
                dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(color_value),
                    ctypes.sizeof(color_value),
                )
        except (AttributeError, OSError, ValueError):
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.img and self.canvas.scale <= 1.0:
            QtCore.QTimer.singleShot(0, self.fit)

    def request_change_row(self, row):
        if row < 0 or row >= len(self.images) or row == self.idx:
            return
        self.block = True
        self.regions.clear()
        self.clear_region()
        self.block = False
        target_name = self.images[row].name if 0 <= row < len(self.images) else ""
        if target_name:
            self.statusBar().showMessage(
                self._t("正在切换图像：{name}", name=target_name)
            )
        self._pending_row_change = row
        if self._image_change_in_progress:
            return
        QtCore.QTimer.singleShot(0, self._process_pending_row_change)

    def sync_file_selection_to_current(self):
        if not hasattr(self, "files"):
            return
        self.files.blockSignals(True)
        try:
            if 0 <= self.idx < len(self.images):
                if self.files.currentRow() != self.idx:
                    self.files.setCurrentRow(self.idx)
            else:
                self.files.setCurrentRow(-1)
        finally:
            self.files.blockSignals(False)

    def _process_pending_row_change(self):
        if self._image_change_in_progress:
            return
        row = self._pending_row_change
        self._pending_row_change = None
        if row is None:
            return
        self._image_change_in_progress = True
        try:
            self.change_row(row)
        finally:
            self._image_change_in_progress = False
        if self._pending_row_change is not None and self._pending_row_change != self.idx:
            QtCore.QTimer.singleShot(0, self._process_pending_row_change)

    def change_row(self, row):
        if row < 0 or row >= len(self.images) or row == self.idx:
            return
        previous_row = self.idx
        if self.skip_unsaved_prompt_once:
            self.skip_unsaved_prompt_once = False
        elif not self.confirm_unsaved_changes(self._t("切换图像")):
            self.sync_file_selection_to_current()
            self._pending_row_change = None
            return
        next_img = self.images[row]
        pix = QtGui.QPixmap(str(next_img))
        if pix.isNull():
            self.sync_file_selection_to_current()
            self.statusBar().showMessage(
                self._t("无法打开图像：{path}", path=next_img)
            )
            return
        try:
            next_data = self.load_annotation_doc(next_img, pix.width(), pix.height())
        except Exception as exc:
            self.sync_file_selection_to_current()
            QtWidgets.QMessageBox.warning(
                self,
                self._t("打开标注失败"),
                self._t(
                    "无法加载标注文件：\n{name}\n\n{error}",
                    name=next_img.name,
                    error=exc,
                ),
            )
            self.statusBar().showMessage(
                self._t("无法加载标注：{name}", name=next_img.name)
            )
            return
        self.idx = row
        self.img = next_img
        self.data = next_data
        self._sam_rgb_cache_key = None
        self._sam_rgb_cache_image = None
        self.sam_segmenter.clear_image_cache()
        self.block = True
        self.canvas.set_doc(pix, self.data)
        self.block = False
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        self.normalize_loaded_shape_labels()
        self.sync_categories_from_shapes()
        self.block = True
        self.refresh_regions()
        self.clear_region()
        self.block = False
        self.dirty = False
        self.update_annotation_mode_buttons()
        self.fit()
        self.title()
        self.sync_file_selection_to_current()
        self.update_file_item_status_by_row(previous_row)
        self.update_file_item_status_by_row(row)
        self.statusBar().showMessage(self._t("当前图像：{name}", name=self.img.name))

    def step(self, n):
        if not self.images:
            return
        target = max(0, min(self.idx + n, len(self.images) - 1))
        if target != self.idx:
            self.files.setCurrentRow(target)

    def image_annotation_exists(self, img):
        ann_path = self.repo.ann_path(img) if img else None
        return bool(ann_path and ann_path.exists())

    def file_status_icon(self, checked):
        key = bool(checked)
        if key in self._file_status_icons:
            return self._file_status_icons[key]
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor("#94a3b8"), 1))
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.drawRoundedRect(0, 0, 15, 15, 3, 3)
        if checked:
            painter.setPen(QtGui.QPen(QtGui.QColor("#dc2626"), 1.8))
            painter.drawLine(4, 8, 7, 11)
            painter.drawLine(7, 11, 12, 4)
        painter.end()
        icon = QtGui.QIcon(pixmap)
        self._file_status_icons[key] = icon
        return icon

    def update_file_item_widget(self, item, img):
        checked = self.image_annotation_exists(img)
        item.setText(img.name)
        item.setToolTip(img.name)
        item.setIcon(self.file_status_icon(checked))
        item.setSizeHint(QtCore.QSize(0, 30))

    def update_file_item_status_by_row(self, row):
        if row < 0 or row >= len(self.images):
            return
        item = self.files.item(row)
        if item is None:
            return
        self.update_file_item_widget(item, self.images[row])

    def refresh_file_list(self):
        current_name = self.img.name if self.img else None
        self.files.blockSignals(True)
        self.files.clear()
        selected_row = -1
        for index, img in enumerate(self.images):
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, img.name)
            self.update_file_item_widget(item, img)
            self.files.addItem(item)
            if current_name and img.name == current_name:
                selected_row = index
        if selected_row >= 0:
            self.files.setCurrentRow(selected_row)
        self.files.blockSignals(False)

    def refresh_regions(self):
        selected_sid = self.canvas.sel
        current_category = self.current_category()
        self.block = True
        self.regions.clear()
        if not self.data:
            self.block = False
            return
        selected_row = -1
        for index, shape in enumerate(self.data.get("shapes", []), start=1):
            self.ensure_shape_label(shape, fallback_category=current_category)
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, shape["id"])
            self.regions.addItem(item)
            selected = bool(selected_sid and shape["id"] == selected_sid)
            self.update_region_item_widget(item, shape, index, selected=selected)
            if selected_sid and shape["id"] == selected_sid:
                selected_row = self.regions.count() - 1
        if selected_row >= 0:
            self.regions.setCurrentRow(selected_row)
        self.block = False

    def update_region_item_widget(self, item, shape, index, selected=False):
        del selected
        text = f"[{index}] {shape_display_name(shape, self.ui_language)}"
        item.setText(text)
        item.setToolTip(text)
        item.setSizeHint(QtCore.QSize(0, 30))

    def clear_region(self):
        return

    def shape(self, sid=None):
        sid = sid if sid is not None else self.canvas.sel
        if not self.data or not sid:
            return None
        for shape in self.data.get("shapes", []):
            if shape.get("id") == sid:
                return shape
        return None

    def on_canvas_selected(self, sid):
        self.block = True
        row = -1
        for i in range(self.regions.count()):
            if self.regions.item(i).data(QtCore.Qt.UserRole) == sid:
                row = i
                break
        self.refresh_regions()
        self.regions.setCurrentRow(row)
        self.block = False

    def on_region_list(self, current, previous):
        del previous
        if self.block:
            return
        sid = current.data(QtCore.Qt.UserRole) if current else None
        self.canvas.sel = sid
        self.canvas.selected.emit(sid or "")
        self.canvas.update()

    def on_region_item_double_clicked(self, item):
        del item
        self.edit_selected_region()

    def on_region_edit(self, _text=None):
        del _text

    def on_canvas_changed(self):
        if self.block or not self.data:
            return
        self.refresh_regions()
        if self.canvas.sel:
            self.on_canvas_selected(self.canvas.sel)
        self.mark_dirty()

    def _assign_current_category_to_shape(self, shape):
        category = self._ensure_category_selected(show_message=True)
        if not category:
            return False
        shape["label"] = category
        attrs = shape.setdefault("attributes", {})
        attrs["object_category"] = category
        self.ensure_category_color(category)
        self.apply_category_color_to_shape(shape, category)
        return True

    def edit_selected_region(self):
        if not self.canvas.sel:
            return
        self.canvas.set_mode("select")
        self.update_annotation_mode_buttons()
        self.canvas.setFocus()
        self.statusBar().showMessage(
            self._t("已进入区域修改模式：可拖动区域或拖动顶点进行修改")
        )

    def apply_current_category_to_selected_region(self):
        shape = self.shape()
        if not shape:
            return
        if not self._assign_current_category_to_shape(shape):
            return
        self.refresh_regions()
        self.mark_dirty()
        self.statusBar().showMessage(
            self._t(
                "已将当前类别应用到选中区域：{category}",
                category=shape.get("label", ""),
            )
        )

    def on_region_context_menu(self, pos):
        item = self.regions.itemAt(pos)
        if item is None:
            return
        self.regions.setCurrentItem(item)
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction(self._t("修改选中区域"))
        apply_category_action = menu.addAction(self._t("将当前类别应用到该区域"))
        chosen = menu.exec_(self.regions.viewport().mapToGlobal(pos))
        if chosen is edit_action:
            self.edit_selected_region()
        elif chosen is apply_category_action:
            self.apply_current_category_to_selected_region()

    def _delete_shapes_by_ids(self, shape_ids):
        if not self.data:
            return
        sid_set = {str(sid) for sid in shape_ids}
        self.data["shapes"] = [shape for shape in self.data.get("shapes", []) if str(shape.get("id", "")) not in sid_set]
        if self.canvas.sel in sid_set:
            self.canvas.sel = None
            self.canvas.selected.emit("")

    def on_shape_created(self, sid):
        shape = self.shape(sid)
        if not shape:
            return
        if not self._assign_current_category_to_shape(shape):
            self._delete_shapes_by_ids([sid])
            self.refresh_regions()
            self.clear_region()
            self.canvas.update()
            return
        self.refresh_regions()
        self.canvas.sel = sid
        self.on_canvas_selected(sid)
        self.mark_dirty()

    def choose_sam_checkpoint(self):
        start_dir = str(self.sam_segmenter.checkpoint.parent) if self.sam_segmenter.checkpoint else str(Path.cwd())
        file_path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self._t("选择 SAM 权重文件"),
            start_dir,
            self._t("SAM 模型 (*.pth *.pt);;所有文件 (*)"),
        )
        if not file_path:
            return False
        self.sam_segmenter.set_checkpoint(file_path)
        self.statusBar().showMessage(
            self._t("SAM 权重已设置：{name}", name=Path(file_path).name)
        )
        return True

    def ensure_sam_available(self, show_message=False):
        error = self.sam_segmenter.availability_error()
        if error == "missing_checkpoint":
            if not self.choose_sam_checkpoint():
                if show_message:
                    QtWidgets.QMessageBox.information(
                        self,
                        self._t("未配置 SAM 权重"),
                        self._t("请先选择 SAM 权重文件后再使用 SAM 分割。"),
                    )
                return False
            error = self.sam_segmenter.availability_error()
        if error:
            if show_message:
                QtWidgets.QMessageBox.warning(
                    self,
                    self._t("SAM 不可用"),
                    self.sam_segmenter.help_message(error, self.ui_language),
                )
            return False
        if not self.sam_segmenter.is_loaded():
            return self._load_sam_predictor_with_feedback(show_message=show_message)
        return True

    def _load_sam_predictor_with_feedback(self, show_message=False):
        signature = self.sam_segmenter.current_signature()
        checkpoint_name = (
            Path(str(self.sam_segmenter.checkpoint)).name
            if self.sam_segmenter.checkpoint
            else self._t("未配置")
        )
        progress = QtWidgets.QProgressDialog(
            self._t("正在加载 SAM 权重，请稍候..."), None, 0, 0, self
        )
        progress.setWindowTitle(self._t("加载 SAM 权重"))
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setLabelText(
            self._t(
                "正在加载 {name}\n首次加载可能需要几秒到几十秒。",
                name=checkpoint_name,
            )
        )
        progress.setMinimumWidth(460)
        label = progress.findChild(QtWidgets.QLabel)
        if label is not None:
            label.setMinimumWidth(400)
            label.setWordWrap(True)
        progress.show()
        QtWidgets.QApplication.processEvents()
        try:
            self.sam_segmenter._ensure_predictor()
        except Exception as exc:
            progress.close()
            if show_message:
                QtWidgets.QMessageBox.warning(self, self._t("SAM 加载失败"), str(exc))
            return False
        progress.close()
        if self._sam_loaded_notice_signature != signature:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle(self._t("SAM 加载完成"))
            msg_box.setText(
                self._t(
                    "SAM 权重已加载完成：\n{name}\n\n现在可以使用“SAM 分割”进行标注。",
                    name=checkpoint_name,
                )
            )
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box.setMinimumWidth(460)
            msg_box.exec_()
            self._sam_loaded_notice_signature = signature
        return True

    def _sam_image_key(self):
        if not self.img:
            return None
        try:
            stat = self.img.stat()
            return (str(self.img.resolve()), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return str(self.img)

    def _sam_image_rgb(self):
        image_key = self._sam_image_key()
        if self._sam_rgb_cache_key != image_key or self._sam_rgb_cache_image is None:
            self._sam_rgb_cache_image = Image.open(self.img).convert("RGB")
            self._sam_rgb_cache_key = image_key
        return self._sam_rgb_cache_image

    def on_sam_box_requested(self, box_xyxy):
        if not self.img or not self.data:
            return
        if not self.ensure_sam_available(show_message=True):
            self.statusBar().showMessage(self._t("SAM 分割未就绪"))
            return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            image_rgb = self._sam_image_rgb()
            polygon_points = self.sam_segmenter.segment_polygon(image_rgb, box_xyxy, image_key=self._sam_image_key())
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, self._t("SAM 分割失败"), str(exc))
            self.statusBar().showMessage(self._t("SAM 分割失败"))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        preview_regions = polygon_points if polygon_points and isinstance(polygon_points[0][0], list) else [polygon_points]
        if preview_regions:
            self.on_sam_preview_accepted(preview_regions)
            self.canvas.clear_sam_session()
            self.canvas.update()
            self.statusBar().showMessage(
                self._t("SAM 框分割已生成 {count} 个区域", count=len(preview_regions))
            )

    def on_sam_points_changed(self, positive_points, negative_points):
        if not self.img or not self.data:
            return
        if not self.ensure_sam_available(show_message=True):
            self.statusBar().showMessage(self._t("SAM 分割未就绪"))
            return
        if not positive_points:
            self.canvas.set_sam_preview([])
            self.statusBar().showMessage(
                self._t("SAM 点分割至少需要一个左键正样本点")
            )
            return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            image_rgb = self._sam_image_rgb()
            polygon_regions = self.sam_segmenter.segment_polygon_by_points(
                image_rgb,
                positive_points,
                negative_points,
                image_key=self._sam_image_key(),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, self._t("SAM 分割失败"), str(exc))
            self.statusBar().showMessage(self._t("SAM 分割失败"))
            self.canvas.set_sam_preview([])
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.canvas.set_sam_preview(polygon_regions)
        if polygon_regions:
            self.statusBar().showMessage(
                self._t("SAM 预览已更新，可继续加点或拖拽顶点微调，按 Enter 确认")
            )

    def on_sam_preview_accepted(self, regions):
        if not regions:
            return
        if not self._ensure_category_selected(show_message=True):
            return
        created_sids = []
        self.defer_auto_save = True
        try:
            for region in regions:
                sid = self.canvas.add_polygon_shape(region, label="", emit_created=False)
                if sid:
                    created_sids.append(sid)
            for sid in created_sids:
                shape = self.shape(sid)
                if shape:
                    self._assign_current_category_to_shape(shape)
        finally:
            self.defer_auto_save = False
        if created_sids:
            self.refresh_regions()
            self.canvas.sel = created_sids[0]
            self.on_canvas_selected(created_sids[0])
            self.mark_dirty()
            if self.auto_save_enabled and self.dirty:
                self.save()
            self.statusBar().showMessage(
                self._t("SAM 区域已确认，共生成 {count} 个区域", count=len(created_sids))
            )

    def set_sam_submode(self, mode):
        self.current_sam_mode = mode if mode in {"sam_point", "sam_box"} else "sam_point"
        self.sam_point_action.setChecked(self.current_sam_mode == "sam_point")
        self.sam_box_action.setChecked(self.current_sam_mode == "sam_box")
        self.set_mode(self.current_sam_mode)

    def update_annotation_mode_buttons(self):
        current_mode = getattr(self.canvas, "mode", "select")
        self.rectangle_action.setChecked(current_mode == "rectangle")
        self.polygon_action.setChecked(current_mode == "polygon")
        self.sam_mode_button.setChecked(current_mode in {"sam_point", "sam_box"})
        if current_mode == "sam_box":
            self.current_sam_mode = "sam_box"
        elif current_mode == "sam_point":
            self.current_sam_mode = "sam_point"
        self.sam_point_action.setChecked(self.current_sam_mode == "sam_point")
        self.sam_box_action.setChecked(self.current_sam_mode == "sam_box")

    def set_mode(self, mode):
        if not self.img or not self.data:
            self.statusBar().showMessage(self._t("请先打开图像后再开始标注。"))
            return
        if mode in {"rectangle", "polygon", "sam_point", "sam_box"} and not self._ensure_category_selected(show_message=True):
            self.canvas.set_mode("select")
            self.update_annotation_mode_buttons()
            self.statusBar().showMessage(
                self._t("请先在右侧选择标注类别，再开始标注。")
            )
            return
        if mode in {"sam_point", "sam_box"} and not self.ensure_sam_available(show_message=True):
            self.statusBar().showMessage(self._t("SAM 分割当前不可用"))
            return
        self.canvas.set_mode(mode)
        self.update_annotation_mode_buttons()

    def undo_mode_step(self):
        if self.canvas.mode == "sam_point":
            self.canvas.undo_sam_point()
            return
        self.canvas.undo_polygon_point()

    def pause_annotation(self):
        self.canvas.pause_annotation()
        self.update_annotation_mode_buttons()
        self.statusBar().showMessage(self._t("已暂停标注"))

    def del_region(self):
        if self.canvas.delete_selected_vertex():
            self.refresh_regions()
            self.mark_dirty()
            return
        if self.canvas.delete_selected():
            self.refresh_regions()
            self.clear_region()
            self.mark_dirty()
            self.statusBar().showMessage(self._t("已删除选中区域"))

    def save(self):
        if not self.img or not self.data:
            return False
        current_category = self.current_category()
        for shape in self.data.get("shapes", []):
            self.ensure_shape_label(shape, fallback_category=current_category)
        if self.repo.ann_dir is None:
            QtWidgets.QMessageBox.warning(
                self,
                self._t("未设置 JSON 保存目录"),
                self._t("请先单独指定 JSON 保存目录后再保存。"),
            )
            self.statusBar().showMessage(self._t("请先指定 JSON 保存目录"))
            return False
        self.repo.ann_dir.mkdir(parents=True, exist_ok=True)
        path = self.repo.ann_path(self.img)
        export_data = export_labelme_like_json(self.img, self.data)
        path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._doc_cache[self._doc_cache_key(self.img)] = json.loads(json.dumps(export_data, ensure_ascii=False))
        self.dirty = False
        self.upsert_json_file_list_item(path)
        self.update_json_progress_display()
        self.update_file_item_status_by_row(self.idx)
        self.title()
        self.statusBar().showMessage(self._t("已保存标注：{path}", path=path))
        return True

    def closeEvent(self, event):
        if self.confirm_unsaved_changes(self._t("关闭窗口")):
            event.accept()
        else:
            event.ignore()
