# [Draft] Thử nghiệm Hybrid AI Model cho Laptop yếu (Groq/Gemini + SLM)

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu (Objectives)
*   **Giảm tải tài nguyên cục bộ:** Chuyển các tác vụ suy luận nặng (Semantic Verification) lên Cloud (qua API Free Tier) để laptop yếu (RAM 8GB) có thể chạy mượt mà.
*   **Duy trì hiệu năng & độ chính xác:** Tận dụng tốc độ của Groq/Gemini Flash để giảm độ trễ (latency) và tăng độ chính xác so với việc chạy model nhỏ cục bộ.
*   **Đảm bảo tính riêng tư tùy chọn:** Cung cấp chế độ "Privacy Mode" để chạy hoàn toàn offline (fallback về SLM local) khi xử lý mã nguồn nhạy cảm.

## 2. Giải pháp Đề xuất (Proposed Solution)
*   **Kiến trúc Hybrid Router:** Cập nhật module `core/ai` để hỗ trợ đa backend:
    *   **Online Tier (Mặc định cho Open Source):** Sử dụng API của Groq (Llama 3) hoặc Google Gemini 1.5 Flash.
    *   **Offline Tier (Privacy Mode):** Sử dụng `llama.cpp` chạy các model đã lượng tử hóa (Quantized 4-bit) như Phi-3-mini hoặc Qwen2.5-3b.
*   **Cơ chế hoạt động:**
    1.  User cấu hình `nsss.yaml`: `mode: hybrid` hoặc `mode: local-only`.
    2.  Hệ thống phân tích tĩnh (Static Analysis) chạy trước để lọc ứng viên.
    3.  Các ứng viên nghi ngờ được gửi đến `HybridRouter`.
    4.  Nếu `local-only`: gọi `llama.cpp`.
    5.  Nếu `hybrid`: gọi API (Groq/Gemini). Nếu lỗi mạng/rate limit -> fallback về `local-only`.

## 3. Phân tích Tác động (Impact Analysis)
*   **Hiệu năng (Performance):**
    *   **Online:** Tốc độ phản hồi cực nhanh (<1s cho Groq), không tốn CPU/RAM laptop.
    *   **Offline:** Tốn khoảng 4-6GB RAM và CPU cao, tốc độ chậm hơn (5-10s/query) trên máy yếu.
*   **Bảo mật (Security):**
    *   **Online:** Snippet code được gửi ra ngoài. Cần cảnh báo rõ ràng cho user.
    *   **Offline:** An toàn tuyệt đối, dữ liệu không rời khỏi máy.
*   **Vận hành (Ops):**
    *   Cần quản lý API Keys (Env vars).
    *   Cần cơ chế tải/quản lý file model `.gguf` cho chế độ offline.

## 4. Chi phí & Tài nguyên (Cost & Resources)
*   **Free Tier:**
    *   **Groq:** Miễn phí hào phóng cho Llama 3 (tại thời điểm 2026).
    *   **Gemini Flash:** Miễn phí với giới hạn rate limit cao.
*   **Hardware:**
    *   **Online:** Laptop RAM 4GB+ là đủ.
    *   **Offline:** Yêu cầu tối thiểu RAM 8GB (cho Phi-3/Qwen-3B).

## 5. Rủi ro & Kế hoạch Rollback (Risks & Mitigation)
| Rủi ro | Mức độ | Biện pháp giảm thiểu |
|---|---|---|
| API Rate Limit (Free Tier) | Cao | Tự động fallback sang Local SLM hoặc bỏ qua bước semantic (fail-open/fail-closed config). |
| Lộ lọt dữ liệu (User quên bật Privacy Mode) | Cao | Mặc định là `local-only` nếu không thấy API Key. Hiển thị warning to rõ khi chạy mode Online. |
| Model Local quá nặng gây treo máy | Trung bình | Dùng model siêu nhỏ (Phi-3-mini 3.8B) và giới hạn thread CPU. |

## 6. Tiêu chí Nghiệm thu (Success Criteria)
*   Tích hợp thành công SDK của Groq/Gemini và `llama-cpp-python`.
*   Chạy trọn vẹn scan trên repo benchmark `vulnerable_flask_app` với RAM sử dụng < 6GB (chế độ Hybrid).
*   Độ chính xác (F1 Score) của chế độ Online tương đương hoặc hơn GPT-3.5.
*   Cơ chế Fallback hoạt động: Rút dây mạng -> Tự chuyển sang Local SLM.

## 7. Checklist Triển khai
- [ ] Research: Chọn library client tối ưu (langchain vs native sdk).
- [ ] Prototype: Viết script test kết nối Groq & Gemini Flash.
- [ ] Prototype: Viết script test `llama.cpp` với Phi-3-mini 4-bit.
- [ ] Update Architecture: Thiết kế lại interface `LLMProvider` trong code NSSS.
- [ ] Draft Implementation Plan.
