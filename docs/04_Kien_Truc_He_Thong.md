# 04. Kiến Trúc Hệ Thống Kỹ Thuật (Technical Architecture V2.3)

Kiến trúc V2.3 chuyển dịch sang mô hình **Defense-in-Depth**, kết hợp phân tích tĩnh chuyên sâu (SSA) và kiểm chứng ngữ nghĩa (LLM).

## 1. Tech Stack (Ngăn Xếp Công Nghệ)

| Thành phần | Công cụ | Vai trò |
| :--- | :--- | :--- |
| **Code Parser & SSA** | Custom Builder (Python AST) | Xây dựng đồ thị SSA và CFG hỗ trợ Async (Async-Aware CFG). |
| **Context Inference** | Custom Script | Quét `settings.py`, `.env`, `requirements.txt`, `Dockerfile`, `pyproject.toml`. |
| **Framework Plugins** | Plugin System | Logic chuyên biệt cho Django, FastAPI, Flask (Routing, Injection). |
| **Rule Engine** | **Semgrep** | Quét nhanh các mẫu (Patterns) và lọc sơ bộ. |
| **Graph Intelligence** | **GNN** | Risk Ranker (Xếp hạng rủi ro) trên đồ thị CPG. |
| **Semantic Verifier** | **Qwen2.5-Coder-7B (Canonical)** | Kiểm chứng lỗi qua Semantic Signatures. |
| **Secret Scanner** | Regex & Entropy Analysis | Chạy song song ở Stage 1 để bắt Credential leakage. |
| **Knowledge Base** | Neo4j / Disk Cache | Lưu trữ CPG/SSA, Librarian Profiles và Cache kết quả. |

## 2. Luồng Xử Lý 4 Giai Đoạn (The Pipeline)

### Stage 1: Deep Code Understanding (SSA & Context)
*   **SSA Building:** Biến code động thành tĩnh, tách các phiên bản biến (`a_1`, `a_2`).
*   **Async-Aware CFG:** Mô hình hóa các điểm `await` như nút chuyển trạng thái.
*   **Speculative Expansion:** Nối cạnh ảo dựa trên phân tích kế thừa, giới hạn phạm vi (Scoped Expansion).
*   **Inference Config:** Nạp biến môi trường và IaC (Dockerfile/Helm) vào context.
*   **Decorator Unrolling:** Bóc lớp vỏ Decorator để lộ logic thực.

### Stage 2: The Librarian (Third-party Knowledge)
*   Tra cứu profile thư viện (Source/Sink/Sanitizer).
*   **Version Check:** Đối chiếu phiên bản chính xác (`Flask==2.0.1`).
*   **AI Fallback:** LLM tạo Shadow Profile nếu thiếu thông tin DB.
*   **OpenAPI Integration:** Đọc OpenAPI specs để hiểu kiểu dữ liệu Microservices.

### Stage 3: Tiered Analysis (Filtering & Routing)
*   **Lớp 1 (Ranker):** Semgrep + GNN chấm điểm rủi ro.
*   **Lớp 2 (Routing):** Chuyển tiếp High Risk/Complex Logic sang Stage 4.
*   **Sink-Driven Focus:** Áp dụng Backwards Slicing từ Sink lên Source để tối ưu.

### Stage 4: Semantic Verification (LLM)
*   **RAG-based Slicing:** Chỉ gửi bản tóm tắt hành vi (Semantic Signatures) của hàm con.
*   **Deterministic Prompting:** Hỏi LLM về tính chất Data Flow (Deterministic) thay vì Simulation.
*   **Verification Call:** Xác nhận tính khả thi dựa trên Input -> Output contracts.
*   **Privacy Masking:** Mã hóa tên biến nhạy cảm trước khi gửi API.

## 3. Chế độ Vận hành (Operational Modes)
1.  **CI/CD Mode (Fast):** Chỉ chạy Stage 1 & 3 (Rule-based). Ưu tiên tốc độ, chặn lỗi cơ bản.
2.  **Audit Mode (Deep):** Chạy toàn bộ 4 Stage + Speculative Expansion tối đa.
3.  **Baseline Mode:** Chỉ báo cáo lỗi mới (Diff-only Reporting), quản lý nợ kỹ thuật.
4.  **Student Hybrid Mode (New):** Chạy Engineering trên Laptop và AI Inference trên Google Colab (Chi tiết xem `docs/05_Low_Resource_Architecture.md`).

## 4. Đặc tính Hệ thống
*   **Deterministic:** `temperature=0`, `seed` cố định và Hash-based Caching.
*   **Plugin Architecture:** Chuyển logic framework (Django/FastAPI) ra plugin độc lập để dễ bảo trì.
*   **Incremental & Persistent:** Diff-based scanning kết hợp Persistent Caching (CPG/SSA trên đĩa).
*   **Centralized AI Server:** Triển khai Server GPU nội bộ phục vụ chung cho team.
*   **Safe Auto-Fix:** Đề xuất vá lỗi với cơ chế **Constraint Checking** (tuân thủ cú pháp/logic) để đảm bảo an toàn.
*   **Visual Tracing:** Xuất kết quả dưới dạng đồ thị luồng dữ liệu (Graph Visualization) thay vì chỉ text.
