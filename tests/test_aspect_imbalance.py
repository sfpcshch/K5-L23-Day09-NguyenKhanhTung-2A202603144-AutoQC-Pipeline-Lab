from pipeline.checks import aspect_imbalance


def test_normal_boxes_and_balanced_classes_are_silent(make_ds, cfg):
    ds = make_ds(
        images={"a": 1, "b": 2},
        labels={
            "a": ["0 0.5 0.5 0.2 0.2", "1 0.3 0.5 0.1 0.3"],
            "b": ["2 0.5 0.5 0.3 0.2", "3 0.5 0.5 0.4 0.2"],
        },
        size=(640, 480),
    )
    assert aspect_imbalance.run(ds, cfg) == []


def test_extreme_wide_and_tall_aspect_ratios(make_ds, cfg):
    # w_px = 0.5*640 = 320, h_px = 0.05*480 = 24 -> 13.33:1 (> 8.0)
    # w_px = 0.02*640 = 12.8, h_px = 0.5*480 = 240 -> 18.75:1 (> 8.0)
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["0 0.5 0.5 0.5 0.05", "1 0.5 0.5 0.02 0.5", "0 0.5 0.5 0.2 0.2"]},
        size=(640, 480),
    )
    iss = aspect_imbalance.run(ds, cfg)
    got = [(i.code, i.severity, i.image, i.line) for i in iss]
    assert got == [
        ("BOX_EXTREME_ASPECT", "warn", "a", 1),
        ("BOX_EXTREME_ASPECT", "warn", "a", 2),
    ]


def test_class_imbalance_detected_across_dataset(make_ds, cfg):
    # 12 person boxes vs 1 bus box -> ratio 12.0 > 10.0
    person_lines = [f"1 0.5 0.5 0.1 0.2"] * 12
    ds = make_ds(
        images={"a": 1, "b": 2},
        labels={"a": person_lines, "b": ["3 0.5 0.5 0.3 0.2"]},
        size=(640, 480),
    )
    iss = aspect_imbalance.run(ds, cfg)
    imb = [i for i in iss if i.code == "CLASS_IMBALANCE"]
    assert len(imb) == 1
    assert imb[0].severity == "warn"
    assert imb[0].image == "<dataset>"
    assert imb[0].extra["ratio"] == 12.0


def test_broken_lines_and_custom_thresholds(make_ds, cfg):
    cfg["aspect_imbalance"] = {"max_aspect_ratio": 3.0, "max_imbalance_ratio": 2.0}
    # 0.3*640=192, 0.1*480=48 -> 4.0:1 > 3.0
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["garbage", "93 0.5 0.5 0.2 0.2", "0 0.5 0.5 0.3 0.1", "0 0.2 0.2 0.1 0.1", "0 0.8 0.8 0.1 0.1", "1 0.5 0.5 0.1 0.1"]},
        size=(640, 480),
    )
    iss = aspect_imbalance.run(ds, cfg)
    codes = {i.code for i in iss}
    assert codes == {"BOX_EXTREME_ASPECT", "CLASS_IMBALANCE"}
    assert [i.line for i in iss if i.code == "BOX_EXTREME_ASPECT"] == [3]
