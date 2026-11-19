# Báo cáo Day 09 — Nguyễn Khánh Tùng, 2A202603144

## 1. Kết luận trước
Pipeline đưa ra kết luận **Hold** (mã thoát `10`). Trong số 224 ảnh đầu vào của lô `data/raw`, bước intake chấp nhận **202 ảnh** và loại bỏ **22 ảnh** lỗi nặng/trùng lặp; toàn bộ 202 ảnh hợp lệ này được xuất ra bộ dữ liệu nháp tại `submission/export/clean_v1/`. Quyết định là **Hold** vì pipeline đã triệt tiêu hoàn toàn 100% lỗi bắt buộc (`n_errors = 0`), tuy nhiên sau khi người duyệt sử dụng hết ngân sách 80 ảnh, vẫn còn **38/202 ảnh** (tỉ lệ cảnh báo **18.81%**) chứa các cảnh báo ngữ nghĩa chưa được xác minh, vượt ngưỡng cảnh báo cho phép `warn_ratio_hold = 10.00%`.

---

## 2. Lỗi và phân việc

Thống kê chi tiết từ báo cáo `submission/reports/02_error_list_v1` (tổng cộng 20 mã lỗi, 71 lỗi bắt buộc và 240 dòng cảnh báo trước khi sửa):

| Mã lỗi | Số ảnh / dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|:---:|---|
| `CORRUPT_IMAGE` | 2 ảnh / 2 dòng | Máy (intake) | File ảnh bị hỏng cấu trúc header/byte, không thể đọc bằng PIL `Image.load()`. Máy loại bỏ thẳng tay khỏi dataset. |
| `BAD_SIZE` | 3 ảnh / 3 dòng | Máy (intake) | Kích thước cạnh ngắn < 250px, không đạt tiêu chuẩn độ phân giải tối thiểu của dự án. Máy tự động loại bỏ. |
| `DUP_IMAGE_EXACT` | 8 ảnh / 8 dòng | Máy (intake) | Trùng khớp từng byte (md5) với một ảnh đã xuất hiện trước đó trong lô raw. Máy tự động loại bỏ bản sao. |
| `DUP_IMAGE_NEAR` | 4 ảnh / 4 dòng | Máy (intake) | Trùng lặp gần đúng (perceptual hash distance $\le 10$). Máy tự động loại bỏ để tránh overfit và thiên lệch phân bố. |
| `LEAK_TEST` | 5 ảnh / 5 dòng | Máy (intake) | Trùng lặp hoàn toàn hoặc gần đúng với ảnh trong kho `test/` hoặc `gold_val/`. Máy bắt buộc loại bỏ để tránh metric đẹp giả. |
| `BAD_CLASS_NAME` | 1 ảnh / 2 dòng | Máy (autofix) | File `data.yaml` ghi sai tên lớp (`Person`, `Bus` viết hoa). Máy tự động sửa lại đúng danh sách chuẩn `cfg["classes"]`. |
| `BAD_FORMAT` | 3 ảnh / 3 dòng | Máy (autofix) | Dòng nhãn thiếu cột số hoặc chứa giá trị bất thường (`nan`/`inf`). Máy tự động xóa dòng lỗi (`drop_line`). |
| `BAD_CLASS_ID` | 6 ảnh / 6 dòng | Máy (autofix) | ID lớp ngoài phạm vi hợp lệ $0..3$ (như -1, 4, 7, 93). Máy tự động xóa dòng lỗi (`drop_line`). |
| `BOX_ZERO` | 4 ảnh / 4 dòng | Máy (autofix) | Box có chiều rộng hoặc chiều cao $\le 0$. Máy tự động xóa dòng lỗi (`drop_line`). |
| `BOX_OUT_OF_IMAGE` | 8 ảnh / 8 dòng | Máy (autofix) | Box có tọa độ biên vượt ra ngoài phạm vi $[0, 1]$ quá dung sai 0.002. Máy tự động cắt xén biên (`clip_box`) về $[0, 1]$. |
| `DUP_BOX` | 7 ảnh / 7 dòng | Máy (autofix) | Hai box cùng lớp có $\text{IoU} > 0.90$. Máy tự động xóa box thứ hai trùng lặp (`drop_line`). |
| `MISSING_LABEL_FILE` | 6 ảnh / 6 dòng | Người (hàng đợi) | Có file ảnh nhưng hoàn toàn không có file `.txt`. Máy không thể tự bịa nhãn (ghi `needs_label`), bắt buộc đưa lên đầu hàng đợi để con người gán mới. |
| `EMPTY_LABEL` | 12 ảnh / 12 dòng | Người (hàng đợi) | File nhãn rỗng (0 bytes). Cần người xác minh đây là ảnh nền (negative sample) hay là thiếu sót của người gán. |
| `BOX_HUGE` | 3 ảnh / 3 dòng | Người (hàng đợi) | Diện tích box phủ $> 95\%$ khung hình. Thường là gán nhầm toàn bộ nền ảnh. Cần người kiểm tra. |
| `BOX_TINY` | 4 ảnh / 6 dòng | Người (hàng đợi) | Cạnh ngắn $< 12\text{ px}$. Cần người kiểm tra xem vật thể có đủ chi tiết nhận dạng hay chỉ là đốm nhiễu. |
| `CLASS_RARE` | 1 ảnh / 4 dòng | Máy/Người | Thống kê dataset xuất hiện các token hiếm (-1, 4, 7, 93). Đã được triệt tiêu khi máy xóa các `BAD_CLASS_ID`. |
| `POSSIBLE_WRONG_CLASS` | 18 ảnh / 18 dòng | Người (hàng đợi) | Nhãn ghi một lớp nhưng model checker dự đoán lớp khác với $\text{IoU} \ge 0.50$ và $\text{conf} \ge 0.60$. Bắt buộc người phân xử. |
| `POSSIBLE_MISSING` | 52 ảnh / 53 dòng | Người (hàng đợi) | Model checker phát hiện vật thể rõ nét ($\text{conf} \ge 0.60$, diện tích $\ge 600\text{ px}^2$) nhưng nhãn bỏ sót. Người cần thêm box. |
| `POSSIBLE_LOOSE_BOX` | 24 ảnh / 28 dòng | Người (hàng đợi) | Box cùng lớp nhưng lệch/lỏng so với dự đoán ($0.30 \le \text{IoU} < 0.50$). Cần người nắn lại biên bounding box. |
| `POSSIBLE_FALSE_POS` | 24 ảnh / 25 dòng | Người (hàng đợi) | Box nhãn không khớp với bất kỳ dự đoán nào của model checker ($\text{IoU} < 0.30$). Cần người xác minh box thừa/ảo. |

