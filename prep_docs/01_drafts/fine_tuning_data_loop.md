# [Draft] Kế hoạch Tinh chỉnh (Fine-tuning) & Data Loop

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu (Objectives)
*   Tạo ra một chu trình khép kín: **Quét -> Phát hiện sai -> Học -> Cải thiện**.
*   Tăng độ chính xác (Precision) của lớp AI, giảm thiểu cảnh báo giả (False Positives) đặc thù của dự án.

## 2. Quy trình Data Loop (Vòng lặp dữ liệu)
### Bước 1: Thu thập (Collection)
*   **Nguồn:**
    1.  **User Feedback:** Khi user đánh dấu "Ignore" hoặc "False Positive" trong IDE/Dashboard.
    2.  **Commit Fixes:** Tự động trích xuất các commit có từ khóa "fix security", "cve" từ git history.
*   **Lưu trữ:** Lưu dạng cặp `(Code Snippet, Label)` vào file JSONL tại `data/feedback_loop/`.
    *   `Label`: `VULNERABLE` hoặc `SAFE`.

### Bước 2: Chuẩn bị Dataset (Preparation)
*   Sử dụng các Public Datasets làm nền tảng (Base Knowledge):
    *   **Big-Vuln:** Hàng nghìn mẫu code lỗ hổng thực tế.
    *   **SecurityEval:** Các mẫu prompt gây lỗi bảo mật.
*   Trộn (Mix) dữ liệu nội bộ (thu thập ở B1) với Public Datasets theo tỷ lệ 1:5 (1 nội bộ, 5 công khai) để tránh overfitting.

### Bước 3: Fine-tuning (Tinh chỉnh)
*   **Công cụ:** Sử dụng **Unsloth** (thư viện tối ưu hóa Llama/Mistral) trên **Google Colab (Free GPU T4)**.
*   **Phương pháp:** LoRA (Low-Rank Adaptation) - chỉ train một phần nhỏ tham số (adapter) để tiết kiệm tài nguyên.
*   **Base Model:** Phi-3-mini hoặc Llama-3-8B.

### Bước 4: Đánh giá & Triển khai (Eval & Deploy)
*   So sánh model cũ và mới trên tập `holdout` (dữ liệu chưa từng thấy).
*   Nếu F1-Score tăng > 2% -> Convert sang GGUF và cập nhật vào hệ thống (Local/Offline mode).

## 3. Công cụ & Tài nguyên (Free Tier)
*   **Training:** Google Colab (Free Tier), Kaggle Notebooks (2x T4 GPU).
*   **Framework:** Unsloth (nhanh hơn 2x, ít RAM hơn 70%), Hugging Face TRL.
*   **Tracking:** Weights & Biases (W&B) bản cá nhân (Personal Free).

## 4. Checklist Triển khai
- [ ] Tạo thư mục `data/feedback_loop`.
- [ ] Viết script `scripts/collect_feedback.py` để trích xuất dữ liệu từ SARIF report.
- [ ] Chuẩn bị Notebook mẫu trên Colab để chạy Unsloth với dataset demo.
