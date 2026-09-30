import argparse
import sys
from pathlib import Path

from PyQt5 import QtWidgets

from .config import LANGUAGE_ZH, SUPPORTED_LANGUAGES
from .main_window import SimpleAnnotationMain
from .sam_backend import SamBoxSegmenter, default_sam_checkpoint_path


def main():
    ap = argparse.ArgumentParser(description="StelleraSAM bilingual SAM annotation platform")
    ap.add_argument("--image-dir", type=Path, default=None)
    ap.add_argument("--annotation-dir", type=Path, default=None)
    ap.add_argument("--sam-checkpoint", type=Path, default=None)
    ap.add_argument("--sam-model-type", type=str, default="")
    ap.add_argument("--language", choices=SUPPORTED_LANGUAGES, default=None)
    ap.add_argument("--sam-self-test", action="store_true", help="仅执行 SAM 权重和依赖自检后退出")
    args = ap.parse_args()

    if args.sam_self_test:
        checkpoint = args.sam_checkpoint or default_sam_checkpoint_path()
        segmenter = SamBoxSegmenter(checkpoint, args.sam_model_type)
        error = segmenter.availability_error()
        if error:
            raise SystemExit(segmenter.help_message(error, args.language or LANGUAGE_ZH))
        segmenter._ensure_predictor()
        checkpoint_name = Path(checkpoint).name if checkpoint else "未配置"
        print(f"SAM self-test passed: {checkpoint_name}")
        return

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = SimpleAnnotationMain(
        args.image_dir,
        args.annotation_dir,
        args.sam_checkpoint,
        args.sam_model_type,
        args.language,
    )
    win.show()
    sys.exit(app.exec_())
