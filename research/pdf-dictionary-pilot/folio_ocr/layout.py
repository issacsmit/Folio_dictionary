from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .config import FEATURE_TITLE_RE


@dataclass
class PageLayout:
    width: int
    height: int
    header_y: int
    footer_y: int
    left_x: int
    right_x: int
    gutter_x: int
    columns: list[tuple[int, int, int, int]]  # x0,y0,x1,y1
    boxes: list[dict]


def _horizontal_rule_y(ink: np.ndarray, y0: int, y1: int, min_frac: float) -> int | None:
    h, w = ink.shape
    y1 = min(y1, h)
    y0 = max(y0, 0)
    if y1 <= y0:
        return None
    row = ink[y0:y1].sum(axis=1)
    thresh = min_frac * w
    hits = np.where(row >= thresh)[0]
    if len(hits) == 0:
        return None
    return int(y0 + hits[0])


def detect_layout(gray: np.ndarray) -> PageLayout:
    h, w = gray.shape
    ink = (gray < 128).astype(np.uint8)
    header_y = _horizontal_rule_y(ink, 40, min(320, h // 6), 0.55)
    if header_y is None:
        header_y = 210
    else:
        header_y = min(header_y + 10, h // 4)

    footer_y = h - 20
    foot_rule = _horizontal_rule_y(ink, h - 180, h - 10, 0.45)
    if foot_rule is not None:
        footer_y = foot_rule - 4

    left_x = 0
    col_region = ink[header_y:footer_y]
    col_proj = col_region.sum(axis=0)
    # skip left thumb index: first 4% often a giant letter
    thumb_w = int(w * 0.035)
    # first x with substantial body ink after thumb
    after = np.where(col_proj[thumb_w:] > col_region.shape[0] * 0.02)[0]
    left_x = thumb_w + int(after[0]) if len(after) else int(w * 0.04)
    left_x = max(left_x, int(w * 0.02))

    right_hits = np.where(col_proj > col_region.shape[0] * 0.02)[0]
    right_x = int(right_hits[-1]) + 8 if len(right_hits) else w - 8
    right_x = min(right_x, w - 4)

    body = ink[header_y:footer_y, left_x:right_x]
    proj = body.sum(axis=0).astype(np.float64)
    k = max(15, (right_x - left_x) // 80)
    if k % 2 == 0:
        k += 1
    smooth = np.convolve(proj, np.ones(k) / k, mode="same")
    center = (right_x - left_x) // 2
    window = (right_x - left_x) // 6
    sl = slice(center - window, center + window)
    gutter_local = int(np.argmin(smooth[sl]))
    gutter_x = left_x + (center - window) + gutter_local

    gap = 16
    columns = [
        (left_x, header_y, max(left_x + 50, gutter_x - gap), footer_y),
        (min(w - 50, gutter_x + gap), header_y, right_x, footer_y),
    ]

    boxes = _detect_feature_boxes(gray, header_y, footer_y, left_x, right_x)
    return PageLayout(
        width=w,
        height=h,
        header_y=header_y,
        footer_y=footer_y,
        left_x=left_x,
        right_x=right_x,
        gutter_x=gutter_x,
        columns=columns,
        boxes=boxes,
    )


def _detect_feature_boxes(
    gray: np.ndarray, header_y: int, footer_y: int, left_x: int, right_x: int
) -> list[dict]:
    h, w = gray.shape
    body = gray[header_y:footer_y, left_x:right_x]
    bw = (body < 80).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    body_area = body.shape[0] * body.shape[1]
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area < 0.015 * body_area or area > 0.7 * body_area:
            continue
        if cw < 0.25 * body.shape[1]:
            continue
        if ch < 80:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        rectangular = len(approx) >= 4
        if not rectangular:
            continue
        out.append(
            {
                "x0": int(left_x + x),
                "y0": int(header_y + y),
                "x1": int(left_x + x + cw),
                "y1": int(header_y + y + ch),
            }
        )
    out.sort(key=lambda b: (b["y0"], b["x0"]))
    return out


def column_index(layout: PageLayout, x_center: float) -> int:
    return 0 if x_center < layout.gutter_x else 1


def line_in_box(line: dict, box: dict, pad: int = 8) -> bool:
    cx = (line["x0"] + line["x1"]) / 2
    cy = (line["y0"] + line["y1"]) / 2
    return box["x0"] - pad <= cx <= box["x1"] + pad and box["y0"] - pad <= cy <= box["y1"] + pad


_FEATURE_RE = re.compile(FEATURE_TITLE_RE, re.I)


def is_feature_title(text: str) -> bool:
    return bool(_FEATURE_RE.search((text or "").strip()))


def load_gray(path) -> np.ndarray:
    im = Image.open(path).convert("L")
    return np.array(im)