### Phân tích hàng đợi duyệt `05_review_queue.csv` và ngân sách 80 ảnh:
1. **Thứ tự ưu tiên:** Hàng đợi chấm điểm ưu tiên theo công thức: $\text{score} = \sum w_i \times (1 + \text{conf})$. Trong đó `NEEDS_LABEL` có trọng số cao nhất ($w=10.0$), tiếp đến là `POSSIBLE_WRONG_CLASS` ($w=3.0$), `POSSIBLE_MISSING` và `POSSIBLE_FALSE_POS` ($w=2.0$), `POSSIBLE_LOOSE_BOX` ($w=1.5$).
   - Ảnh đầu hàng là `img_0020` (priority 11.524) vì ảnh này vừa bị máy xóa dòng ID lạ (`FIXED_DROP_LINE`), vừa bị model cảnh báo đồng thời cả thiếu nhãn `POSSIBLE_MISSING` lẫn gán nhầm lớp `POSSIBLE_WRONG_CLASS`.
   - Ngay sau đó là 6 ảnh hoàn toàn chưa có nhãn `NEEDS_LABEL` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). Việc đẩy các ảnh này lên đầu giúp con người gán nhãn bổ sung ngay, ngăn chặn lỗi bắt buộc làm hỏng pipeline ở vòng 3.
