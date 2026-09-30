import re

from PyQt5 import QtCore, QtGui



IMG_SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SHAPE_LINE_COLOR = QtGui.QColor("#0891b2")
CATEGORY_COLOR_PALETTE = [
    "#0891b2",
    "#dc2626",
    "#16a34a",
    "#7c3aed",
    "#d97706",
    "#2563eb",
    "#db2777",
    "#0f766e",
    "#9333ea",
    "#b45309",
]

CATEGORY_ITEM_COLOR_ROLE = QtCore.Qt.UserRole
CATEGORY_ITEM_NAME_ROLE = QtCore.Qt.UserRole + 1
LINE_WIDTH_OPTIONS = [
    ("0.1%", 0.001),
    ("0.2%", 0.002),
    ("0.5%", 0.005),
    ("0.7%", 0.007),
    ("1.0%", 0.010),
]
UI_COLOR = {
    "text_primary": "#243234",
    "text_toolbar_hover": "#ffffff",
    "text_title_blue": "#273a3b",
    "text_title_purple": "#273a3b",
    "text_button_blue": "#29413f",
    "text_button_purple": "#29413f",
    "text_muted": "#778486",
    "toolbar_bg": "#193f43",
    "toolbar_border": "#102f32",
    "toolbar_button_bg": "#193f43",
    "toolbar_button_border": "#4f7375",
    "toolbar_button_hover": "#28575a",
    "toolbar_button_hover_border": "#739596",
    "toolbar_button_pressed": "#123438",
    "toolbar_button_pressed_border": "#8badac",
    "toolbar_button_disabled_bg": "#29484b",
    "toolbar_button_disabled_border": "#496669",
    "left_group_bg": "#f8faf9",
    "left_group_border": "#d4ddda",
    "left_title_bg": "#f8faf9",
    "left_placeholder_bg": "#f1f5f3",
    "left_placeholder_border": "#c7d3cf",
    "left_button_border": "#b9cbc6",
    "left_button_hover_bg": "#e8f1ee",
    "left_button_hover_border": "#86aaa2",
    "left_button_pressed_bg": "#dceae6",
    "left_button_pressed_border": "#6f9990",
    "json_group_bg": "#f8faf9",
    "json_group_border": "#d4ddda",
    "json_placeholder_bg": "#f1f5f3",
    "json_placeholder_border": "#c7d3cf",
    "json_button_border": "#b9cbc6",
    "json_button_hover_bg": "#e8f1ee",
    "json_button_hover_border": "#86aaa2",
    "json_button_pressed_bg": "#dceae6",
    "json_button_pressed_border": "#6f9990",
    "file_list_bg": "#ffffff",
    "file_list_border": "#d6dfdc",
    "file_item_bg": "#ffffff",
    "file_item_border": "#e3e9e7",
    "file_item_selected_bg": "#e3efeb",
    "file_item_selected_border": "#83aaa1",
    "json_list_bg": "#ffffff",
    "json_list_border": "#d6dfdc",
    "step1_group_bg": "#eff4f8",
    "step1_group_border": "#cfd9e3",
    "step1_title_bg": "#ffffff",
    "step1_title_border": "#cfd9e3",
    "step2_group_bg": "#f2f6f1",
    "step2_group_border": "#d3ddcf",
    "step2_title_bg": "#ffffff",
    "step2_title_border": "#d3ddcf",
    "step3_group_bg": "#f5f3f7",
    "step3_group_border": "#d9d2e0",
    "step3_title_bg": "#ffffff",
    "step3_title_border": "#d9d2e0",
    "step_card_bg": "#ffffff",
    "step_card_border": "#dce4eb",
    "step_card_title_bg": "#fafbfd",
    "step_card_title_border": "#dce4eb",
    "step_inner_text": "#566466",
    "step_section_title_text": "#304244",
    "action_button_bg": "#dcebe7",
    "action_button_border": "#8db1a9",
    "action_button_hover": "#cee2dd",
    "action_button_hover_border": "#709c93",
    "action_button_pressed": "#bfd8d2",
    "action_button_pressed_border": "#5f8b82",
    "action_button_disabled_bg": "#edf1f0",
    "action_button_disabled_border": "#d7dfdd",
}


