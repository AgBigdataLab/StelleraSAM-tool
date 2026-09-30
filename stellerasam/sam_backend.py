import sys
from pathlib import Path

from .config import LANGUAGE_ZH, tr_text


def runtime_root_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_sam_checkpoint_path():
    roots = [runtime_root_dir()]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.insert(0, Path(bundle_root).resolve())
    for root in roots:
        for relative_path in (
            Path("SAM_weight") / "sam_vit.pth",
            Path("SAM_weight") / "sam_vit_b_01ec64.pth",
            Path("checkpoints") / "sam_vit_b_01ec64.pth",
            Path("SAM权重") / "sam_vit_b_01ec64.pth",
            Path("sam_vit_b_01ec64.pth"),
        ):
            candidate = root / relative_path
            if candidate.exists():
                return candidate
    return None


class SamBoxSegmenter:
    def __init__(self, checkpoint=None, model_type="", device=""):
        self.checkpoint = Path(checkpoint).expanduser() if checkpoint else None
        self.model_type = str(model_type or "").strip()
        self.device = str(device or "").strip()
        self._predictor = None
        self._loaded_signature = None
        self._image_signature = None

    def set_checkpoint(self, checkpoint):
        self.checkpoint = Path(checkpoint).expanduser() if checkpoint else None
        self._predictor = None
        self._loaded_signature = None
        self._image_signature = None

    def set_model_type(self, model_type):
        self.model_type = str(model_type or "").strip()
        self._predictor = None
        self._loaded_signature = None
        self._image_signature = None

    def current_signature(self):
        return (str(self.checkpoint), self.resolved_model_type(), self.device)

    def is_loaded(self):
        return self._predictor is not None and self._loaded_signature == self.current_signature()

    def resolved_model_type(self):
        if self.model_type:
            return self.model_type
        checkpoint_name = str((self.checkpoint or "").name).lower()
        if "vit_h" in checkpoint_name:
            return "vit_h"
        if "vit_l" in checkpoint_name:
            return "vit_l"
        return "vit_b"

    def availability_error(self):
        if not self.checkpoint or not self.checkpoint.exists():
            return "missing_checkpoint"
        try:
            import torch  # noqa: F401
            from segment_anything import SamPredictor, sam_model_registry  # noqa: F401
        except Exception as exc:
            return f"dependency_error:{exc}"
        model_type = self.resolved_model_type()
        if model_type not in {"vit_b", "vit_l", "vit_h"}:
            return f"invalid_model_type:{model_type}"
        return ""

    def help_message(self, error, language=LANGUAGE_ZH):
        if error == "missing_checkpoint":
            return tr_text(
                language, "未找到 SAM 权重文件。请先选择或传入 .pth/.pt 权重文件。"
            )
        if error.startswith("dependency_error:"):
            detail = error.split(":", 1)[1].strip() if ":" in error else error
            return tr_text(
                language,
                "SAM 依赖加载失败，当前环境无法启用 SAM 分割。\n\nPython: {python}\n详细异常：{detail}",
                python=sys.executable,
                detail=detail,
            )
        if error.startswith("invalid_model_type:"):
            return tr_text(
                language, "SAM 模型类型无效。当前仅支持 vit_b / vit_l / vit_h。"
            )
        return error or tr_text(language, "SAM 初始化失败。")

    def _load_sam_state_dict(self, torch_module, checkpoint_path):
        checkpoint_path = str(checkpoint_path)
        load_kwargs = {"map_location": "cpu"}
        try:
            state_dict = torch_module.load(checkpoint_path, weights_only=True, **load_kwargs)
        except TypeError:
            state_dict = torch_module.load(checkpoint_path, **load_kwargs)
        if isinstance(state_dict, dict):
            for key in ("state_dict", "model", "model_state_dict"):
                nested = state_dict.get(key)
                if isinstance(nested, dict) and nested:
                    return nested
        return state_dict

    def _ensure_predictor(self):
        error = self.availability_error()
        if error:
            raise RuntimeError(self.help_message(error))
        signature = (str(self.checkpoint), self.resolved_model_type(), self.device)
        if self._predictor is not None and self._loaded_signature == signature:
            return self._predictor
        import torch
        from segment_anything import SamPredictor, sam_model_registry

        model_type = self.resolved_model_type()
        sam_model = sam_model_registry[model_type](checkpoint=None)
        state_dict = self._load_sam_state_dict(torch, self.checkpoint)
        sam_model.load_state_dict(state_dict)
        runtime_device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        sam_model.to(device=runtime_device)
        self._predictor = SamPredictor(sam_model)
        self._loaded_signature = signature
        self._image_signature = None
        return self._predictor

    def _set_predictor_image(self, predictor, image_rgb, image_key=None):
        import numpy as np

        image_rgb = np.asarray(image_rgb)
        image_signature = image_key if image_key is not None else (
            image_rgb.shape,
            str(image_rgb.dtype),
            int(image_rgb.__array_interface__["data"][0]),
        )
        if self._image_signature != image_signature:
            predictor.set_image(image_rgb)
            self._image_signature = image_signature
        return image_rgb

    def clear_image_cache(self):
        self._image_signature = None

    @staticmethod
    def _box_polygon(box_xyxy):
        x1, y1, x2, y2 = [float(v) for v in box_xyxy]
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def _mask_to_polygon(self, mask, box_xyxy):
        import cv2
        import numpy as np

        mask_u8 = (mask.astype(np.uint8) > 0).astype(np.uint8) * 255
        contours, _hierarchy = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for contour in contours:
            if cv2.contourArea(contour) < 16:
                continue
            epsilon = max(1.0, 0.003 * cv2.arcLength(contour, True))
            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = [[float(pt[0][0]), float(pt[0][1])] for pt in approx]
            if len(points) >= 3:
                polygons.append(points)
        if polygons:
            polygons.sort(key=lambda pts: abs(self._polygon_area(pts)), reverse=True)
            return polygons
        return [self._box_polygon(box_xyxy)]

    @staticmethod
    def _polygon_area(points):
        area = 0.0
        for idx, (x1, y1) in enumerate(points):
            x2, y2 = points[(idx + 1) % len(points)]
            area += x1 * y2 - x2 * y1
        return area * 0.5

    def segment_polygon(self, image_rgb, box_xyxy, image_key=None):
        import numpy as np

        predictor = self._ensure_predictor()
        self._set_predictor_image(predictor, image_rgb, image_key=image_key)
        box = np.asarray(box_xyxy, dtype=np.float32)
        masks, scores, _logits = predictor.predict(
            point_coords=None,
            point_labels=None,
            box=box,
            multimask_output=True,
        )
        if masks is None or len(masks) == 0:
            return self._box_polygon(box_xyxy)
        best_index = int(np.argmax(scores if scores is not None else [0]))
        polygons = self._mask_to_polygon(masks[best_index], box_xyxy)
        return polygons[0] if polygons else self._box_polygon(box_xyxy)

    def segment_polygon_by_points(self, image_rgb, positive_points, negative_points=None, image_key=None):
        import numpy as np

        predictor = self._ensure_predictor()
        self._set_predictor_image(predictor, image_rgb, image_key=image_key)
        pos = [[float(x), float(y)] for x, y in (positive_points or [])]
        neg = [[float(x), float(y)] for x, y in (negative_points or [])]
        if not pos and not neg:
            return []
        point_coords = np.asarray(pos + neg, dtype=np.float32)
        point_labels = np.asarray([1] * len(pos) + [0] * len(neg), dtype=np.int32)
        masks, scores, _logits = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=None,
            multimask_output=True,
        )
        if masks is None or len(masks) == 0:
            return []
        best_index = int(np.argmax(scores if scores is not None else [0]))
        if not pos:
            return []
        xs = [p[0] for p in pos]
        ys = [p[1] for p in pos]
        fallback_box = (min(xs), min(ys), max(xs), max(ys))
        return self._mask_to_polygon(masks[best_index], fallback_box)