2. **Hiệu quả xử lý ngữ nghĩa với ngân sách 80 ảnh:**
   - Trong vòng 2 (sau khi máy tự sửa), toàn bộ dataset còn lại **123 cảnh báo ngữ nghĩa trên 103 ảnh**.
   - Với ngân sách 80 ảnh được xếp theo độ ưu tiên, người duyệt đã xử lý thành công **94/123 dòng cảnh báo ngữ nghĩa (đạt tỉ lệ 76.4%)**, phủ **74/103 ảnh có lỗi ngữ nghĩa (đạt 71.8%)**.
   - Đặc biệt, người duyệt đã rà soát và khắc phục được **100% (18/18 dòng) lỗi gán nhầm lớp `POSSIBLE_WRONG_CLASS`** và **96.2% (51/53 dòng) lỗi thiếu nhãn `POSSIBLE_MISSING`**. Các cảnh báo còn sót lại chưa duyệt rơi vào nhóm có trọng số thấp hơn ở cuối hàng đợi gồm các box lỏng nhẹ (`POSSIBLE_LOOSE_BOX`) và box nghi ngờ thừa (`POSSIBLE_FALSE_POS`).

---

## 3. Calibration (2 ngưỡng)

Bảng so sánh trước và sau khi thực hiện sweep trên tập calibration `data/calib/`:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|:---:|:---:|---|---|
| `duplicates.phash_dist` | 2 | **10** | DUP_IMAGE_EXACT: 1.00 / 1.00 $\rightarrow$ 1.00 / 1.00<br>DUP_IMAGE_NEAR: 1.00 / 0.50 (F1=0.67) $\rightarrow$ **1.00 / 0.67 (F1=0.80)** | `phash_dist` là lỗi bắt buộc dẫn đến hành động xóa ảnh (`remove_image`). Do đó, điều kiện tiên quyết là **Precision phải đạt tuyệt đối 1.00** (không được xóa nhầm ảnh thật). Ngưỡng 2 quá chặt làm sót ảnh biến đổi (Recall chỉ 50%). Ngưỡng 10 tăng Recall lên 67% mà vẫn giữ Precision 1.00. |
| `second_opinion.conf` | 0.25 | **0.60** | WRONG_CLASS: 0.56 / 0.83 $\rightarrow$ **0.62 / 0.83**<br>MISSING: 0.50 / 1.00 $\rightarrow$ **0.57 / 1.00**<br>LOOSE_BOX: 0.29 / 0.40 $\rightarrow$ 0.20 / 0.20<br>FALSE_POS: 0.36 / 1.00 $\rightarrow$ 0.36 / 1.00 | Tăng `conf` từ 0.25 lên 0.60 giúp tăng Precision của `WRONG_CLASS` từ 0.56 lên 0.62 và `MISSING` từ 0.50 lên 0.57 trong khi vẫn duy trì **Recall tối đa (100% MISSING, 83% WRONG_CLASS)**. Trên tập raw, việc này giúp loại bỏ 118 cảnh báo rác do model hallucinate ở mức tự tin thấp, giảm hàng đợi từ 143 xuống 125 ảnh, tập trung ngân sách 80 ảnh vào đúng các lỗi nghiêm trọng. |

### Điểm calibration có thể đánh lừa bạn:
1. **Bẫy quá khớp trên tập calib nhỏ với `phash_dist`:** Tập calib chỉ có 39 ảnh với 6 lỗi `DUP_IMAGE_NEAR` nhân tạo. Nếu chỉ nhìn vào bảng sweep calib để tối đa hóa F1, ta sẽ bị cám dỗ chọn `phash_dist = 16` (F1 đạt đỉnh 0.91, Recall 0.83). Tuy nhiên, khi kiểm chứng trực tiếp trên lô dữ liệu thật `data/raw`:
   - Tại `phash_dist = 16`, tổng số ảnh bị coi là trùng tăng vọt lên 26 ảnh. Trực quan hóa hình ảnh cho thấy dist=16 phạm lỗi nghiêm trọng: nó coi bức ảnh chụp vận động viên đánh tennis trên sân cỏ (`img_0011`) là trùng với bức ảnh hai người trượt tuyết trên núi băng (`img_0008`) do phân bố màu đồng nhất gây trùng mã băm perceptual!
   - Ngược lại, tại `phash_dist = 10`, cặp biên xa nhất là `img_0186` và `img_0061` (hai ảnh cùng chụp một cô gái ngồi trên ghế gỗ công viên với góc chụp và độ sáng biến đổi nhẹ) được gom chính xác mà không xóa nhầm bất kỳ ảnh khác biệt nào.