def normalize_qt_css_colors(colors):
    normalized = {}
    for key, value in colors.items():
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{8}", value):
            hex_value = value[1:]
            value = f"#{hex_value[6:8]}{hex_value[:6]}"
        normalized[key] = value
    return normalized


UI_COLOR = normalize_qt_css_colors(UI_COLOR)

LANGUAGE_ZH = "zh_CN"
LANGUAGE_EN = "en_US"
SUPPORTED_LANGUAGES = (LANGUAGE_ZH, LANGUAGE_EN)

# Chinese is the canonical UI copy. English translations are centralized here
# so language switching never touches annotation data or model behaviour.
EN_TEXT = {
    "未加载图像": "No image loaded",
    "未命名区域": "Unnamed instance",
    "标注文件列表": "Images",
    "打开标注文件夹": "Open Image Folder",
    "JSON 文件保存列表": "Saved JSON Annotations",
    "指定 JSON 文件保存路径": "Choose JSON Output Folder",
    "未设置 JSON 保存路径": "JSON output folder is not set",
    "已保存标注：{saved} / {total}": "Saved annotations: {saved} / {total}",
    "已标注区域": "Annotated Instances",
    "输入新类别名称": "Enter a new class name",
    "添加": "Add",
    "当前类别": "Current class",
    "未选择": "Not selected",
    "编辑当前选中区域的标签": "Edit the selected instance label",
    "标签": "Label",
    "标注类别": "Annotation Classes",
    "选择模式：可拖动区域；矩形：拖拽；多边形：左键加点":
        "Select: drag an instance; Rectangle: drag; Polygon: left-click to add vertices",
    "打开单张图像": "Open Image",
    "JSON 保存目录": "JSON Output Folder",
    "打开文件": "Open",
    "自动保存": "Auto Save",
    "手动保存": "Save Now",
    "保存方式": "Save",
    "线粗细": "Contour",
    "线粗细：选择标注轮廓线粗细": "Set the annotation contour width",
    "上一张": "Previous",
    "下一张": "Next",
    "矩形": "Rectangle",
    "多边形": "Polygon",
    "返回上一步": "Undo Step",
    "暂停标注": "Pause Annotation",
    "删除区域": "Delete Instance",
    "标注": "Annotate",
    "编辑": "Edit",
    "视图": "View",
    "© {year} 中国农业科学院农业信息研究所": "© {year} Agricultural Information Institute, CAAS",
    "缩小": "Zoom Out",
    "放大": "Zoom In",
    "缩小（Ctrl+滚轮下）": "Zoom Out (Ctrl+Wheel Down)",
    "放大（Ctrl+滚轮上）": "Zoom In (Ctrl+Wheel Up)",
    "点分割 (E)": "Point Prompt (E)",
    "框分割 (Q)": "Box Prompt (Q)",
    "SAM 分割": "SAM",
    "SAM 分割：下拉选择点分割或框分割":
        "Choose point-prompt or box-prompt segmentation",
    "中文 / EN": "中文 / EN",
    "中文": "中文",
    "English": "English",
    "界面语言已切换为中文": "Interface language changed to English",
    "当前标注线粗细：图像长边的 {label}":
        "Contour width: {label} of the image long side",
    "当前标注类别已切换为：{category}": "Current annotation class: {category}",
    "当前标注类别已切换为：{category}  快捷键：{shortcut}":
        "Current annotation class: {category}  Shortcut: {shortcut}",
    "设置类别颜色：{category}": "Set class color: {category}",
    "类别颜色已更新：{category} -> {color}": "Class color updated: {category} -> {color}",
    "已删除类别：{category}": "Class deleted: {category}",
    "未设置标注类别": "No Annotation Class",
    "请先在右侧“标注类别”中添加并选择一个类别，再开始标注。":
        "Add and select a class in the Annotation Classes panel before annotating.",
    "存在未保存修改": "Unsaved Changes",
    "当前图像有未保存修改，是否在{action}前保存？":
        "This image has unsaved changes. Save before {action}?",
    "保存": "Save",
    "不保存": "Discard",
    "取消": "Cancel",
    "选择标注文件夹": "Select Image Folder",
    "图像文件 (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)":
        "Image Files (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp)",
    "选择 JSON 保存目录": "Select JSON Output Folder",
    "JSON 保存目录已设置为：{path}": "JSON output folder set to: {path}",
    "切换标注文件夹": "switching image folders",
    "目录中没有图像：{path}": "No images found in: {path}",
    "已加载 {count} 张图像": "Loaded {count} images",
    "打开失败": "Open Failed",
    "图像文件不存在：{path}": "Image file does not exist: {path}",
    "打开图像": "opening another image",
    "已打开单张图像：{name}": "Opened image: {name}",
    "请先打开图像": "Open an image first",
    "缩放比例：{scale:.2f}x": "Zoom: {scale:.2f}x",
    "正在切换图像：{name}": "Switching to image: {name}",
    "切换图像": "switching images",
    "无法打开图像：{path}": "Cannot open image: {path}",
    "打开标注失败": "Annotation Load Failed",
    "无法加载标注文件：\n{name}\n\n{error}":
        "Cannot load the annotation file:\n{name}\n\n{error}",
    "无法加载标注：{name}": "Cannot load annotation: {name}",
    "当前图像：{name}": "Current image: {name}",
    "已进入区域修改模式：可拖动区域或拖动顶点进行修改":
        "Instance edit mode: drag the instance or one of its vertices",
    "已将当前类别应用到选中区域：{category}":
        "Applied current class to the selected instance: {category}",
    "修改选中区域": "Edit Selected Instance",
    "将当前类别应用到该区域": "Apply Current Class",
    "选择 SAM 权重文件": "Select SAM Checkpoint",
    "SAM 模型 (*.pth *.pt);;所有文件 (*)": "SAM Model (*.pth *.pt);;All Files (*)",
    "SAM 权重已设置：{name}": "SAM checkpoint set: {name}",
    "未配置 SAM 权重": "SAM Checkpoint Not Configured",
    "请先选择 SAM 权重文件后再使用 SAM 分割。":
        "Select a SAM checkpoint before using SAM segmentation.",
    "SAM 不可用": "SAM Unavailable",
    "未配置": "Not configured",
    "正在加载 SAM 权重，请稍候...": "Loading the SAM checkpoint...",
    "加载 SAM 权重": "Loading SAM",
    "正在加载 {name}\n首次加载可能需要几秒到几十秒。":
        "Loading {name}\nInitial loading may take several seconds.",
    "SAM 加载失败": "SAM Load Failed",
    "SAM 加载完成": "SAM Ready",
    "SAM 权重已加载完成：\n{name}\n\n现在可以使用“SAM 分割”进行标注。":
        "SAM checkpoint loaded:\n{name}\n\nSAM segmentation is now available.",
    "SAM 分割未就绪": "SAM segmentation is not ready",
    "SAM 分割失败": "SAM Segmentation Failed",
    "SAM 框分割已生成 {count} 个区域": "SAM box prompt created {count} instance(s)",
    "SAM 点分割至少需要一个左键正样本点":
        "SAM point prompting requires at least one positive left-click",
    "SAM 预览已更新，可继续加点或拖拽顶点微调，按 Enter 确认":
        "SAM preview updated; add prompts or refine vertices, then press Enter",
    "SAM 区域已确认，共生成 {count} 个区域": "Confirmed {count} SAM instance(s)",
    "请先打开图像后再开始标注。": "Open an image before starting annotation.",
    "请先在右侧选择标注类别，再开始标注。":
        "Select an annotation class before starting.",
    "SAM 分割当前不可用": "SAM segmentation is currently unavailable",
    "已暂停标注": "Annotation paused",
    "已删除选中区域": "Selected instance deleted",
    "未设置 JSON 保存目录": "JSON Output Folder Not Set",
    "请先单独指定 JSON 保存目录后再保存。":
        "Choose a JSON output folder before saving.",
    "请先指定 JSON 保存目录": "Choose a JSON output folder first",
    "已保存标注：{path}": "Annotation saved: {path}",
    "关闭窗口": "closing the window",
    "当前保存方式：{mode}": "Save mode: {mode}",
    "你好，请在左侧选择图像开始标注工作":
        "Open an image from the left panel to begin annotation",
    "已删除当前 SAM 预览区域": "Current SAM preview instance deleted",
    "已删除当前 SAM 预览顶点": "Current SAM preview vertex deleted",
    "矩形区域不支持删除单个顶点": "Rectangle vertices cannot be deleted individually",
    "多边形至少需要保留 3 个顶点": "A polygon must retain at least three vertices",
    "已删除当前顶点": "Current vertex deleted",
    "SAM 点分割：左键添加保留点，右键添加排除点，拖拽顶点微调，Enter 确认":
        "SAM point prompt: left-click positive, right-click negative, drag vertices, Enter to confirm",
    "矩形：按住左键拖拽框选，松开完成":
        "Rectangle: hold and drag the left mouse button, then release",
    "多边形：左键加点，点击首点或按 Enter 闭合，Esc 取消":
        "Polygon: left-click vertices; click the first vertex or press Enter to close; Esc to cancel",
    "已撤销最近一个 SAM 提示点": "Last SAM prompt removed",
    "已返回多边形上一步": "Last polygon vertex removed",
    "已结束标注": "Annotation ended",
    "SAM 分割至少需要先生成一个有效预览区域":
        "Generate a valid SAM preview before confirming",
    "已向{direction}微调 SAM 预览区域": "SAM preview moved {direction}",
    "已向{direction}移动选中区域": "Selected instance moved {direction}",
    "左": "left",
    "右": "right",
    "上": "up",
    "下": "down",
    "未找到 SAM 权重文件。请先选择或传入 .pth/.pt 权重文件。":
        "SAM checkpoint not found. Select or provide a .pth/.pt checkpoint.",
    "SAM 依赖加载失败，当前环境无法启用 SAM 分割。\n\nPython: {python}\n详细异常：{detail}":
        "SAM dependencies could not be loaded.\n\nPython: {python}\nDetails: {detail}",
    "SAM 模型类型无效。当前仅支持 vit_b / vit_l / vit_h。":
        "Invalid SAM model type. Supported types: vit_b, vit_l, and vit_h.",
    "SAM 初始化失败。": "SAM initialization failed.",
}


def tr_text(language, text, **values):
    template = EN_TEXT.get(text, text) if language == LANGUAGE_EN else text
    return template.format(**values) if values else template


def blank(name, w, h):
    return {
        "tool": "StelleraSAM",
        "version": "1.0.0",
        "imagePath": name,
        "originalImageName": name,
        "previousImageName": "",
        "imageWidth": w,
        "imageHeight": h,
        "imageAttributes": {},
        "shapes": [],
    }


def normalize_shape_ids(data):
    shapes = list((data or {}).get("shapes", []) or [])
    for index, shape in enumerate(shapes, 1):
        shape["id"] = str(index)
    return data


def next_shape_id(shapes):
    max_id = 0
    for shape in shapes or []:
        try:
            max_id = max(max_id, int(str(shape.get("id", "")).strip()))
        except (TypeError, ValueError):
            continue
    return str(max_id + 1)


def natural_sort_key(value):
    text = str(value or "")
    parts = re.split(r"(\d+)", text.lower())
    return [int(part) if part.isdigit() else part for part in parts]
