# CONTRIBUTING GUIDE - Neuro-Symbolic Software Security

Chào mừng bạn đến với dự án Neuro-Symbolic Software Security. Tài liệu này hướng dẫn cách thiết lập môi trường và đóng góp cho dự án theo tiêu chuẩn V2.3.

## 1. Quy trình Phát triển (Development Workflow)

Dự án tuân thủ mô hình **Defense-in-Depth** với quy trình xử lý 4 giai đoạn:

1.  **Phân tích Tĩnh (SSA & Context):** Xây dựng đồ thị SSA và CFG từ mã nguồn Python.
2.  **Tra cứu Thư viện (The Librarian):** Đối chiếu với tri thức thư viện bên thứ 3.
3.  **Phân tầng Xử lý (Tiered Analysis):** Sử dụng Semgrep và GNN để lọc và xếp hạng rủi ro.
4.  **Kiểm chứng Ngữ nghĩa (LLM):** Sử dụng LLM (Qwen2.5/DeepSeek) để xác nhận lỗi thông qua Semantic Signatures.

### Các bước đóng góp:
*   **Bước 1:** Fork và tạo nhánh mới (`feature/`, `bugfix/`).
*   **Bước 2:** Implement logic (ưu tiên tách biệt Framework logic thành các Plugin).
*   **Bước 3:** Viết Unit Test cho các thành phần mới.
*   **Bước 4:** Chạy kiểm tra ở chế độ **Audit Mode** để đảm bảo không có lỗi phát sinh.

## 2. Thiết lập Môi trường (Environment Setup)

### Yêu cầu hệ thống:
*   **Python:** 3.9+
*   **Custom AST Builder:** (Nằm trong repo) Công cụ chính để xây dựng đồ thị SSA và CFG cho Python.
*   **Joern (Optional):** Có thể sử dụng để trích xuất CPG cho các thành phần đa ngôn ngữ hoặc phân tích sâu.
*   **GPU:** Khuyến nghị cho việc chạy GNN local hoặc Centralized AI Server access.

### Các bước cài đặt:
1.  Clone repository.
2.  Khởi tạo virtual environment: `python -m venv venv`.
3.  Cài đặt dependencies: (Hiện tại dự án đang trong giai đoạn cấu trúc, vui lòng tham khảo `pyproject.toml` khi có).
4.  Cấu hình biến môi trường: Sao chép `.env.example` thành `.env` và điền các API Key cần thiết.

## 3. Các Script Khả dụng (Available Scripts)

*(Lưu ý: Các script sẽ được cập nhật chính thức trong `package.json` hoặc `makefile`)*

*   `npm run scan:fast`: Chạy CI/CD Mode (Chỉ Stage 1 & 3).
*   `npm run scan:full`: Chạy Audit Mode (Toàn bộ 4 Stage).
*   `npm run test`: Chạy bộ test suite.
*   `npm run lint`: Kiểm tra format và coding style.

## 4. Quy trình Kiểm thử (Testing Procedures)

*   **Unit Tests:** Kiểm tra từng module riêng lẻ (Parser, SSA Builder).
*   **Integration Tests:** Kiểm tra luồng dữ liệu xuyên suốt các Stage.
*   **Regression Tests:** Đảm bảo các lỗ hổng đã fix không xuất hiện lại (sử dụng Baseline Mode).

---
**Liên hệ:** Mọi thắc mắc vui lòng tạo Issue trên hệ thống quản lý mã nguồn.