2. **Bẫy "Release giả" khi nâng `conf` quá cao:** Nếu nâng `second_opinion.conf = 0.80`, hàng đợi chỉ còn 102 ảnh, và sau khi duyệt 80 ảnh thì tỉ lệ cảnh báo còn lại giảm xuống 7.92% ($< 10\%$), đưa kết luận thành Release. Tuy nhiên, nhìn vào bảng calibration, ở `conf = 0.80` Recall của `MISSING` bị sụt thảm hại từ 100% xuống còn 75% (bỏ sót 25% vật thể không gán nhãn). Việc "Release" này là do công cụ kiểm tra bị mù chứ không phải do dữ liệu đã sạch. Vì vậy chọn `conf = 0.60` và báo cáo **Hold trung thực** là quyết định chuẩn xác.

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

### (a) Bằng chứng thực nghiệm chứng minh Quality Gate chặn đúng:
Khi chạy pipeline với cờ thử nghiệm không có người duyệt:
```bash
python -m pipeline.run --budget 0 --work work/run_nb --reports work/rep_nb --export-dir work/exp_nb
```
- **Kết quả:** Pipeline kết luận **REWORK**, in thông báo lỗi `còn 6 lỗi bắt buộc (ERROR) chưa được xử lý; tỉ lệ ảnh còn cảnh báo chưa duyệt 112/202 (55.45%) >= ngưỡng 10.00%`.
- **Mã thoát:** Hệ thống trả về mã thoát chính xác là **`20`** (mã chuẩn cho CI chặn merge/deploy).
- **Hành vi xuất:** Cửa chặn đã **ngăn chặn hoàn toàn việc xuất bộ dữ liệu**, thư mục `work/exp_nb` hoàn toàn không được tạo ra. Điều này chứng minh cửa chặn hoạt động độc lập và bảo vệ dữ liệu tuyệt đối trước các sai sót chưa được con người khắc phục.

### (b) Hai điểm mù pipeline không thể bắt được (kèm bằng chứng):
1. **Lỗi bounding box bị lệch góc hoặc lỏng nhẹ ($0.50 \le \text{IoU} < 0.65$):**
   - Theo định nghĩa hình học, nếu box nhãn và box dự đoán có $\text{IoU} \ge 0.50$, thuật toán coi như hai bên đã đồng thuận về mặt vị trí (`iou_match = 0.5`). Vì vậy, các trường hợp box vẽ hơi rộng hoặc viền mép bị thừa một khoảng nhỏ nhưng IoU vẫn đạt quanh mức 0.52 – 0.58 sẽ hoàn toàn lọt qua cửa kiểm tra mà không sinh bất kỳ cảnh báo nào.
2. **Các ca nhầm lẫn ngữ cảnh phức tạp mà cả nhãn lẫn model lớn đều bối rối:**
   - Trong ảnh `img_0078` và `img_0083` có các xe bán tải nhỏ (pickup) và xe tải van chở hàng nhỏ gắn biển quảng cáo Zeeman. Cả người gán nhãn ban đầu lẫn model `yolo26l` đều gặp khó khăn trong việc phân định ranh giới giữa `car` (xe con), `truck` (xe tải nhỏ) và `bus`. Nếu model lớn cũng dự đoán nhầm lớp theo cùng xu hướng của nhãn sai, cơ chế `second_opinion` sẽ không phát hiện được sự bất thường.
