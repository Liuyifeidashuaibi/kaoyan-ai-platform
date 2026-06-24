"""
试卷图像预处理 — 基于 Pillow 实现透视矫正、灰度优化、清晰度增强、边缘裁切。

输入: jpg/png/webp 字节
输出: 标准化矩形图片字节（JPEG/PNG）
"""

from __future__ import annotations

import io
import logging
from typing import Literal

from PIL import Image, ImageFilter, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

# 默认输出格式与质量
_DEFAULT_FORMAT = "JPEG"
_DEFAULT_QUALITY = 92
_MAX_LONG_EDGE = 2400  # 输出图片长边上限，避免 OCR 输入过大


def preprocess_exam_image(
    image_bytes: bytes,
    *,
    perspective_correction: bool = True,
    grayscale: bool = False,
    sharpen: bool = True,
    auto_trim: bool = True,
    remove_handwriting: bool = True,
    output_format: Literal["JPEG", "PNG"] = "JPEG",
    quality: int = _DEFAULT_QUALITY,
    max_long_edge: int = _MAX_LONG_EDGE,
) -> bytes:
    """
    试卷图片预处理全链路。

    :param image_bytes: 原始图片字节
    :param perspective_correction: 是否尝试透视矫正
    :param grayscale: 是否转灰度
    :param sharpen: 是否锐化增强清晰度
    :param auto_trim: 是否自动裁切白边
    :param remove_handwriting: 是否过滤手写笔迹（蓝/红/绿墨）
    :param output_format: 输出格式 JPEG/PNG
    :param quality: JPEG 质量
    :param max_long_edge: 长边上限像素
    :return: 处理后的图片字节
    """
    img = Image.open(io.BytesIO(image_bytes))
    logger.info(
        "原始图片: %dx%d mode=%s format=%s",
        img.width, img.height, img.mode, img.format,
    )

    # 确保 RGB 模式（处理 RGBA/P/LA）
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 1. 透视矫正（四点定位 + affine transform）
    if perspective_correction:
        img = _apply_perspective_correction(img)

    # 2. 自动裁切白边
    if auto_trim:
        img = _auto_trim_borders(img)

    # 3. 手写笔迹过滤（颜色通道分离）
    if remove_handwriting:
        img = _remove_handwriting(img)

    # 4. 灰度优化
    if grayscale:
        img = _optimize_grayscale(img)

    # 5. 清晰度增强（UnsharpMask）
    if sharpen:
        img = _apply_sharpening(img)

    # 6. 尺寸归一化（长边限制）
    img = _resize_if_needed(img, max_long_edge)

    # 输出
    buf = io.BytesIO()
    save_kwargs = {}
    if output_format == "JPEG":
        save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
    else:
        save_kwargs = {"format": "PNG", "optimize": True}

    img.save(buf, **save_kwargs)
    result = buf.getvalue()
    logger.info(
        "预处理完成: %dx%d → %dx%d, 大小 %d → %d bytes",
        Image.open(io.BytesIO(image_bytes)).width,
        Image.open(io.BytesIO(image_bytes)).height,
        img.width, img.height,
        len(image_bytes), len(result),
    )
    return result


