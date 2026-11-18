"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed_set = set(reviewed)
    n_images = len(stems)
    hold_ratio = cfg["gate"]["warn_ratio_hold"]

    n_errors = sum(1 for i in issues if i.severity == ERROR)
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stems and i.image not in reviewed_set
    }
    n_warn_images = len(warn_images)
    raw_ratio = (n_warn_images / n_images) if n_images > 0 else 0.0
    warn_ratio = round(raw_ratio, 4)

    reasons = []
    if n_errors > 0:
        decision = "Rework"
        reasons.append(f"còn {n_errors} lỗi bắt buộc (ERROR) chưa được xử lý")
        if raw_ratio >= hold_ratio:
            reasons.append(
                f"tỉ lệ ảnh còn cảnh báo chưa duyệt {n_warn_images}/{n_images} "
                f"({warn_ratio:.2%}) >= ngưỡng {hold_ratio:.2%}"
            )
    elif raw_ratio >= hold_ratio:
        decision = "Hold"
        reasons.append(
            f"tỉ lệ ảnh còn cảnh báo chưa duyệt {n_warn_images}/{n_images} "
            f"({warn_ratio:.2%}) >= ngưỡng {hold_ratio:.2%}"
        )
    else:
        decision = "Release"
        reasons.append(
            f"không còn lỗi bắt buộc; tỉ lệ ảnh còn cảnh báo chưa duyệt "
            f"{n_warn_images}/{n_images} ({warn_ratio:.2%}) < ngưỡng {hold_ratio:.2%}"
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