3. **Ảnh trùng bị cắt xén sâu hoặc biến đổi phi tuyến tính:**
   - Thuật toán `phash` tính toán dựa trên tần số không gian thấp (DCT). Nếu một ảnh bị cắt xén mất $> 80\%$ bối cảnh xung quanh rồi lật gương hoặc phóng to cục bộ một góc nhỏ, khoảng cách Hamming sẽ vượt quá ngưỡng 10, khiến pipeline không thể phát hiện được sự trùng lặp.

---

## 5. Train: raw vs clean (so sánh thực nghiệm)

Thí nghiệm huấn luyện được thực hiện trực tiếp trên GPU máy trạm **NVIDIA GeForce RTX 3050 Ti Laptop GPU**, sử dụng model `yolo26n.pt`, huấn luyện 20 epochs với batch size 16 trên độ phân giải 640px, đánh giá độc lập trên tập `data/test` (100 ảnh, nhãn người chuẩn).

Kết quả tổng hợp từ `submission/results/comparison.md`:

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| `raw` | 224 | 2 | 0.699 ± 0.034 | 0.508 ± 0.014 | 0.768 ± 0.063 | 0.614 ± 0.062 |
| `clean` | 202 | 2 | **0.748 ± 0.009** | **0.521 ± 0.001** | **0.790 ± 0.070** | **0.656 ± 0.039** |

Chênh lệch mAP50 (`clean` − `raw`) = **+0.049** (+4.9% mAP50 tuyệt đối).

Chi tiết mAP50 theo từng lớp qua các seed:
- `raw` (seed 0 / seed 1): car: 0.711 / 0.737 | person: 0.830 / 0.836 | **truck: 0.598 / 0.585** | **bus: 0.560 / 0.733**.
- `clean` (seed 0 / seed 1): car: 0.739 / 0.759 | person: 0.836 / 0.830 | **truck: 0.645 / 0.685** | **bus: 0.744 / 0.743**.

### Phân tích số liệu và kết luận trung thực:
1. **So sánh chênh lệch với độ nhiễu giữa các seed:**
   - Chênh lệch mAP50 đạt **+0.049**, vượt qua độ lệch chuẩn giữa 2 seed của biến thể `clean` ($\sigma = 0.009$) và nhỉnh hơn độ lệch của biến thể `raw` ($\sigma = 0.034$).
   - Đáng chú ý, pipeline kiểm nhãn giúp **ổn định hóa quá trình huấn luyện rõ rệt**: độ lệch chuẩn mAP50 giảm từ $0.034$ ở `raw` xuống chỉ còn $0.009$ ở `clean` (giảm gần 4 lần), và mAP50-95 ổn định tuyệt đối ($\sigma = 0.001$).
   - Tuy nhiên, vì tập test chỉ gồm 100 ảnh và số lượng seed mới ở mức $N=2$, dải biến thiên của raw $[0.665, 0.733]$ vẫn tiệm cận sát dải biến thiên của clean $[0.739, 0.757]$. Do đó, kết luận khoa học trung thực là: **Dữ liệu sau pipeline có xu hướng cải thiện hiệu năng rõ rệt và tăng tính ổn định của mô hình, nhưng cần mở rộng lên $\ge 5$ seeds và tập test lớn hơn để khẳng định ý nghĩa thống kê ở mức tin cậy $95\%$.**
2. **Hai nguyên nhân cốt lõi giải thích sự vượt trội của `clean`:**
   - **Cứu vãn hai lớp thiểu số (`truck` và `bus`):** Ở dữ liệu `raw`, lớp `truck` và `bus` bị nhiễu loạn nặng nề do các nhãn rác (`class_id` 93, 7, 4, -1) và bị gán nhầm lẫn sang `car`. Sau khi pipeline dọn sạch nhãn rác và người duyệt sửa đúng, mAP50 của lớp `truck` tăng từ trung bình $0.592 \rightarrow 0.665$ (**tăng +7.3%**), lớp `bus` tăng từ $0.647 \rightarrow 0.744$ (**tăng +9.7%**).
   - **Loại bỏ 5 ảnh rò rỉ tập test (`LEAK_TEST`) và 14 ảnh trùng lặp:** Dữ liệu `raw` có hiện tượng học vẹt các mẫu trùng lặp và ảnh rò rỉ. Khi loại bỏ, mô hình không còn bị phân tán trọng số vào các mẫu trùng byte/gần trùng, giúp khả năng tổng quát hóa trên tập test tăng lên, thể hiện qua Recall tăng từ $0.614 \rightarrow 0.656$ (+4.2%).

