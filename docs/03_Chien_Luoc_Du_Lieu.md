# 03. Chiến Lược Dữ Liệu & Tri Thức (Data & Knowledge Strategy)

Trong V2.3, dữ liệu không chỉ là Code mà còn là **Ngữ cảnh (Context)** và **Tri thức chuyên gia (Librarian)**. Chiến lược: **"Context-Aware & Deterministic Summarization"**.

## 1. Nguồn Dữ Liệu & Tri Thức (Sources)

### A. Librarian Database (Tri thức thư viện)
*   **Verified Profiles:** Metadata về các thư viện phổ biến (Flask, Django, Requests) bao gồm các Source/Sink/Sanitizer đã được định nghĩa.
*   **Community-First:** Ưu tiên tải các profile đã được cộng đồng kiểm duyệt.
*   **Version Pinning:** Lưu trữ profile theo từng phiên bản cụ thể (ví dụ: `Safe in 2.0, Vulnerable in 1.9`).
*   **AI Fallback (Shadow Profiles):** Khi gặp thư viện lạ, LLM sẽ đọc Docs/Source để tạo Stub tạm thời với các nhãn Taint dự kiến.

### B. Context Data (Dữ liệu cấu hình & Môi trường)
*   **Environment Context:** `requirements.txt`, `pyproject.toml`, `.env`, `Dockerfile`, Helm Charts.
*   **Framework Rules:** Tập hợp các quy tắc định tuyến (Routing) và cơ chế Injection của từng framework (Django Signals, FastAPI Dependency).
*   **Privacy Masks:** Bảng ánh xạ mã hóa (Anonymization Map) dùng cho Privacy Masking (ví dụ: `func_payment` -> `func_A`).

### C. Semantic Signatures (Dữ liệu cho LLM)
*   **Deterministic Signature Schema:** Trích xuất đặc tả kỹ thuật cứng:
    *   `Input -> Output`
    *   `Side-Effects` (DB access, Network)
    *   `Taint-Propagation` (Tainted/Clean)
*   **Few-shot Examples:** Các đoạn code mẫu (Positive/Negative) để hướng dẫn LLM.

## 2. Pipeline Tiền Xử Lý (Data Preprocessing V2.3)
Quy trình biến đổi code thô thành dữ liệu có cấu trúc:

1.  **Bước 1: SSA Transformation (Tĩnh hóa)**
    *   Tách biến thành các phiên bản (`a_1`, `a_2`) theo dõi trạng thái.
    *   **Async-Mapping:** Chuyển `await/yield` thành các nút trạng thái trong CFG (Async-Aware CFG).

2.  **Bước 2: Speculative Graph Expansion & Implicit Modeling**
    *   **Dynamic Resolution:** Dùng SSA đoán hàm mục tiêu của `getattr`.
    *   **Implicit Signals:** Tạo cạnh ảo (Synthetic Edges) nối Sender -> Receiver cho Pub/Sub (Django Signals).
    *   **Decorator Unrolling:** Bóc lớp vỏ Decorator để lộ logic cốt lõi.

3.  **Bước 3: Deterministic Summarization & Masking**
    *   **Hierarchical Summarization:** Tóm tắt hàm lá thành Signature ngắn gọn.
    *   **Privacy Masking:** Mã hóa tên biến/hàm nhạy cảm trước khi gửi Cloud AI.
    *   **Prompt Injection Defense:** Loại bỏ comment rác.

## 3. Chiến Lược Lưu Trữ & Truy Xuất (Persistence & Retrieval)
Để tối ưu hiệu năng và hỗ trợ Incremental Analysis:

*   **Graph Persistence:** Lưu trữ đồ thị CPG/SSA đã phân tích xuống Disk Cache hoặc Graph DB (Neo4j) để tái sử dụng, tránh phân tích lại từ đầu.
*   **Strict Caching:** Hash(Input Signature) -> Result. Cố định `temperature=0` để đảm bảo tính nhất quán (Determinism). Nếu Input không đổi, tuyệt đối không gọi lại AI.
*   **Diff-based Lookup:** Chỉ tải lại các file thay đổi và truy ngược (Reverse Dependency) các module bị ảnh hưởng.

## 4. Quản lý Phản hồi (Feedback Loop)
*   **Interactive Triage:** Khi chuyên gia đánh dấu False Positive, hệ thống trích xuất **Signature** của trường hợp đó lưu vào Local Knowledge Base.
*   **Baseline Management:** Ghi nhận lỗi hiện tại là "Nợ cũ", chỉ báo cáo lỗi MỚI trong Pull Request để tránh Alert Fatigue.
