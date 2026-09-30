from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from .config import (
    LANGUAGE_ZH,
    SHAPE_LINE_COLOR,
    SUPPORTED_LANGUAGES,
    next_shape_id,
    tr_text,
)


class Canvas(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    selected = QtCore.pyqtSignal(str)
    message = QtCore.pyqtSignal(str)
    shapeCreated = QtCore.pyqtSignal(str)
    samBoxRequested = QtCore.pyqtSignal(object)
    samPointsChanged = QtCore.pyqtSignal(object, object)
    samPreviewAccepted = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self.pix = QtGui.QPixmap()
        self.data = None
        self.scale = 1.0
        self.mode = "select"
        self.sel = None
        self.rect0 = None
        self.poly = []
        self.cur = None
        self.drag = None
        self.drag_dirty = False
        self.selected_vertex = None
        self.selected_sam_preview_vertex = None
        self.interactive = True
        self.shape_line_color = QtGui.QColor(SHAPE_LINE_COLOR)
        self.shape_line_ratio = 0.002
        self.pan = None
        self.sam_positive_points = []
        self.sam_negative_points = []
        self.sam_preview_regions = []
        self.sam_active_region_index = -1
        self.sam_point_history = []
        self.ui_language = LANGUAGE_ZH

    def set_ui_language(self, language):
        self.ui_language = language if language in SUPPORTED_LANGUAGES else LANGUAGE_ZH
        self.update()

    def _t(self, text, **values):
        return tr_text(self.ui_language, text, **values)

    def _handle_radius(self):
        return max(self._shape_line_width() * 1.28, 1.95 / max(self.scale, 0.1))

    def _shape_vertices(self, shape):
        pts = [QtCore.QPointF(x, y) for x, y in shape.get("points", [])]
        if shape.get("shape_type") == "rectangle" and len(pts) >= 2:
            rect = QtCore.QRectF(pts[0], pts[1]).normalized()
            return [
                QtCore.QPointF(rect.left(), rect.top()),
                QtCore.QPointF(rect.right(), rect.top()),
                QtCore.QPointF(rect.right(), rect.bottom()),
                QtCore.QPointF(rect.left(), rect.bottom()),
            ]
        return pts

    def _draw_handle(self, painter, point, selected=False, active=False, color=None):
        radius = self._handle_radius() * (1.08 if selected else 1.0)
        fill_color = QtGui.QColor(color or "#39d353")
        if active:
            outer_radius = radius * 1.42
            outer_color = QtGui.QColor("#ef4444")
            outer_color.setAlpha(235)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(outer_color)
            painter.drawEllipse(point, outer_radius, outer_radius)
            fill_color = fill_color.lighter(122)
        elif selected:
            fill_color = fill_color.lighter(108)
        painter.setPen(QtGui.QPen(QtGui.QColor("#111827"), max(0.8, self._shape_line_width() * 0.22)))
        painter.setBrush(fill_color)
        painter.drawEllipse(point, radius, radius)
        if active:
            inner_radius = radius * 0.34
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor("#111827"))
            painter.drawEllipse(point, inner_radius, inner_radius)

    def _set_rectangle_corner(self, shape, index, point):
        pts = [QtCore.QPointF(x, y) for x, y in shape.get("points", [])]
        if len(pts) < 2:
            return
        rect = QtCore.QRectF(pts[0], pts[1]).normalized()
        corners = [
            QtCore.QPointF(rect.left(), rect.top()),
            QtCore.QPointF(rect.right(), rect.top()),
            QtCore.QPointF(rect.right(), rect.bottom()),
            QtCore.QPointF(rect.left(), rect.bottom()),
        ]
        opposite = corners[(index + 2) % 4]
        new_rect = QtCore.QRectF(point, opposite).normalized()
        shape["points"] = [[new_rect.left(), new_rect.top()], [new_rect.right(), new_rect.bottom()]]

    def _set_shape_vertex(self, shape, index, point):
        if shape.get("shape_type") == "rectangle":
            self._set_rectangle_corner(shape, index, point)
            return
        if 0 <= index < len(shape.get("points", [])):
            shape["points"][index] = [point.x(), point.y()]

    def set_doc(self, pix, data):
        self.pix = pix
        self.data = data
        self.scale = 1.0
        self.sel = None
        self.rect0 = None
        self.poly = []
        self.cur = None
        self.drag = None
        self.drag_dirty = False
        self.selected_vertex = None
        self.selected_sam_preview_vertex = None
        self.pan = None
        self.clear_sam_session()
        self._sync()
        self.selected.emit("")
        self.update()

    def _sync(self):
        self.resize(self.pix.size() * self.scale if not self.pix.isNull() else QtCore.QSize(900, 640))
        self.updateGeometry()

    def sizeHint(self):
        return self.pix.size() * self.scale if not self.pix.isNull() else QtCore.QSize(900, 640)

    def set_scale(self, v):
        self.scale = max(0.1, min(v, 12))
        self._sync()

    def set_interactive(self, enabled):
        self.interactive = bool(enabled)
        if not self.interactive:
            self.rect0 = None
            self.poly = []
            self.cur = None
            self.drag = None
            self.drag_dirty = False
            self.selected_vertex = None
            self.selected_sam_preview_vertex = None
            self.pan = None
            self.clear_sam_session()
        self.update()
        self.update()

    def set_shape_line_color(self, color):
        qcolor = QtGui.QColor(color)
        if qcolor.isValid():
            self.shape_line_color = qcolor
            self.update()

    def set_shape_line_ratio(self, ratio):
        try:
            ratio = float(ratio)
        except (TypeError, ValueError):
            return
        self.shape_line_ratio = max(0.001, min(ratio, 0.02))
        self.update()

    def _shape_color(self, shape=None):
        if shape:
            saved = shape.get("line_color")
            if saved:
                qcolor = QtGui.QColor(saved)
                if qcolor.isValid():
                    return qcolor
        return QtGui.QColor(self.shape_line_color)

    def _shape_line_width(self):
        if self.pix.isNull():
            return 1.5
        long_side = max(self.pix.width(), self.pix.height())
        return max(1.0, long_side * self.shape_line_ratio)

    def _shape_geometry(self, shape):
        pts = [QtCore.QPointF(x, y) for x, y in shape.get("points", [])]
        if shape.get("shape_type") == "rectangle" and len(pts) >= 2:
            rect = QtCore.QRectF(pts[0], pts[1]).normalized()
            return rect, rect.center(), rect.width() * rect.height()
        if len(pts) >= 3:
            poly = QtGui.QPolygonF(pts)
            bounds = poly.boundingRect()
            return poly, bounds.center(), abs(self._polygon_area_points(pts))
        return None, None, 0.0

    @staticmethod
    def _polygon_area_points(points):
        area = 0.0
        for index, point in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            area += point.x() * next_point.y() - next_point.x() * point.y()
        return area * 0.5

    def _shape_label_font_size(self, area):
        if area <= 0:
            return 0.0
        return (area ** 0.5) * 0.032

    def _draw_shape_label(self, painter, shape):
        label = normalized_shape_label(shape)
        if not label:
            return
        geometry, center, area = self._shape_geometry(shape)
        if geometry is None or center is None or area <= 0:
            return
        font = QtGui.QFont("Times New Roman")
        font.setWeight(QtGui.QFont.DemiBold)
        font_size = self._shape_label_font_size(area)
        if font_size <= 0:
            return
        font.setPixelSize(max(1, int(round(font_size))))
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        text_width = metrics.horizontalAdvance(label)
        text_height = metrics.height()
        padding_x = max(10, int(round(text_height * 0.55)))
        padding_y = max(5, int(round(text_height * 0.32)))
        label_rect = QtCore.QRectF(
            center.x() - (text_width / 2) - padding_x,
            center.y() - (text_height / 2) - padding_y,
            text_width + padding_x * 2,
            text_height + padding_y * 2,
        )
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(248, 250, 252, 208))
        painter.drawRoundedRect(label_rect, 5, 5)
        painter.setPen(QtGui.QColor("#0f172a"))
        painter.drawText(label_rect, QtCore.Qt.AlignCenter, label)

    def set_mode(self, m):
        if self.mode == m:
            return
        self.mode = m
        self.rect0 = None
        self.poly = []
        self.cur = None
        self.drag = None
        self.drag_dirty = False
        self.selected_vertex = None
        self.selected_sam_preview_vertex = None
        self.pan = None
        if m != "sam_point":
            self.clear_sam_session()
        self.update()

    def clear_sam_session(self):
        self.sam_positive_points = []
        self.sam_negative_points = []
        self.sam_preview_regions = []
        self.sam_active_region_index = -1
        self.sam_point_history = []
        self.selected_sam_preview_vertex = None

    def set_sam_preview(self, regions):
        self.sam_preview_regions = [
            [[float(x), float(y)] for x, y in region]
            for region in (regions or [])
            if len(region or []) >= 3
        ]
        if self.sam_preview_regions:
            if self.sam_active_region_index < 0 or self.sam_active_region_index >= len(self.sam_preview_regions):
                self.sam_active_region_index = 0
        else:
            self.sam_active_region_index = -1
        self.update()

    def undo_polygon_point(self):
        if self.mode != "polygon" or not self.poly:
            return False
        self.poly.pop()
        if not self.poly:
            self.cur = None
        self.update()
        return True

    def pause_annotation(self):
        self.rect0 = None
        self.poly = []
        self.cur = None
        self.drag = None
        self.drag_dirty = False
        self.selected_vertex = None
        self.selected_sam_preview_vertex = None
        self.pan = None
        self.clear_sam_session()
        self.mode = "select"
        self.update()

    def active_shape(self):
        if not self.data or not self.sel:
            return None
        for s in self.data["shapes"]:
            if s["id"] == self.sel:
                return s

    def add_polygon_shape(self, points, label="polygon", emit_created=True):
        if not self.data or len(points or []) < 3:
            return ""
        shape = {
            "id": next_shape_id(self.data["shapes"]),
            "label": label,
            "shape_type": "polygon",
            "points": [[float(x), float(y)] for x, y in points],
            "line_color": self.shape_line_color.name(),
            "attributes": {},
        }
        self.data["shapes"].append(shape)
        self.sel = shape["id"]
        self.selected.emit(self.sel)
        if emit_created:
            self.shapeCreated.emit(self.sel)
        self.changed.emit()
        self.update()
        return self.sel

    def delete_selected(self):
        if not self.data or not self.sel:
            return False
        n = len(self.data["shapes"])
        self.data["shapes"] = [s for s in self.data["shapes"] if s["id"] != self.sel]
        self.sel = None
        if len(self.data["shapes"]) != n:
            self.selected.emit("")
            self.changed.emit()
            self.update()
            return True
        return False

    def nudge_selected(self, dx, dy):
        if not self.data or not self.sel:
            return False
        shape = self.active_shape()
        if not shape:
            return False
        for point in shape.get("points", []):
            point[0] += dx
            point[1] += dy
        self.changed.emit()
        self.update()
        return True

    def _nudge_step(self):
        if self.pix.isNull():
            return 1
        return max(1, int(round(self.pix.width() * 0.01)))

    def _move_sam_preview(self, dx, dy):
        if not self.sam_preview_regions:
            return False
        if 0 <= self.sam_active_region_index < len(self.sam_preview_regions):
            target_regions = [self.sam_preview_regions[self.sam_active_region_index]]
        else:
            target_regions = self.sam_preview_regions
        for region in target_regions:
            for point in region:
                point[0] += dx
                point[1] += dy
        self.update()
        return True

    def _set_sam_preview_vertex(self, region_index, point_index, point):
        if 0 <= region_index < len(self.sam_preview_regions):
            region = self.sam_preview_regions[region_index]
            if 0 <= point_index < len(region):
                region[point_index] = [point.x(), point.y()]

    def delete_selected_vertex(self):
        if self.mode in {"sam_point", "sam_box"} and self.selected_sam_preview_vertex is not None:
            region_index, point_index = self.selected_sam_preview_vertex
            if not (0 <= region_index < len(self.sam_preview_regions)):
                self.selected_sam_preview_vertex = None
                return False
            region = self.sam_preview_regions[region_index]
            if len(region) <= 3:
                del self.sam_preview_regions[region_index]
                if not self.sam_preview_regions:
                    self.sam_active_region_index = -1
                else:
                    self.sam_active_region_index = min(self.sam_active_region_index, len(self.sam_preview_regions) - 1)
                self.selected_sam_preview_vertex = None
                self.update()
                self.message.emit(self._t("已删除当前 SAM 预览区域"))
                return True
            if 0 <= point_index < len(region):
                del region[point_index]
                self.selected_sam_preview_vertex = None
                self.update()
                self.message.emit(self._t("已删除当前 SAM 预览顶点"))
                return True
            return False

        if self.selected_vertex is None or not self.data:
            return False
        sid, vertex_index = self.selected_vertex
        shape = None
        for candidate in self.data.get("shapes", []):
            if candidate.get("id") == sid:
                shape = candidate
                break
        if not shape:
            self.selected_vertex = None
            return False
        if shape.get("shape_type") == "rectangle":
            self.message.emit(self._t("矩形区域不支持删除单个顶点"))
            return False
        points = shape.get("points", [])
        if len(points) <= 3:
            self.message.emit(self._t("多边形至少需要保留 3 个顶点"))
            return False
        if 0 <= vertex_index < len(points):
            del points[vertex_index]
            self.selected_vertex = None
            self.changed.emit()
            self.update()
            self.message.emit(self._t("已删除当前顶点"))
            return True
        return False

    def _sam_preview_hit_handle(self, pt):
        if not self.sam_preview_regions:
            return None
        radius = self._handle_radius() * 1.5
        for region_index in range(len(self.sam_preview_regions) - 1, -1, -1):
            region = self.sam_preview_regions[region_index]
            for point_index, vertex_xy in enumerate(region):
                vertex = QtCore.QPointF(vertex_xy[0], vertex_xy[1])
                if QtCore.QLineF(vertex, pt).length() <= radius:
                    return region_index, point_index
        return None

    def undo_sam_point(self):
        if not self.sam_point_history:
            return False
        self.sam_point_history.pop()
        self.sam_positive_points = []
        self.sam_negative_points = []
        for kind, x, y in self.sam_point_history:
            if kind == "positive":
                self.sam_positive_points.append([x, y])
            else:
                self.sam_negative_points.append([x, y])
        self.samPointsChanged.emit(list(self.sam_positive_points), list(self.sam_negative_points))
        self.update()
        return True

    def paintEvent(self, e):
        del e
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#fcfdfd"))
        if self.pix.isNull():
            p.setPen(QtGui.QColor("#536466"))
            font = p.font()
            font.setPointSize(14)
            font.setWeight(QtGui.QFont.Medium)
            p.setFont(font)
            p.drawText(
                self.rect(),
                QtCore.Qt.AlignCenter,
                self._t("你好，请在左侧选择图像开始标注工作"),
            )
            return
        p.save()
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, self.scale < 1.0)
        p.scale(self.scale, self.scale)
        p.drawPixmap(0, 0, self.pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        base_line_width = self._shape_line_width()
        if self.data:
            for s in self.data["shapes"]:
                sel = s["id"] == self.sel
                shape_color = self._shape_color(s)
                pen = QtGui.QPen(shape_color)
                pen.setWidthF(base_line_width * (1.25 if sel else 1.0))
                pen.setStyle(QtCore.Qt.DashLine)
                p.setPen(pen)
                fill = QtGui.QColor(shape_color)
                fill.setAlpha(90 if sel else 45)
                p.setBrush(fill)
                pts = [QtCore.QPointF(x, y) for x, y in s["points"]]
                if s["shape_type"] == "rectangle" and len(pts) >= 2:
                    r = QtCore.QRectF(pts[0], pts[1]).normalized()
                    p.drawRect(r)
                elif len(pts) >= 3:
                    poly = QtGui.QPolygonF(pts)
                    p.drawPolygon(poly)
                else:
                    continue
                self._draw_shape_label(p, s)
                for vertex_index, vertex in enumerate(self._shape_vertices(s)):
                    vertex_selected = (
                        self.selected_vertex is not None
                        and self.selected_vertex[0] == s["id"]
                        and self.selected_vertex[1] == vertex_index
                    )
                    self._draw_handle(p, vertex, selected=sel, active=vertex_selected)
        if self.mode in {"rectangle", "sam_box"} and self.rect0 and self.cur:
            pen = QtGui.QPen(self.shape_line_color, base_line_width, QtCore.Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QtGui.QColor(self.shape_line_color.red(), self.shape_line_color.green(), self.shape_line_color.blue(), 40))
            preview_rect = QtCore.QRectF(self.rect0, self.cur).normalized()
            p.drawRect(preview_rect)
            for vertex in [
                QtCore.QPointF(preview_rect.left(), preview_rect.top()),
                QtCore.QPointF(preview_rect.right(), preview_rect.top()),
                QtCore.QPointF(preview_rect.right(), preview_rect.bottom()),
                QtCore.QPointF(preview_rect.left(), preview_rect.bottom()),
            ]:
                self._draw_handle(p, vertex, selected=False, active=False, color=self.shape_line_color)
        if self.mode == "polygon" and self.poly:
            p.setPen(QtGui.QPen(self.shape_line_color, base_line_width, QtCore.Qt.DashLine))
            poly = QtGui.QPolygonF(self.poly)
            if len(self.poly) >= 2:
                p.drawPolyline(poly)
            if self.cur:
                p.drawLine(self.poly[-1], self.cur)
            for idx, point in enumerate(self.poly):
                self._draw_handle(
                    p,
                    point,
                    selected=idx == 0 and len(self.poly) >= 3,
                    active=False,
                    color="#39d353" if idx == 0 and len(self.poly) >= 3 else self.shape_line_color,
                )
        if self.mode in {"sam_point", "sam_box"}:
            if self.sam_preview_regions:
                for region_index, region in enumerate(self.sam_preview_regions):
                    p.setPen(QtGui.QPen(self.shape_line_color, base_line_width, QtCore.Qt.DashLine))
                    fill = QtGui.QColor(self.shape_line_color)
                    fill.setAlpha(65 if region_index == self.sam_active_region_index else 40)
                    p.setBrush(fill)
                    preview_poly = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in region])
                    p.drawPolygon(preview_poly)
                    for point_index, point_xy in enumerate(region):
                        point = QtCore.QPointF(point_xy[0], point_xy[1])
                        selected = (
                            (
                                self.drag is not None
                                and self.drag.get("kind") == "sam_preview_vertex"
                                and self.drag.get("region_index") == region_index
                                and self.drag.get("point_index") == point_index
                            )
                            or self.selected_sam_preview_vertex == (region_index, point_index)
                        )
                        self._draw_handle(p, point, selected=region_index == self.sam_active_region_index, active=selected, color="#f59e0b")
            p.setBrush(QtCore.Qt.NoBrush)
            for point in self.sam_positive_points:
                qp = QtCore.QPointF(point[0], point[1])
                self._draw_handle(p, qp, selected=False, active=False, color="#16a34a")
            for point in self.sam_negative_points:
                qp = QtCore.QPointF(point[0], point[1])
                self._draw_handle(p, qp, selected=False, active=False, color="#dc2626")
                cross_r = self._handle_radius() * 0.85
                p.setPen(QtGui.QPen(QtGui.QColor("#dc2626"), max(1.0, base_line_width * 0.55)))
                p.drawLine(
                    QtCore.QLineF(
                        QtCore.QPointF(qp.x() - cross_r, qp.y() - cross_r),
                        QtCore.QPointF(qp.x() + cross_r, qp.y() + cross_r),
                    )
                )
                p.drawLine(
                    QtCore.QLineF(
                        QtCore.QPointF(qp.x() - cross_r, qp.y() + cross_r),
                        QtCore.QPointF(qp.x() + cross_r, qp.y() - cross_r),
                    )
                )
        p.restore()

    def pos2img(self, pos):
        if self.pix.isNull():
            return QtCore.QPointF(0, 0)
        return QtCore.QPointF(
            max(0, min(pos.x() / self.scale, self.pix.width() - 1)),
            max(0, min(pos.y() / self.scale, self.pix.height() - 1)),
        )

    def hit(self, pt):
        if not self.data:
            return None
        for s in reversed(self.data["shapes"]):
            pts = [QtCore.QPointF(x, y) for x, y in s["points"]]
            if s["shape_type"] == "rectangle" and len(pts) >= 2 and QtCore.QRectF(pts[0], pts[1]).normalized().contains(pt):
                return s["id"]
            if s["shape_type"] == "polygon" and len(pts) >= 3 and QtGui.QPolygonF(pts).containsPoint(pt, QtCore.Qt.OddEvenFill):
                return s["id"]
        return None

    def hit_handle(self, pt):
        if not self.data:
            return None
        radius = self._handle_radius() * 1.5
        for s in reversed(self.data["shapes"]):
            vertices = self._shape_vertices(s)
            for index, vertex in enumerate(vertices):
                if QtCore.QLineF(vertex, pt).length() <= radius:
                    return s["id"], index
        return None

    def _poly_first_hit(self, pt):
        if len(self.poly) < 3:
            return False
        return QtCore.QLineF(self.poly[0], pt).length() <= self._handle_radius() * 1.5

    def mousePressEvent(self, e):
        if self.pix.isNull():
            return
        self.setFocus()
        pt = self.pos2img(e.pos())
        self.cur = pt
        if not self.interactive:
            if e.button() == QtCore.Qt.LeftButton:
                self.pan = {"pos": e.pos()}
            return
        if self.mode == "sam_point":
            if e.button() == QtCore.Qt.LeftButton:
                preview_handle = self._sam_preview_hit_handle(pt)
                if preview_handle is not None:
                    self.sam_active_region_index = preview_handle[0]
                    self.selected_sam_preview_vertex = preview_handle
                    self.selected_vertex = None
                    self.drag = {"kind": "sam_preview_vertex", "region_index": preview_handle[0], "point_index": preview_handle[1]}
                    self.update()
                    return
                self.selected_sam_preview_vertex = None
                self.sam_positive_points.append([pt.x(), pt.y()])
                self.sam_point_history.append(("positive", pt.x(), pt.y()))
                self.samPointsChanged.emit(list(self.sam_positive_points), list(self.sam_negative_points))
                self.message.emit(
                    self._t("SAM 点分割：左键添加保留点，右键添加排除点，拖拽顶点微调，Enter 确认")
                )
                self.update()
                return
            if e.button() == QtCore.Qt.RightButton:
                self.sam_negative_points.append([pt.x(), pt.y()])
                self.sam_point_history.append(("negative", pt.x(), pt.y()))
                self.samPointsChanged.emit(list(self.sam_positive_points), list(self.sam_negative_points))
                self.message.emit(
                    self._t("SAM 点分割：左键添加保留点，右键添加排除点，拖拽顶点微调，Enter 确认")
                )
                self.update()
                return
        if self.mode == "sam_box":
            if e.button() == QtCore.Qt.LeftButton:
                preview_handle = self._sam_preview_hit_handle(pt)
                if preview_handle is not None:
                    self.sam_active_region_index = preview_handle[0]
                    self.selected_sam_preview_vertex = preview_handle
                    self.selected_vertex = None
                    self.drag = {"kind": "sam_preview_vertex", "region_index": preview_handle[0], "point_index": preview_handle[1]}
                    self.update()
                    return
                self.selected_sam_preview_vertex = None
                self.rect0 = pt
                self.update()
                return
        if self.mode == "rectangle":
            if e.button() == QtCore.Qt.LeftButton:
                self.rect0 = pt
                self.message.emit(self._t("矩形：按住左键拖拽框选，松开完成"))
                self.update()
            return
        if self.mode == "polygon":
            if e.button() == QtCore.Qt.LeftButton:
                if self._poly_first_hit(pt):
                    self.finish_poly()
                    return
                self.poly.append(pt)
                self.message.emit(
                    self._t("多边形：左键加点，点击首点或按 Enter 闭合，Esc 取消")
                )
                self.update()
            return
        if self.mode == "select" and e.button() == QtCore.Qt.LeftButton:
            handle = self.hit_handle(pt)
            if handle:
                self.sel = handle[0]
                self.selected.emit(self.sel)
                self.selected_vertex = handle
                self.selected_sam_preview_vertex = None
                self.drag = {"kind": "vertex", "sid": handle[0], "index": handle[1]}
                self.update()
                return
            self.sel = self.hit(pt)
            self.selected.emit(self.sel or "")
            self.selected_vertex = None
            self.selected_sam_preview_vertex = None
            self.drag = {"kind": "move", "start": pt} if self.sel else None
            if not self.sel:
                self.pan = {"pos": e.pos()}
            self.update()

    def mouseMoveEvent(self, e):
        if self.pix.isNull():
            return
        pt = self.pos2img(e.pos())
        self.cur = pt
        if self.mode == "select" and self.pan:
            delta = e.pos() - self.pan["pos"]
            window = self.window()
            scroll = getattr(window, "scroll", None)
            if scroll:
                scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().value() - delta.x())
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().value() - delta.y())
                scroll.viewport().update()
            self.pan["pos"] = e.pos()
            return
        if not self.interactive:
            return
        if self.mode in {"sam_point", "sam_box"} and self.drag and self.drag.get("kind") == "sam_preview_vertex":
            self._set_sam_preview_vertex(self.drag["region_index"], self.drag["point_index"], pt)
            self.update()
            return
        if self.mode == "select" and self.drag and self.sel:
            s = self.active_shape()
            if s:
                if self.drag.get("kind") == "vertex":
                    self._set_shape_vertex(s, self.drag["index"], pt)
                else:
                    start = self.drag["start"]
                    dx, dy = pt.x() - start.x(), pt.y() - start.y()
                    for p in s["points"]:
                        p[0] += dx
                        p[1] += dy
                    self.drag["start"] = pt
                self.drag_dirty = True
        self.update()

    def mouseReleaseEvent(self, e):
        if self.pan:
            self.pan = None
            return
        if not self.interactive:
            return
        if self.mode == "rectangle" and e.button() == QtCore.Qt.LeftButton and self.rect0 and self.data:
            r = QtCore.QRectF(self.rect0, self.pos2img(e.pos())).normalized()
            self.rect0 = None
            if r.width() >= 4 and r.height() >= 4:
                s = {
                    "id": next_shape_id(self.data["shapes"]),
                    "label": "rectangle",
                    "shape_type": "rectangle",
                    "points": [[r.left(), r.top()], [r.right(), r.bottom()]],
                    "line_color": self.shape_line_color.name(),
                    "attributes": {},
                }
                self.data["shapes"].append(s)
                self.sel = s["id"]
                self.selected.emit(self.sel)
                self.shapeCreated.emit(self.sel)
                self.changed.emit()
            self.update()
            return
        if self.mode == "sam_box" and e.button() == QtCore.Qt.LeftButton and self.rect0 and self.data:
            r = QtCore.QRectF(self.rect0, self.pos2img(e.pos())).normalized()
            self.rect0 = None
            if r.width() >= 4 and r.height() >= 4:
                self.samBoxRequested.emit((r.left(), r.top(), r.right(), r.bottom()))
            self.update()
            return
        if self.mode in {"sam_point", "sam_box"} and self.drag and self.drag.get("kind") == "sam_preview_vertex":
            self.drag = None
            self.update()
            return
        if self.mode == "select" and self.drag_dirty:
            self.drag_dirty = False
            self.drag = None
            self.changed.emit()
            self.update()
            return
        self.drag = None

    def mouseDoubleClickEvent(self, e):
        del e

    def keyPressEvent(self, e):
        if not self.interactive:
            return
        if e.modifiers() & QtCore.Qt.ControlModifier and e.key() == QtCore.Qt.Key_Z:
            if self.mode == "sam_point" and self.undo_sam_point():
                self.message.emit(self._t("已撤销最近一个 SAM 提示点"))
                return
            if self.undo_polygon_point():
                self.message.emit(self._t("已返回多边形上一步"))
            return
        if e.key() == QtCore.Qt.Key_Escape:
            self.pause_annotation()
            self.message.emit(self._t("已结束标注"))
            return
        if e.key() == QtCore.Qt.Key_Delete:
            if self.delete_selected_vertex():
                return
        if self.mode in {"sam_point", "sam_box"} and e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self.sam_preview_regions:
                self.samPreviewAccepted.emit([[list(point) for point in region] for region in self.sam_preview_regions])
                self.clear_sam_session()
                self.update()
            else:
                self.message.emit(self._t("SAM 分割至少需要先生成一个有效预览区域"))
            return
        if self.mode == "polygon" and e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.finish_poly()
            return
        if e.key() == QtCore.Qt.Key_Left:
            step = self._nudge_step()
            if self.mode in {"sam_point", "sam_box"} and self._move_sam_preview(-step, 0):
                self.message.emit(self._t("已向{direction}微调 SAM 预览区域", direction=self._t("左")))
                return
            if self.nudge_selected(-step, 0):
                self.message.emit(self._t("已向{direction}移动选中区域", direction=self._t("左")))
            return
        if e.key() == QtCore.Qt.Key_Right:
            step = self._nudge_step()
            if self.mode in {"sam_point", "sam_box"} and self._move_sam_preview(step, 0):
                self.message.emit(self._t("已向{direction}微调 SAM 预览区域", direction=self._t("右")))
                return
            if self.nudge_selected(step, 0):
                self.message.emit(self._t("已向{direction}移动选中区域", direction=self._t("右")))
            return
        if e.key() == QtCore.Qt.Key_Up:
            step = self._nudge_step()
            if self.mode in {"sam_point", "sam_box"} and self._move_sam_preview(0, -step):
                self.message.emit(self._t("已向{direction}微调 SAM 预览区域", direction=self._t("上")))
                return
            if self.nudge_selected(0, -step):
                self.message.emit(self._t("已向{direction}移动选中区域", direction=self._t("上")))
            return
        if e.key() == QtCore.Qt.Key_Down:
            step = self._nudge_step()
            if self.mode in {"sam_point", "sam_box"} and self._move_sam_preview(0, step):
                self.message.emit(self._t("已向{direction}微调 SAM 预览区域", direction=self._t("下")))
                return
            if self.nudge_selected(0, step):
                self.message.emit(self._t("已向{direction}移动选中区域", direction=self._t("下")))
            return
        super().keyPressEvent(e)

    def finish_poly(self):
        if self.data and len(self.poly) >= 3:
            s = {
                "id": next_shape_id(self.data["shapes"]),
                "label": "polygon",
                "shape_type": "polygon",
                "points": [[p.x(), p.y()] for p in self.poly],
                "line_color": self.shape_line_color.name(),
                "attributes": {},
            }
            self.data["shapes"].append(s)
            self.sel = s["id"]
            self.selected.emit(self.sel)
            self.shapeCreated.emit(self.sel)
            self.changed.emit()
        self.poly = []
        self.update()


