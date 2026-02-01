# [Draft] Kế hoạch Tự động hóa DevSecOps cho Laptop yếu

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu (Objectives)
*   Xây dựng hệ thống "Hàng rào bảo vệ" nhiều lớp mà không làm nặng máy dev.
*   Tự động hóa hoàn toàn việc báo cáo lỗi bảo mật lên GitHub Security tab.

## 2. Giải pháp Đề xuất (Proposed Solution)
*   **Lớp 1 (Siêu nhẹ - Local):** Cài đặt `pre-commit` với các hook:
    *   `ruff`: Lint và format code Python siêu nhanh (viết bằng Rust).
    *   `check-added-large-files`: Ngăn chặn commit nhầm file model nặng.
    *   `detect-private-key`: Ngăn chặn lộ mã bí mật cơ bản.
*   **Lớp 2 (Trung bình - CI/CD):** GitHub Actions `nsss-scan-lite.yml`:
    *   Chạy `make scan-fast` trên Cloud.
    *   Sử dụng SARIF format để đẩy kết quả lên GitHub Code Scanning.

## 3. Phân tích Tác động (Impact Analysis)
*   **Hiệu năng:** `pre-commit` chỉ tốn khoảng 1-2 giây mỗi lần commit, gần như không cảm nhận được trên máy yếu.
*   **Vận hành:** Cần cài đặt lệnh `pre-commit install` một lần duy nhất.

## 4. Chi phí & Tài nguyên (Cost & Resources)
*   Hoàn toàn miễn phí (GitHub Actions free tier cho Public/Private repos).

## 5. Tiêu chí Nghiệm thu (Success Criteria)
*   Mọi commit đều được kiểm tra lint tự động.
*   Mọi Pull Request đều hiển thị bảng báo cáo bảo mật của NSSS trong phần check.
*   Dashboard GitHub Security hiển thị được các lỗ hổng tìm thấy.

## 6. Checklist Triển khai
- [ ] Tạo file `.pre-commit-config.yaml` từ mẫu trong `assets/`.
- [ ] Chạy thử lệnh `pre-commit run --all-files`.
- [ ] Kiểm tra tính năng upload SARIF trên repo GitHub thực tế.
