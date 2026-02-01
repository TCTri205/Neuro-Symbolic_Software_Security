# ADR-001: Chiến lược Hybrid Cloud-Local cho Laptop yếu

*   **Trạng thái:** ✅ Đã chốt
*   **Người quyết định:** NSSS Architecture Team
*   **Ngày:** 01/02/2026

## Bối cảnh (Context)
Dự án NSSS cần phát triển các tính năng phân tích sâu (Semantic Verification) sử dụng LLM. Tuy nhiên, việc chạy các LLM đủ thông minh ngay trên máy cá nhân cấu hình thấp (RAM 8GB-16GB, không GPU) gây ra các vấn đề:
1.  Máy bị treo, không thể làm việc khác.
2.  Tốc độ scan cực chậm (latency cao).
3.  Độ chính xác thấp do chỉ chạy được các model SLM rất nhỏ.

## Quyết định (Decision)
Chúng ta sẽ áp dụng mô hình Hybrid (Lai) giữa Cloud và Local:

1.  **Phát triển & CI/CD:**
    *   Sử dụng **GitHub Actions** làm môi trường scan chính. Cloud runner của GitHub có tài nguyên ổn định, không tốn pin/tài nguyên laptop của dev.
2.  **Kiểm tra tại chỗ (Local):**
    *   Chỉ sử dụng **Pre-commit hooks** và các bộ lọc tĩnh siêu nhẹ (Linter, Regex-based rules).
    *   Các lớp phân tích nặng (Taint analysis, SSA) chỉ chạy khi thực sự cần thiết hoặc chạy trên 1 file đơn lẻ.
3.  **Lớp Trí tuệ nhân tạo (AI Layer):**
    *   Mặc định sử dụng **API Free Tier (Groq, Gemini Flash)**. Điều này cho phép máy yếu tiếp cận được các model mạnh nhất (Llama 3 70B, Gemini 1.5 Pro) với tốc độ tức thì.
    *   Cung cấp chế độ **Privacy/Offline** sử dụng `llama.cpp` và model lượng tử hóa (Phi-3-mini) cho các trường hợp đặc biệt, dù chấp nhận latency cao.

## Hệ quả (Consequences)
*   **Tích cực:**
    *   Dev có thể làm việc liên tục mà không lo máy bị đơ.
    *   Tận dụng được các model AI hàng đầu thế giới mà không tốn chi phí phần cứng.
    *   Giảm nợ kỹ thuật bằng cách tập trung vào logic lõi thay vì tối ưu hóa engine chạy model local.
*   **Tiêu cực:**
    *   Cần kết nối Internet để đạt hiệu năng tốt nhất.
    *   Cần quản lý API Key và chi phí (dù hiện tại dùng Free Tier).
