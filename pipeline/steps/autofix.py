"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_IMAGE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_image(code: str) -> bool:
    return code in REMOVE_IMAGE_CODES or code.startswith("DUP_IMAGE_")


def fix(ds, issues, cfg):
    fixes = []
    err_issues = [i for i in issues if i.severity == ERROR]

    # 1. Xoá ảnh lỗi nặng / trùng / rò rỉ trước, ghi nhận để bỏ qua các lỗi dòng của ảnh đó
    removed = set()
    for i in err_issues:
        if _is_remove_image(i.code) and i.image not in removed:
            removed.add(i.image)
            ip = ds.image_path(i.image)
            if ip is not None and ip.exists():
                ip.unlink()
            lp = ds.label_path(i.image)
            if lp.exists():
                lp.unlink()
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "remove_image",
                "before": i.code,
                "after": "đã xoá ảnh và nhãn",
            })

    # 2. Sửa tên lớp trong data.yaml (tối đa 1 lần)
    if any(i.code == "BAD_CLASS_NAME" for i in err_issues):
        old_names = ds.yaml_names()
        expected = {idx: name for idx, name in enumerate(cfg["classes"])}
        if ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        else:
            data = {"path": "."}
        data["names"] = expected
        ds.yaml_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": str(old_names),
            "after": str(expected),
        })

    # 3. Ảnh thiếu file nhãn: KHÔNG tạo file nhãn, ghi needs_label để đẩy lên đầu hàng đợi người duyệt
    missing_seen = set()
    for i in err_issues:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed and i.image not in missing_seen:
            missing_seen.add(i.image)
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # 4. Gom lỗi theo file nhãn, ghi lại MỘT lần giữ nguyên số dòng gốc (kể cả dòng trống)
    drops = defaultdict(set)
    clips = defaultdict(set)
    for i in err_issues:
        if i.image in removed or i.line is None:
            continue
        if i.code in DROP_CODES:
            drops[i.image].add(i.line)
        elif i.code in CLIP_CODES:
            clips[i.image].add(i.line)

    for stem in sorted(set(drops) | set(clips)):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        drop_set = drops[stem]
        clip_set = clips[stem]

        for line_no, raw_ln in enumerate(raw_lines, start=1):
            if line_no in drop_set:
                # Xoá dòng luôn thắng cắt box nếu 1 dòng có cả 2 lỗi
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": raw_ln,
                    "after": "",
                })
            elif line_no in clip_set:
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(raw_ln)
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": raw_ln,
                        "after": "",
                    })
                    continue

                x1 = max(0.0, min(1.0, cx - w / 2))
                y1 = max(0.0, min(1.0, cy - h / 2))
                x2 = max(0.0, min(1.0, cx + w / 2))
                y2 = max(0.0, min(1.0, cy + h / 2))
                nw, nh = x2 - x1, y2 - y1

                if nw <= 1e-6 or nh <= 1e-6:
                    # Box nằm hẳn ngoài ảnh sau khi cắt -> xoá dòng
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": raw_ln,
                        "after": "",
                    })
                else:
                    ncx, ncy = (x1 + x2) / 2, (y1 + y2) / 2
                    fixed_ln = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                    new_lines.append(fixed_ln)
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": raw_ln,
                        "after": fixed_ln,
                    })
            else:
                new_lines.append(raw_ln)

        content = "\n".join(new_lines) + ("\n" if new_lines else "")
        lp.write_text(content, encoding="utf-8")

    return fixes
