import json
from pathlib import Path

from .config import IMG_SUFFIX, blank, natural_sort_key, normalize_shape_ids


class Repo:
    def __init__(self, img_dir, ann_dir=None):
        self.set_dirs(img_dir, ann_dir)

    def set_dirs(self, img_dir, ann_dir=None):
        self.img_dir = Path(img_dir) if img_dir else None
        self.ann_dir = Path(ann_dir) if ann_dir else None

    def images(self):
        if self.img_dir is None or not self.img_dir.exists():
            return []
        return sorted(
            [p for p in self.img_dir.iterdir() if p.is_file() and p.suffix.lower() in IMG_SUFFIX],
            key=lambda p: natural_sort_key(p.name),
        )

    def ann_path(self, img):
        if self.ann_dir is None:
            return None
        return self.ann_dir / f"{img.stem}.json"

    def load(self, img, w, h):
        p = self.ann_path(img)
        if p and p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            data["imagePath"], data["imageWidth"], data["imageHeight"] = img.name, w, h
            data.setdefault("originalImageName", img.name)
            data.setdefault("previousImageName", "")
            data.setdefault("imageAttributes", {})
            data.setdefault("shapes", [])
            normalize_shape_ids(data)
            return data
        return blank(img.name, w, h)

    def save(self, img, data):
        if self.ann_dir is None:
            raise ValueError("尚未设置 JSON 保存目录。")
        self.ann_dir.mkdir(parents=True, exist_ok=True)
        data["imagePath"] = img.name
        data.setdefault("originalImageName", img.name)
        normalize_shape_ids(data)
        p = self.ann_path(img)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def rename_image_and_annotation(self, old_img, new_name):
        new_img = old_img.with_name(new_name)
        if new_img.exists() and new_img != old_img:
            raise FileExistsError(f"目标文件已存在: {new_img.name}")
        old_ann = self.ann_path(old_img)
        new_ann = self.ann_path(new_img)
        old_img.rename(new_img)
        if old_ann and old_ann.exists() and old_ann != new_ann:
            self.ann_dir.mkdir(parents=True, exist_ok=True)
            old_ann.rename(new_ann)
        return new_img
