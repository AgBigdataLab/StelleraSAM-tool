# StelleraSAM-tool

**A SAM-assisted instance annotation tool for individual *Stellera chamaejasme* plants**

Shuchen Liu<sup>1,2</sup>, Yunpeng Cui<sup>1,2*</sup>

StelleraSAM is a bilingual desktop application for instance-level annotation of *S. chamaejasme* in natural grassland images. It supports SAM-assisted mask generation, manual boundary refinement, and LabelMe-compatible JSON export.

## Features

- Positive/negative point prompts and box prompts
- Manual polygon and rectangle annotation
- Mask-boundary refinement and instance management
- Chinese and English interfaces
- CPU and CUDA inference
- LabelMe-compatible JSON output

## Windows release

A ready-to-run GPU package is available on the repository's **Releases** page. Extract the archive and run `StelleraSAM.exe`.

## Run from source

Python 3.8 or later is required. Create an environment and install the dependencies:

```bash
conda create -n stellerasam python=3.8 -y
conda activate stellerasam
pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 --index-url https://download.pytorch.org/whl/cu118
pip install Pillow==9.5.0 PyQt5==5.15.9 numpy==1.24.3 opencv-python==4.12.0.88
pip install git+https://github.com/facebookresearch/segment-anything.git
```

Create `SAM_weight` in the project root and place a compatible `vit_b`, `vit_l`, or `vit_h` checkpoint in it. The default ViT-B paths are:

```text
SAM_weight/sam_vit.pth
SAM_weight/sam_vit_b_01ec64.pth
```

Start the application:

```bash
python StelleraSAM.py
```

## Output

Each annotated image is saved as a same-stem `.json` file containing polygon masks, class labels, instance identifiers, and image metadata.

## License

Released under the [BSD 3-Clause License](LICENSE).

## Contact

For questions, contact Yunpeng Cui or Shuchen Liu.

