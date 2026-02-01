# NSSS Development Manifesto

Tài liệu này định nghĩa các nguyên tắc cốt lõi, đóng vai trò là "kim chỉ nam" cho mọi quyết định kỹ thuật và phát triển trong dự án NSSS.

## 1. Privacy First (Quyền riêng tư là trên hết)
*   Mã nguồn của người dùng là tài sản nhạy cảm.
*   Hệ thống phải cung cấp chế độ hoạt động hoàn toàn Offline (Air-gapped) khi cần thiết.
*   Dữ liệu gửi lên Cloud (qua API) phải được sự đồng ý của người dùng và được tối giản hóa (ví dụ: chỉ gửi đoạn mã nghi ngờ thay vì toàn bộ file).

## 2. Low-Spec Optimization (Tối ưu cho cấu hình thấp)
*   Mọi tính năng phải được thiết kế để có thể chạy được trên máy tính cá nhân cấu hình trung bình/yếu (RAM 8GB-16GB, không GPU mạnh).
*   Sử dụng chiến lược "Offloading": Đẩy các tác vụ nặng (scan toàn diện, AI suy luận sâu) lên CI/CD (Cloud) hoặc API chuyên dụng.
*   Ưu tiên các thư viện hiệu năng cao (Rust/C++ bindings) và model đã lượng tử hóa (Quantized).

## 3. Neuro-Symbolic Balance (Cân bằng Nửa-Ký hiệu)
*   **Symbolic (Tĩnh):** Đóng vai trò là "Bộ lọc" (Filter) - nhanh, chính xác tuyệt đối về mặt logic, không ảo giác.
*   **Neuro (AI):** Đóng vai trò là "Người thẩm định" (Verifier) - hiểu ngữ cảnh, xử lý các trường hợp mơ hồ mà luật tĩnh không bắt được.
*   Nguyên tắc: AI không bao giờ thay thế phân tích tĩnh, nó chỉ bổ trợ để giảm False Positives.

## 4. Engineering First, AI Second
*   Xây dựng hệ thống ổn định, có test coverage cao và kiến trúc tốt trước khi áp dụng các kỹ thuật AI phức tạp.
*   AI phải được coi là một module có thể thay thế hoặc tắt bỏ mà không làm hỏng tính năng cơ bản của hệ thống.