def shape_display_name(shape, language=LANGUAGE_ZH):
    attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
    label = normalized_shape_label(shape)
    category = str(attrs.get("object_category", "")).strip()
    return label or category or tr_text(language, "未命名区域")


def normalized_shape_label(shape):
    if not isinstance(shape, dict):
        return ""
    label = str(shape.get("label", "")).strip()
    shape_type = str(shape.get("shape_type", "")).strip().lower()
    if not label:
        return ""
    if label.lower() in {"rectangle", "polygon"}:
        return ""
    if shape_type and label.lower() == shape_type:
        return ""
    return label


def export_shape_label(shape):
    label = normalized_shape_label(shape)
    if label:
        return label
    attrs = shape.get("attributes", {}) if isinstance(shape, dict) else {}
    category = str(attrs.get("object_category", "")).strip()
    return category or "unlabeled"


def export_labelme_like_json(img, data):
    image_path = Path(img)
    shapes = []
    for shape in (data or {}).get("shapes", []) or []:
        shape_type = str(shape.get("shape_type", "")).strip() or "polygon"
        points = [[float(point[0]), float(point[1])] for point in shape.get("points", [])]
        shapes.append(
            {
                "label": export_shape_label(shape),
                "line_color": None,
                "fill_color": None,
                "points": points,
                "shape_type": shape_type,
                "flags": {},
            }
        )
    return {
        "version": "3.16.7",
        "flags": {},
        "shapes": shapes,
        "lineColor": [23, 201, 255, 128],
        "fillColor": [255, 248, 248, 128],
        "imagePath": image_path.name,
        "imageHeight": int((data or {}).get("imageHeight", 0) or 0),
        "imageWidth": int((data or {}).get("imageWidth", 0) or 0),
    }
