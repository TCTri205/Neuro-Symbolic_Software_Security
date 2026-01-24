# 05. Kiến Trúc Low-Resource Edition (Client-Server Hybrid)

**Phiên bản:** 1.0 (Adapted for Student/Low-End Hardware)
**Mục tiêu:** Triển khai sức mạnh của Neuro-Symbolic Security với **Chi phí 0đ** và **Phần cứng giới hạn** (CPU Only).

---

## 1. Triết Lý Thiết Kế: "Engineering on Edge, AI on Cloud"

Thay vì cố gắng chạy tất cả trên một máy (gây quá tải), chúng ta chia hệ thống thành hai phần riêng biệt, kết nối qua đường hầm bảo mật (Secure Tunnel).

*   **Engineering First (Tại Laptop):** Các thuật toán Logic (SSA, CFG, Parsing) chạy rất nhanh trên CPU. Chúng ta tận dụng Laptop để xử lý sơ bộ, lọc nhiễu và nén dữ liệu.
*   **AI Second (Tại Colab):** Các tác vụ suy luận ngữ nghĩa (Semantic Verification) cần GPU. Chúng ta "mượn" GPU T4 miễn phí của Google Colab để chạy Model **Qwen2.5** hoặc **DeepSeek-Coder**.

> **Tương tự thực tế:** Laptop đóng vai trò là "Thiết bị biên" (Edge Device) thu thập dữ liệu, còn Colab là "Trung tâm dữ liệu" (Cloud) xử lý trí tuệ nhân tạo.

---

## 2. Sơ Đồ Kiến Trúc (The Hybrid Flow)

```mermaid
graph LR
    subgraph Laptop [Laptop - The Engineer]
        Code[Source Code] --> Parser[AST Parser & SSA]
        Parser --> Graph[Graph Builder]
        Graph --> Semgrep[Semgrep CLI (Rule Filter)]
        Semgrep --> Filter{High Risk?}
        Filter -- No --> Report[Local Report]
        Filter -- Yes --> Signature[Semantic Signature Extractor]
        Signature --> Masking[Privacy Masking]
        Masking --> Client[API Client]
    end

    subgraph Tunnel [Internet Connection]
        Client -- JSON Request --> Ngrok[Ngrok Tunnel]
    end

    subgraph Colab [Google Colab - The AI Brain]
        Ngrok --> API[FastAPI Server]
        API --> Model[Qwen2.5/DeepSeek GGUF]
        Model -- Analysis --> API
    end

    API -- JSON Response --> Client
    Client --> FinalReport[Hybrid Report]
```

---

## 3. Ngăn Xếp Công Nghệ (Tech Stack) - Tối Ưu Hóa

Chúng ta thay thế các component nặng nề của V2.3 bằng các lựa chọn nhẹ nhàng hơn nhưng vẫn hiệu quả.

| Thành phần | V2.3 Gốc (Enterprise) | Low-Resource Edition (Student) | Lý do thay thế |
| :--- | :--- | :--- | :--- |
| **AI Model** | **Qwen2.5-Coder-7B (Canonical)** | **DeepSeek-Coder-6.7B-Instruct (GGUF)** | Chạy miễn phí trên Colab T4 GPU. GGUF là định dạng nén giúp load model nhanh. |
| **Graph DB** | Neo4j (Nặng RAM) | **NetworkX (In-Memory)** | Thư viện Python thuần, đủ sức xử lý đồ thị vài nghìn nút trên RAM laptop. |
| **Container** | Docker (Nặng máy ảo) | **Python venv** | Chạy trực tiếp trên môi trường máy thật (Native), tiết kiệm tài nguyên. |
| **Giao tiếp** | Internal Network | **PyNgrok / Cloudflared** | Tạo đường hầm (Tunnel) public port từ Colab ra Internet để Laptop kết nối. |
| **Server AI** | Self-hosted GPU Server | **Google Colab Notebook** | Tận dụng hạ tầng miễn phí của Google làm Server tạm thời. |

---

## 4. Ma Trận Đánh Đổi (Trade-off Matrix)

Để đạt được chi phí 0đ, chúng ta chấp nhận đánh đổi một số yếu tố, nhưng **không hy sinh chất lượng phát hiện lỗi cốt lõi**.

| Tiêu chí | V2.3 Gốc | Low-Resource | Phân tích |
| :--- | :--- | :--- | :--- |
| **Chi phí** | $$$ (API, Server) | **$0** | **Ưu điểm lớn nhất.** |
| **Độ trễ (Latency)** | Thấp (<1s) | Trung bình (2-5s) | Do phụ thuộc đường truyền mạng tới Colab. |
| **Privacy** | Cao (Enterprise) | Thấp hơn | Code đi qua Ngrok. Tuy nhiên, áp dụng **Privacy Masking** (Obfuscation) giúp giảm thiểu rủi ro. |
| **Độ ổn định** | 24/7 | Gián đoạn | Colab tự ngắt sau 12h. Cần chạy lại Notebook trước mỗi phiên làm việc. |
| **Quy mô** | Monorepo khổng lồ | Project vừa/nhỏ | Phù hợp với phạm vi đồ án tốt nghiệp và nghiên cứu. |

---

## 5. Chiến Lược "Signature Compression" & Privacy

Để khắc phục mạng yếu và rủi ro gửi code qua internet:

1.  **Semantic Extraction:** Thay vì gửi code thô, trích xuất đặc tả (Signature) gồm Input, Sink, và Luồng dữ liệu (Data Flow Path).
2.  **Typed Privacy Masking:** Mã hóa tên hàm/biến theo kiểu dữ liệu (VD: `process_payment` -> `PAYMENT_FUNC_1`, `user_id` -> `USER_INT_1`) trước khi gửi JSON. Điều này giúp AI giữ được ngữ nghĩa để suy luận chính xác hơn so với mã hóa ngẫu nhiên.
3.  **Strict Caching:** Tính Hash của Signature. Nếu hash đã tồn tại trong Cache cục bộ trên Laptop, lấy kết quả ngay lập tức không cần gửi lên Colab.

-> Gói tin JSON gửi đi cực nhẹ (< 2KB) và an toàn hơn.

---

## 6. Hướng Dẫn Triển Khai
Xem chi tiết giao thức tại [docs/05a_Client_Server_Protocol.md](./05a_Client_Server_Protocol.md) và hướng dẫn chạy demo tại [docs/05b_Demo_Walkthrough.md](./05b_Demo_Walkthrough.md).