---

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối cùng:
- Quyết định hiện tại: **HOLD** (chỉ cho phép xuất bản nháp phục vụ R&D thử nghiệm nội bộ, nghiêm cấm triển khai release ra môi trường sản xuất).
- **Hành động cụ thể để chuyển thành RELEASE:**
  1. Cấp bổ sung ngân sách duyệt thủ công từ 80 ảnh lên **125 ảnh** để duyệt toàn bộ 45 ảnh còn lại trong hàng đợi `05_review_queue.csv`.
  2. Hoặc tập trung phân công người kiểm tra đúng **38 ảnh còn cảnh báo** được liệt kê trong `submission/reports/07_error_list_v3.csv` (chủ yếu là 20 box lỏng `POSSIBLE_LOOSE_BOX` và 13 box thiếu `POSSIBLE_MISSING`). Khi số ảnh cảnh báo chưa duyệt giảm xuống dưới 20 ảnh (tỉ lệ $< 10\%$), pipeline chạy lại sẽ tự động chuyển sang **Release**.

### (b) Ghi chú sử dụng AI (tuân thủ 3 yêu cầu của RULES.md):
1. **Prompt chính:** *"Viết module Python 3 `pipeline/steps/autofix.py` nhận đầu vào `(ds, issues, cfg)` để sửa tự động các lỗi bắt buộc `ERROR`. Quy tắc: `drop_line` cho BAD_FORMAT/BAD_CLASS_ID/BOX_ZERO/DUP_BOX; `clip_box` cho BOX_OUT_OF_IMAGE về [0,1]; `needs_label` cho MISSING_LABEL_FILE (không tạo file nhãn); `rename_classes` cho BAD_CLASS_NAME; `remove_image` cho DUP_IMAGE_*/LEAK_TEST. Yêu cầu an toàn: gom lỗi theo file nhãn để không lệch số dòng gốc khi xóa/sửa nhiều dòng; xóa dòng luôn ưu tiên hơn cắt box; không chạm vào file trong `data/raw`; trả về danh sách dict các thao tác để ghi `03_fixes.csv`."*
2. **Cách kiểm tra:** Chạy toàn bộ 79 bài test tự động (`pytest -q`), chạy script `pipeline.calibrate` trên bộ dữ liệu `data/calib/` có sẵn nhãn chèn lỗi để đối chiếu ma trận nhầm lẫn (Confusion Matrix), và dùng `scripts/viz_labels.py` vẽ trực tiếp các box trước và sau khi sửa để kiểm tra bằng mắt.
3. **Một lần AI đề xuất sai và cách sửa:** Trong phiên bản đầu tiên của hàm `fix()`, AI đã lặp qua từng issue và mở file nhãn để sửa trực tiếp từng dòng. Khi một file có nhiều dòng lỗi (ví dụ dòng 2 và dòng 4 cùng bị lỗi), việc xóa dòng 2 trước đã làm cho dòng 4 cũ bị đẩy lên thành dòng 3, dẫn đến việc xóa nhầm dòng dữ liệu hợp lệ phía sau! Tôi đã phát hiện ra lỗi này khi chạy test `test_drop_several_lines_in_one_file_uses_original_numbers`, và đã tái cấu trúc code: gom toàn bộ số dòng cần xóa/sửa theo từng file (`defaultdict(set)`), đọc toàn bộ nội dung file một lần, đối chiếu theo đúng chỉ số dòng gốc `line_no`, rồi mới ghi đè file một lần duy nhất.

---

## 7. Phần thưởng bổ sung