def _apply_perspective_correction(img: Image.Image) -> Image.Image:
    """
    透视矫正：基于边缘检测找到试卷四角，使用仿射变换拉正为矩形。
    若检测失败则返回原图。
    """
    try:
        from PIL import ImageFilter

        # 转灰度用于边缘检测
        gray = img.convert("L")

        # 增强对比度以便更好地检测边缘
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(1.5)

        # 边缘检测
        edges = gray.filter(ImageFilter.FIND_EDGES)

        # 二值化
        threshold = 80
        edges = edges.point(lambda x: 255 if x > threshold else 0)

        # 查找边界像素
        bbox = edges.getbbox()
        if bbox is None:
            return img

        # 简单的四点定位：将检测到的边界框映射回原图
        # 使用边缘像素的极值点作为四角近似
        corners = _find_four_corners(edges, bbox)
        if corners is None:
            return img

        # 计算目标矩形
        top_left, top_right, bottom_right, bottom_left = corners
        width_top = _distance(top_left, top_right)
        width_bottom = _distance(bottom_left, bottom_right)
        height_left = _distance(top_left, bottom_left)
        height_right = _distance(top_right, bottom_right)

        target_width = int(max(width_top, width_bottom))
        target_height = int(max(height_left, height_right))

        # 仿射变换（使用 Pillow 的 transform）
        # 需要 8 个系数将四边形映射到矩形
        coeffs = _find_perspective_coeffs(
            corners,
            [(0, 0), (target_width, 0), (target_width, target_height), (0, target_height)],
        )
        if coeffs is None:
            return img

        img = img.transform(
            (target_width, target_height),
            Image.PERSPECTIVE,
            coeffs,
            Image.BICUBIC,
        )
        logger.info("透视矫正完成: %dx%d", target_width, target_height)
        return img

    except Exception as exc:
        logger.warning("透视矫正失败，使用原图: %s", exc)
        return img


