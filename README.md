# Neuro-Symbolic Software Security (Python Edition)

> **Kiến trúc V2.3 Finalized** - Hệ thống phân tích bảo mật mã nguồn mở theo triết lý "Engineering First, AI Second".

## 🌟 Giới Thiệu
Dự án này là một công cụ **Static Application Security Testing (SAST)** thế hệ mới dành cho Python. Không giống như các công cụ thuần AI (dễ ảo giác) hay thuần Rule (nhiều báo ảo), chúng tôi kết hợp cả hai:
1.  **Engineering (Nền tảng):** Sử dụng SSA (Static Single Assignment) và CFG để hiểu luồng dữ liệu một cách chính xác.
2.  **AI (Tăng cường):** Sử dụng LLM (Canonical: Qwen2.5-Coder-7B) để kiểm chứng ngữ nghĩa (Semantic Verification) các điểm rủi ro cao.

## 📚 Tài Liệu Kỹ Thuật (Docs)

Hệ thống tài liệu được tổ chức trong thư mục `docs/`:

*   **[00. Tổng Quan Kiến Trúc Toàn Diện](docs/00_Tong_Quan_Kien_Truc_Toan_Dien.md)**: Bức tranh toàn cảnh về V2.3.
*   **[01. Tầm Nhìn Dự Án](docs/01_Tong_Quan_Du_An.md)**: Tại sao chúng ta cần Neuro-Symbolic?
*   **[02. Bản Đồ Lỗ Hổng](docs/02_Ban_Do_Lo_Hong_Python.md)**: Các lỗi Python đặc thù (Deserialization, Injection).
*   **[03. Chiến Lược Dữ Liệu](docs/03_Chien_Luoc_Du_Lieu.md)**: Cách chúng ta nén code thành "Semantic Signatures".
*   **[04. Stack Công Nghệ](docs/04_Kien_Truc_He_Thong.md)**: Chi tiết các thành phần (Semgrep, GNN, Qwen2.5).
*   **[06. Chiến Lược Model & Fine-tuning](docs/06_Chien_Luoc_Model_FineTune.md)**: Tuyển chọn và tinh chỉnh mô hình Verifier (Canonical: Qwen2.5-Coder-7B).

### 🚀 Dành Cho Sinh Viên & Máy Yếu (Low-Resource Edition)
Nếu bạn không có GPU khủng hay kinh phí thuê OpenAI API, hãy xem ngay bộ tài liệu tối ưu hóa này:

*   **[05. Kiến Trúc Low-Resource](docs/05_Low_Resource_Architecture.md)**: Chạy hệ thống với chi phí 0đ (Laptop + Colab Free).
*   **[05a. Giao Thức Client-Server](docs/05a_Client_Server_Protocol.md)**: Chuẩn kết nối JSON.
*   **[05b. Demo Walkthrough](docs/05b_Demo_Walkthrough.md)**: **Kịch bản Demo thực tế** (Kèm code mẫu).

## 🛠️ Cài Đặt Nhanh

### Yêu cầu
*   Python 3.9+
*   Google Colab (cho Low-Resource Mode)

### Chạy Demo (Low-Resource)
Xem hướng dẫn chi tiết tại [docs/05b_Demo_Walkthrough.md](docs/05b_Demo_Walkthrough.md).

```bash
# 1. Tại Laptop (Client)
python demo_client.py

# 2. Tại Colab (Server)
# Chạy notebook để khởi tạo API với ngrok
```

## 🤝 Đóng Góp
Xem [CONTRIB.md](docs/CONTRIB.md) để biết quy trình Pull Request.

---
**Trạng thái:** ✅ V2.3 Ready for Engineering | 📅 Updated: Jan 2026