### (a) Thưởng +3: Check mới phát hiện tỉ lệ khung hình bất thường và mất cân bằng lớp
Đã triển khai module mới `pipeline/checks/aspect_imbalance.py` cùng bộ kiểm thử toàn diện `tests/test_aspect_imbalance.py` (4/4 test passed):
- **`BOX_EXTREME_ASPECT` (WARN):** Phát hiện các bounding box có tỉ lệ khung hình quá dị dạng $\max(w/h, h/w) > 8.0:1$. Khi quét trên dataset sau pipeline, check phát hiện 2 box bất thường:
  - `img_0042` dòng 5: tỉ lệ $9.58:1$ ($25.1 \times 240.8\text{ px}$) — cột đèn giao thông hoặc dải rào chắn hẹp bị gán nhầm.
  - `img_0124` dòng 6: tỉ lệ $9.11:1$ ($118.4 \times 13.0\text{ px}$) — gờ chắn đường bị gán dẹt.
- **`CLASS_IMBALANCE` (WARN):** Kiểm tra tỉ số chênh lệch số lượng box giữa lớp nhiều nhất và lớp ít nhất trên toàn bộ dataset:
  - Dataset hiện tại có 574 box `person` so với chỉ 32 box `bus` (chênh lệch **$17.94\times$**, vượt ngưỡng cảnh báo $10.0\times$). Cảnh báo này giúp đội ngũ huấn luyện áp dụng kỹ thuật cân bằng lớp (focal loss / class-weighted loss) kịp thời.

### (b) Thưởng +2: Kiểm tra và lọc box nhỏ bất thường bằng CVAT
Đã chuẩn bị trọn gói bộ công cụ CVAT kit tại `work/cvat_kit/` gồm cấu hình nhãn `labels.json`, 20 ảnh tiêu biểu và gói nhãn `yolo11_labels.zip`:
1. **Thiết lập bộ lọc CVAT:** Mở task CVAT với nhãn từ `cvat/labels.json`, tạo bộ lọc *Filter*: `width < 20` (hoặc `height < 20`).
2. **Đối chiếu số liệu giữa bộ lọc CVAT và pipeline:**
   - Trong số 20 ảnh đưa vào CVAT, bộ lọc `width < 20` phát hiện tổng cộng 25 box trên 9 ảnh (`img_0026`: 6 box, `img_0051`: 3 box, `img_0069`: 2 box, `img_0161`: 3 box, `img_0183`: 1 box, `img_0020`: 3 box, `img_0053`: 1 box, `img_0135`: 2 box, `img_0031`: 3 box có `height < 20`).
   - Trong khi đó, mã kiểm tra `BOX_TINY` của pipeline sử dụng ngưỡng khắt khe hơn: cạnh ngắn $\min(w, h) < 12\text{ px}$, chỉ bắt 7 box nhỏ nhất (ví dụ `img_0161` có 3 box, `img_0026` có 1 box cạnh 11.4px, `img_0051` có 1 box cạnh 8.9px).
   - **Nhận xét:** Ngưỡng $20\text{ px}$ của CVAT giúp người duyệt nhìn thấy cả những người đứng ở hậu cảnh rất xa (tầm 15–19px) mà pipeline coi là hợp lệ. CVAT cho phép người kiểm tra bấm phím tắt `Del` để xóa nhanh các box này hoặc giữ lại nếu thấy đặc trưng người vẫn nhìn rõ được bằng mắt.
3. **Ý nghĩa của thuộc tính `can_review`:**
   - Trong thực tế gán nhãn, người gán nhãn (annotator) bật cờ `can_review = true` cho các ca khó, bị che khuất một phần hoặc phân vân giữa xe con và xe tải nhỏ để đề nghị kiểm duyệt viên (reviewer) kiểm tra lại.
   - Trong pipeline tự động, cơ chế này tương đương trực tiếp với việc sinh ra các cảnh báo `WARN` (`POSSIBLE_WRONG_CLASS`, `POSSIBLE_LOOSE_BOX`, `POSSIBLE_FALSE_POS`) và đưa vào hàng đợi ưu tiên `05_review_queue.csv` để chuyển tiếp đến mắt người duyệt.
