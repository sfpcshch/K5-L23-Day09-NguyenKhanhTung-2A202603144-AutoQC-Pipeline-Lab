"""CHECK THƯỞNG — Phát hiện box lệch tỉ lệ khung hình (aspect ratio) và mất cân bằng lớp (class imbalance).

Test:  pytest tests/test_aspect_imbalance.py -q

Cấu hình tuỳ chọn trong `cfg.get("aspect_imbalance", {})` (có giá trị mặc định an toàn để không cần sửa
`configs/pipeline.yaml` đã ghim):
- `max_aspect_ratio`: ngưỡng tỉ lệ max(w_px/h_px, h_px/w_px) > ngưỡng -> WARN `BOX_EXTREME_ASPECT` (mặc định 8.0)
- `max_imbalance_ratio`: ngưỡng tỉ số max_count / min_count giữa các lớp hợp lệ > ngưỡng -> WARN `CLASS_IMBALANCE` (mặc định 10.0)
"""
from collections import Counter

from ..common import WARN, Issue, parse_yolo_line


def run(ds, cfg):
    c = cfg.get("aspect_imbalance", {})
    max_aspect = float(c.get("max_aspect_ratio", 8.0))
    max_imbalance = float(c.get("max_imbalance_ratio", 10.0))
    n_classes = len(ds.classes)

    issues = []
    counts = Counter()

    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)
        lines = ds.read_label_lines(stem) or []
        for line_no, text in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if not (0 <= cls_id < n_classes) or w <= 0 or h <= 0:
                continue
            counts[cls_id] += 1
            if size is not None:
                img_w, img_h = size
                w_px, h_px = w * img_w, h * img_h
                if w_px > 0 and h_px > 0:
                    ratio = max(w_px / h_px, h_px / w_px)
                    if ratio > max_aspect:
                        issues.append(
                            Issue(
                                "aspect_imbalance",
                                WARN,
                                "BOX_EXTREME_ASPECT",
                                stem,
                                f"tỉ lệ khung hình box {ratio:.2f}:1 > {max_aspect:.1f}:1 ({w_px:.1f}x{h_px:.1f}px)",
                                line=line_no,
                                extra={"aspect_ratio": round(ratio, 2), "w_px": round(w_px, 1), "h_px": round(h_px, 1)},
                            )
                        )

    if len(counts) >= 2:
        max_cls, max_n = max(counts.items(), key=lambda kv: kv[1])
        min_cls, min_n = min(counts.items(), key=lambda kv: kv[1])
        if min_n > 0:
            imb_ratio = max_n / min_n
            if imb_ratio > max_imbalance:
                issues.append(
                    Issue(
                        "aspect_imbalance",
                        WARN,
                        "CLASS_IMBALANCE",
                        "<dataset>",
                        f"mất cân bằng lớp {imb_ratio:.2f}x (> {max_imbalance:.1f}x): "
                        f"{ds.classes[max_cls]}={max_n} vs {ds.classes[min_cls]}={min_n}",
                        extra={
                            "ratio": round(imb_ratio, 2),
                            "max_class": ds.classes[max_cls],
                            "max_count": max_n,
                            "min_class": ds.classes[min_cls],
                            "min_count": min_n,
                        },
                    )
                )

    return issues