def _find_four_corners(
    edges: Image.Image, bbox: tuple[int, int, int, int]
) -> list[tuple[int, int]] | None:
    """从边缘图像中找到四个角点。"""
    pixels = edges.load()
    width, height = edges.size
    left, top, right, bottom = bbox

    # 扫描边缘像素，找极值点作为四角近似
    edge_points: list[tuple[int, int]] = []
    step = max(1, (right - left) // 50)  # 采样步长

    for y in range(top, bottom, max(1, (bottom - top) // 200)):
        for x in range(left, right, step):
            if pixels[x, y] > 0:
                edge_points.append((x, y))

    if len(edge_points) < 10:
        return None

    # 用极值法找四角
    top_left = min(edge_points, key=lambda p: p[0] + p[1])
    top_right = min(edge_points, key=lambda p: -p[0] + p[1])
    bottom_right = min(edge_points, key=lambda p: -p[0] - p[1])
    bottom_left = min(edge_points, key=lambda p: p[0] - p[1])

    return [top_left, top_right, bottom_right, bottom_left]


def _distance(p1: tuple[int, int], p2: tuple[int, int]) -> float:
    """两点距离。"""
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def _find_perspective_coeffs(
    src: list[tuple[int, int]], dst: list[tuple[int, int]]
) -> list[float] | None:
    """
    计算透视变换系数（8 个参数）。
    解线性方程组: [x1, y1, 1, 0, 0, 0, -x1*X1, -y1*X1] [a] = [X1]
                  [0, 0, 0, x1, y1, 1, -x1*Y1, -y1*Y1] [b] = [Y1]
    """
    try:
        import numpy as np

        matrix = []
        for (x, y), (X, Y) in zip(src, dst):
            matrix.append([x, y, 1, 0, 0, 0, -x * X, -y * X, X])
            matrix.append([0, 0, 0, x, y, 1, -x * Y, -y * Y, Y])

        A = np.array(matrix, dtype=np.float64)
        # 求解 Ax = b
        result = np.linalg.lstsq(A[:, :-1], A[:, -1], rcond=None)
        coeffs = result[0].tolist()
        if len(coeffs) != 8:
            return None
        return coeffs

    except Exception as exc:
        logger.warning("计算透视系数失败: %s", exc)
        return None


def _auto_trim_borders(img: Image.Image, threshold: int = 240) -> Image.Image:
    """自动裁切白色/浅色边框。"""
    try:
        gray = img.convert("L")
        # 找到非白色区域的边界框
        bbox = gray.getbbox()
        if bbox is None:
            return img

        left, top, right, bottom = bbox
        # 加一点边距（1%）
        margin_x = int(img.width * 0.01)
        margin_y = int(img.height * 0.01)
        left = max(0, left - margin_x)
        top = max(0, top - margin_y)
        right = min(img.width, right + margin_x)
        bottom = min(img.height, bottom + margin_y)

        if (right - left) < img.width * 0.3 or (bottom - top) < img.height * 0.3:
            # 裁切后太小，可能误判，返回原图
            return img

        trimmed = img.crop((left, top, right, bottom))
        logger.info("自动裁切: (%d,%d,%d,%d) → %dx%d", left, top, right, bottom, trimmed.width, trimmed.height)
        return trimmed

    except Exception as exc:
        logger.warning("自动裁切失败: %s", exc)
        return img


def _remove_handwriting(img: Image.Image) -> Image.Image:
    """
    手写笔迹过滤 — 基于 HSV 色彩空间分离非黑色墨迹。

    印刷体试卷文字为黑色（低饱和度、低亮度），而手写笔迹通常为
    蓝色/红色/绿色（较高饱和度）。将非黑色像素替换为白色，
    即可消除大部分手写标注、圈画、改错痕迹。

    使用 Pillow + numpy，不依赖 OpenCV。
    """
    try:
        import numpy as np

        # RGB → HSV 转换
        hsv_img = img.convert("HSV")
        rgb_arr = np.array(img, dtype=np.float32)
        hsv_arr = np.array(hsv_img, dtype=np.float32)

        # Pillow HSV 范围: H=[0,255], S=[0,255], V=[0,255]
        h = hsv_arr[:, :, 0]
        s = hsv_arr[:, :, 1]
        v = hsv_arr[:, :, 2]

        # 黑色印刷体判定：饱和度低 且 亮度低
        # 手写笔迹特征：饱和度较高（彩色墨）或亮度较高（铅笔浅灰）
        # 黑色墨: S < 60 且 V < 130
        is_black_ink = (s < 60) & (v < 130)

        # 白色/浅色背景: V > 200
        is_background = v > 200

        # 保留黑色印刷体 + 白色背景，其余（手写）替换为白色
        keep_mask = is_black_ink | is_background

        # 用 numpy 操作: 将不保留的像素设为白色
        result_arr = rgb_arr.copy()
        result_arr[~keep_mask] = [255.0, 255.0, 255.0]

        # 轻微模糊处理：手写区域边缘过渡更自然
        result_img = Image.fromarray(result_arr.astype(np.uint8), "RGB")

        # 统计过滤掉的像素比例
        total = keep_mask.size
        filtered = np.sum(~keep_mask)
        ratio = filtered / total * 100
        logger.info(
            "手写过滤: %d/%d 像素被替换为白色 (%.1f%%)",
            filtered, total, ratio,
        )

        return result_img

    except Exception as exc:
        logger.warning("手写笔迹过滤失败，使用原图: %s", exc)
        return img


def _optimize_grayscale(img: Image.Image) -> Image.Image:
    """灰度优化：转灰度 + 对比度自适应。"""
    try:
        gray = ImageOps.grayscale(img)
        # 自动对比度拉伸
        gray = ImageOps.autocontrast(gray, cutoff=2)
        return gray.convert("RGB")  # 转回 RGB 保持兼容性
    except Exception as exc:
        logger.warning("灰度优化失败: %s", exc)
        return img


def _apply_sharpening(img: Image.Image) -> Image.Image:
    """清晰度增强：UnsharpMask 锐化。"""
    try:
        # UnsharpMask(radius, percent, threshold)
        enhanced = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=2))
        return enhanced
    except Exception as exc:
        logger.warning("锐化失败: %s", exc)
        return img


def _resize_if_needed(img: Image.Image, max_long_edge: int) -> Image.Image:
    """长边超限时等比缩放。"""
    long_edge = max(img.width, img.height)
    if long_edge <= max_long_edge:
        return img

    ratio = max_long_edge / long_edge
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    logger.info("尺寸缩放: %dx%d → %dx%d", long_edge, long_edge, new_w, new_h)
    return img
