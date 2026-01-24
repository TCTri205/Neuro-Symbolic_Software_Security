# RUNBOOK - Neuro-Symbolic Software Security

Tài liệu hướng dẫn vận hành và bảo trì hệ thống Neuro-Symbolic Software Security (V2.3).

## 1. Quy trình Triển khai (Deployment Procedures)

Hệ thống hỗ trợ hai hình thức triển khai chính:

### Centralized AI Server (Khuyến nghị)
1.  **Cài đặt GPU Server:** Triển khai API phục vụ LLM (Self-hosted) hoặc cấu hình Gateway tới OpenAI/Anthropic.
2.  **Cài đặt Backend:** Triển khai các module Stage 1, 2, 3 trên hạ tầng CI/CD hoặc Server riêng biệt.
3.  **Cấu hình Privacy Masking:** Đảm bảo mã hóa tên biến nhạy cảm trước khi gửi tới Cloud LLM.

### Local Deployment
*   Sử dụng cho mục đích Audit nội bộ hoặc môi trường Air-gapped.
*   Yêu cầu GPU có đủ VRAM để chạy các model GNN và Local LLM. **Qwen2.5-Coder-7B** được khuyến nghị là Canonical Model cho bước kiểm chứng ngữ nghĩa (Inference hoặc Fine-tuned). DeepSeek-Coder/Llama 3 có thể sử dụng làm phương án dự phòng.

## 2. Giám sát và Cảnh báo (Monitoring & Alerts)

*   **Token Usage:** Theo dõi chi phí Token nếu sử dụng Cloud API. Hệ thống có cơ chế **Circuit Breaker** để ngắt scan nếu chi phí vượt ngưỡng.
*   **Scan Latency:** Giám sát thời gian phân tích của từng Stage, đặc biệt là Stage 4 (LLM Verification).
*   **False Positive Rate:** Theo dõi phản hồi từ Developer thông qua Feedback Loop để tinh chỉnh Risk Ranker.

## 3. Các vấn đề Thường gặp và Cách xử lý (Common Issues)

| Vấn đề | Nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| **Đứt gãy luồng SSA** | Python dynamic dispatch phức tạp hoặc Monkey Patching. | Kiểm tra log "Unscannable Area", thực hiện review thủ công hoặc bổ sung Framework Plugin. |
| **Token Cost quá cao** | Speculative Expansion quá rộng hoặc file quá lớn. | Điều chỉnh `Hard Limits` cho Speculative Expansion hoặc dùng `Hierarchical Summarization`. |
| **Kết quả không nhất quán** | LLM Hallucination hoặc tính ngẫu nhiên. | Đảm bảo `temperature=0` và kiểm tra `Strict Caching`. |

## 4. Quy trình Khôi phục (Rollback Procedures)

1.  **Dữ liệu Đồ thị:** Khôi phục từ bản sao lưu gần nhất của Graph Persistence (Neo4j/Disk Cache).
2.  **Cấu hình:** Revert các thay đổi trong file `.env` hoặc `settings.py`.
3.  **Hệ thống:** Nếu deploy qua Docker, thực hiện rollback về Image version ổn định trước đó.

---
**Maintenance:** Hệ thống cần được cập nhật Librarian Profiles định kỳ để nhận diện các thư viện mới.
