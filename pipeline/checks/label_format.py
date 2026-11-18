"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    c = cfg["label_format"]
    overflow_tol = c["overflow_tol"]
    min_box_px = c["min_box_px"]
    max_box_frac = c["max_box_frac"]
    dup_box_iou = c["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)
        lines = ds.read_label_lines(stem) or []
        seen = []  # (cls_id, (cx, cy, w, h))

        for line_no, text in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"sai định dạng: {e}", line=line_no))
                continue

            if not (0 <= cls_id < n_classes):
                issues.append(
                    Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                          f"id lớp {cls_id} ngoài 0..{n_classes - 1}", line=line_no, extra={"class_id": cls_id})
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue("label_format", ERROR, "BOX_ZERO", stem,
                          f"box rỗng (w={w}, h={h})", line=line_no)
                )
                continue

            x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                          f"box tràn ảnh {overflow:.4f} (> {overflow_tol})",
                          line=line_no, extra={"overflow": round(overflow, 6)})
                )

            box = (cx, cy, w, h)
            dup_iou = max((iou_xywh(box, prev_box) for prev_cls, prev_box in seen if prev_cls == cls_id), default=0.0)
            if dup_iou > dup_box_iou:
                issues.append(
                    Issue("label_format", ERROR, "DUP_BOX", stem,
                          f"box trùng lớp {cls_id} (IoU={dup_iou:.3f} > {dup_box_iou})",
                          line=line_no, extra={"iou": round(dup_iou, 4)})
                )

            if size is not None:
                img_w, img_h = size
                short_px = min(w * img_w, h * img_h)
                if short_px < min_box_px:
                    issues.append(
                        Issue("label_format", WARN, "BOX_TINY", stem,
                              f"cạnh ngắn {short_px:.1f}px < {min_box_px}px",
                              line=line_no, extra={"short_px": round(short_px, 2)})
                    )

            area_frac = w * h
            if area_frac > max_box_frac:
                issues.append(
                    Issue("label_format", WARN, "BOX_HUGE", stem,
                          f"diện tích box {area_frac:.3f} > {max_box_frac}",
                          line=line_no, extra={"area_frac": round(area_frac, 4)})
                )

            seen.append((cls_id, box))

    return issues
