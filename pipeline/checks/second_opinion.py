"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

So nhãn với dự đoán của model lớn hơn và CHỈ CẢNH BÁO (WARN):
- POSSIBLE_MISSING: dự đoán (conf >= conf, diện tích >= min_area_px) không khớp nhãn nào (IoU < iou_missing)
- POSSIBLE_LOOSE_BOX: có nhãn cùng lớp (IoU >= iou_missing) nhưng IoU tốt nhất < iou_loose
- POSSIBLE_WRONG_CLASS: không có nhãn cùng lớp, nhưng nhãn khác lớp tốt nhất có IoU >= iou_match
- POSSIBLE_FALSE_POS: dòng nhãn hợp lệ không khớp bất kỳ dự đoán nào (conf >= fp_conf, không lọc diện tích) với IoU >= iou_missing
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    c = cfg["second_opinion"]
    conf_thr = c["conf"]
    min_area_px = c["min_area_px"]
    fp_conf = c["fp_conf"]
    iou_missing = c["iou_missing"]
    iou_match = c["iou_match"]
    iou_loose = c["iou_loose"]
    n_classes = len(ds.classes)

    issues = []
    for p in ds.image_files():
        stem = p.stem
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        img_w, img_h = size

        # Giữ số dòng gốc (1-based) để báo POSSIBLE_FALSE_POS chính xác khi có dòng hỏng/trống
        labels = []
        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls_id < n_classes and w > 0 and h > 0:
                labels.append((line_no, cls_id, (cx, cy, w, h)))

        img_preds = preds[stem]

        # 1. Duyệt từng dự đoán của model theo đúng thứ tự trong preds[stem]
        for pr in img_preds:
            p_cls, p_conf, pcx, pcy, pw, ph = pr
            if p_conf < conf_thr:
                continue
            if (pw * img_w) * (ph * img_h) < min_area_px:
                continue

            p_box = (pcx, pcy, pw, ph)
            cands = []
            for line_no, l_cls, l_box in labels:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((iou, l_cls, line_no))

            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model thấy lớp {ds.classes[int(p_cls)]} (conf={p_conf:.2f}) nhưng nhãn không có box",
                        extra={"conf": round(float(p_conf), 4), "pred_class": int(p_cls)},
                    )
                )
                continue

            same_cls = [x for x in cands if x[1] == p_cls]
            if same_cls:
                best_iou = max(x[0] for x in same_cls)
                if best_iou < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box lớp {ds.classes[int(p_cls)]} lỏng/lệch (IoU={best_iou:.2f} < {iou_loose})",
                            extra={"conf": round(float(p_conf), 4), "iou": round(float(best_iou), 4)},
                        )
                    )
                continue

            best_other_iou, best_other_cls, _ = max(cands, key=lambda x: x[0])
            if best_other_iou >= iou_match:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_WRONG_CLASS",
                        stem,
                        f"nhãn ghi {ds.classes[int(best_other_cls)]}, model thấy {ds.classes[int(p_cls)]} "
                        f"(conf={p_conf:.2f}, IoU={best_other_iou:.2f})",
                        extra={
                            "conf": round(float(p_conf), 4),
                            "iou": round(float(best_other_iou), 4),
                            "pred_class": int(p_cls),
                            "label_class": int(best_other_cls),
                        },
                    )
                )

        # 2. Kiểm tra POSSIBLE_FALSE_POS theo thứ tự số dòng nhãn
        fp_preds = [pr for pr in img_preds if pr[1] >= fp_conf]
        for line_no, l_cls, l_box in labels:
            best_iou = max(
                (iou_xywh(l_box, (pr[2], pr[3], pr[4], pr[5])) for pr in fp_preds),
                default=0.0,
            )
            if best_iou < iou_missing:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"box lớp {ds.classes[int(l_cls)]} không khớp dự đoán nào của model (max IoU={best_iou:.2f})",
                        line=line_no,
                        extra={"iou": round(float(best_iou), 4), "label_class": int(l_cls)},
                    )
                )

    return issues
