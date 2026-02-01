# [Draft] Giao thức Đánh giá Chuẩn (Benchmarking Protocol)

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu
*   Đảm bảo tính khách quan và khoa học khi đánh giá hiệu năng của NSSS.
*   Thiết lập một "thước đo" chuẩn (Baseline) để so sánh giữa các phiên bản NSSS (Regression Test).

## 2. Tập Dữ liệu Kiểm thử (Testbeds)
### A. Synthetic Benchmarks (Nhân tạo)
*   **OWASP Benchmark (Python):** Các lỗi cổ điển (SQLi, XSS, CmdInj).
*   **Sard (NIST):** Bộ dữ liệu chuẩn của chính phủ Mỹ.
*   *Mục tiêu:* Đo độ bao phủ (Recall) lý thuyết.

### B. Real-world Benchmarks (Thực tế)
*   **Target Repos:** Chọn 5-10 repo open-source phổ biến (VD: `django-cms`, `flask-appbuilder`) ở phiên bản cũ đã biết có lỗ hổng (Known CVEs).
*   *Mục tiêu:* Đo độ chính xác thực tế (Precision) và khả năng xử lý code phức tạp.

## 3. Các chỉ số đo lường (Metrics)
*   **True Positive (TP):** Báo đúng lỗi thật.
*   **False Positive (FP):** Báo lỗi nhưng code an toàn (Gây phiền nhiễu).
*   **False Negative (FN):** Có lỗi nhưng không báo (Nguy hiểm nhất).
*   **Recall (Độ nhạy):** $TP / (TP + FN)$ - Bắt được bao nhiêu % lỗi.
*   **Precision (Độ chính xác):** $TP / (TP + FP)$ - Tin cậy đến mức nào.
*   **F1-Score:** Trung bình điều hòa của Recall và Precision.
*   **Resource Usage:** RAM tối đa, Thời gian scan trung bình/1k LOC.

## 4. Quy trình thực hiện (Procedure)
1.  **Baseline:** Chạy Semgrep và Bandit trên tập Testbeds -> Lưu kết quả.
2.  **Experiment:** Chạy NSSS (Hybrid Mode) trên tập Testbeds.
3.  **Comparison:** So sánh kết quả NSSS vs Baseline.
4.  **Analysis:** Phân tích các ca NSSS làm tốt hơn (nhờ AI/SSA) và các ca làm tệ hơn.

## 5. Checklist Triển khai
- [ ] Tải bộ dữ liệu OWASP Benchmark.
- [ ] Viết script `scripts/run_benchmark.py` để tự động chạy và tính toán Metrics.
- [ ] Tạo bảng Excel/CSV mẫu để so sánh kết quả.
