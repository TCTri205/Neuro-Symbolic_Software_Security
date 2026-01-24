# 01. Tổng Quan Dự Án: Neuro-Symbolic Software Security (Python Edition)

## 1. Tầm Nhìn & Sự Chuyển Dịch
Dự án đánh dấu bước chuyển mình chiến lược từ C/C++ sang **Python** - ngôn ngữ phổ biến nhất trong AI và Backend hiện đại. Sự thay đổi này định nghĩa lại hoàn toàn bài toán bảo mật:
*   **Từ:** Memory Safety (Buffer Overflow, Segfault).
*   **Sang:** **Logic Flaws & Taint Analysis** (Injection, Deserialization, Supply Chain).

Mục tiêu tối thượng: Xây dựng một hệ thống **Automated Security Auditor** theo triết lý **"Engineering First, AI Second"**. Sử dụng kỹ thuật phần mềm cổ điển (SSA, CFG) làm nền tảng vững chắc và AI để giải quyết các bài toán ngữ nghĩa phức tạp.

## 2. Các Thay Đổi Cốt Lõi V2.3
Hệ thống chuyển dịch sang mô hình cộng sinh (Symbiotic):
*   **Inference Config:** Chủ động đọc môi trường (`settings.py`, `requirements.txt`, `Dockerfile`, `pyproject.toml`) thay vì giả lập không cấu hình.
*   **Risk Ranker:** GNN không còn quyền vứt bỏ code, chỉ xếp hạng ưu tiên xử lý để tránh sót lỗi (False Negative).
*   **Version-Aware Librarian:** Quản lý tri thức thư viện theo từng phiên bản cụ thể (Version pinning).
*   **SSA & Speculative Expansion:** Giải quyết bài toán code động và Dynamic Dispatch bằng kỹ thuật "tĩnh hóa".
*   **Plugin Architecture:** Tách biệt logic xử lý Framework (Django, FastAPI) thành các plugin độc lập để dễ dàng mở rộng và bảo trì.
*   **Operational Modes:** Hỗ trợ đa chế độ vận hành: CI/CD (Fast), Audit (Deep) và **Student Hybrid (Low-Resource)**.
*   **Privacy & Compliance:** Hỗ trợ Local LLM và Privacy Masking cho khách hàng Enterprise.

## 3. Quy Trình Xử Lý (Pipeline Overview)
Hệ thống vận hành qua 4 giai đoạn hình phễu: **Thu thập rộng -> Phân tích sâu -> Kiểm chứng kỹ**.

1.  **Stage 1: Deep Code Understanding:** Tĩnh hóa code động bằng SSA và Speculative Expansion. Xử lý môi trường và cấu hình (IaC).
2.  **Stage 2: The Librarian:** Đối chiếu tri thức thư viện và phiên bản (Version-Aware) để hiểu hành vi của bên thứ 3.
3.  **Stage 3: Tiered Analysis:** Phân tầng xử lý:
    *   **Lớp 1 (Ranker):** GNN + Rules (Semgrep) chạy trên đồ thị CPG để chấm điểm rủi ro.
    *   **Lớp 2 (Routing):** Định tuyến dựa trên rủi ro (Low Risk -> Rule/Small LLM, High Risk -> Qwen2.5-Coder-7B).
4.  **Stage 4: Semantic Verification:** Dùng LLM kiểm chứng ngữ nghĩa các điểm rủi ro cao (High Risk), loại bỏ báo ảo bằng RAG-based Slicing và Semantic Prompting.

## 4. Giải Pháp Cho Các "Điểm Mù" Kỹ Thuật (The Hard Problems)
Khác với C/C++, tính năng động của Python và sự phụ thuộc vào Framework là rào cản lớn nhất. V2.3 giải quyết triệt để thông qua các kỹ thuật:

| Vấn đề (The Hard Problem) | Giải pháp V2.3 (The Fix) |
| :--- | :--- |
| **Biến đổi kiểu (`a='b'` -> `a=3`)** | **SSA (Static Single Assignment):** Tách biến thành các phiên bản `a_1`, `a_2` để biết chính xác type tại mỗi điểm. |
| **Hàm động (`getattr`, `eval`)** | **Speculative Expansion:** Kết hợp SSA để đoán tên hàm. Nếu không đoán được, nối edge tới tất cả hàm candidate (chấp nhận nhiễu để an toàn). |
| **Token Cost quá cao** | **Hierarchical Summarization:** Tóm tắt các hàm lá (leaf nodes) thành text ngắn gọn thay vì gửi raw code. |
| **False Negatives (Sót lỗi)** | **Tiered Defense:** Không vứt bỏ code ở các bước đầu, chỉ xếp hạng thấp hơn. Vẫn quét bằng Rule engine ở tầng thấp. |
| **Framework "Magic"** | **Framework Awareness Plugins:** Module chuyên biệt hiểu cơ chế routing/injection của Django, FastAPI, Flask. |
| **Async/Concurrency** | **Async-Aware CFG:** Theo dõi luồng dữ liệu qua `await`, `asyncio.gather`. |

## 5. Nguyên Lý Neuro-Symbolic V2.3 (Symbiotic)
Hệ thống hoạt động theo mô hình cộng sinh, tận dụng sức mạnh của cả hai thế giới:
1.  **Symbolic (Nền tảng - Engineering First):**
    *   Xây dựng đồ thị CPG dựa trên SSA, theo dõi chính xác trạng thái biến.
    *   **Speculative Expansion** để xử lý tính động.
    *   **Determinism:** Caching chặt chẽ và hash input signature để đảm bảo tính nhất quán.
2.  **Neural (Tăng cường - AI Second):**
    *   **Risk Ranker (GNN):** Xếp hạng mức độ rủi ro để ưu tiên xử lý.
    *   **Semantic Verifier (LLM):** Kiểm chứng các điểm nghi ngờ.
    *   **Semantic Signature Extraction:** Trích xuất đặc tả kỹ thuật (Input -> Output, Side-Effects, Taint-Propagation) thay vì tóm tắt văn xuôi, giảm thiểu ảo giác (Hallucination).

## 6. Lộ Trình Triển Khai (Roadmap)
*   **Giai đoạn 1: Foundation & Optimization (Quý 1)**
    *   Xây dựng Parser & SSA Builder hỗ trợ `pyproject.toml`.
    *   Tích hợp Secret Scanner, Context-Aware Sanitizers.
    *   Thiết kế Graph Persistence, Diff-based Scanning và Baseline Mode.
*   **Giai đoạn 2: Hybrid Intelligence (Quý 2)**
    *   Tích hợp Rule Engine (Semgrep) và Async-Aware CFG.
    *   Phát triển Speculative Expansion, Type Hint Awareness và **Deterministic LLM Gateway**.
    *   Plugin Architecture cho Frameworks.
*   **Giai đoạn 3: The Verifier & Ecosystem (Quý 3)**
    *   Tích hợp LLM với Semantic Signature Extraction và **Privacy Masking**.
    *   Triển khai **Centralized AI Server** và cơ chế Safe Auto-Fix.
    *   Hoàn thiện Visual Tracing và Heuristic Linking (MQ).

## 7. Biến Thể Triển Khai
*   **Enterprise Edition:** Full features, On-premise/Cloud, Privacy Masking, Centralized AI Server.
*   **Low-Resource Edition (Student/Research):** Client-Server Hybrid (Laptop chạy Engineering <-> Colab chạy AI), tối ưu chi phí 0đ.
