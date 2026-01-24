# 02. Bản Đồ Lỗ Hổng Python (Vulnerability Landscape)

Tài liệu này định nghĩa các "Mục tiêu Tấn công" (Target Class) của hệ thống V2.3. Chúng ta tập trung vào các lỗi đặc thù của Python và sự đứt gãy luồng dữ liệu do tính động của ngôn ngữ.

## Nhóm 1: Critical Taint Vulnerabilities (Source-Sink)
Hệ thống sử dụng **SSA-Enhanced Taint Analysis** để truy vết từ Source đến Sink, vượt qua các thách thức về Dynamic Dispatch và Monkey Patching.

| CWE | Tên Lỗ Hổng | Mức độ | Source (Nguồn) | Sink (Điểm đến) | Ghi chú V2.3 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CWE-502** | **Insecure Deserialization** | 🔴 Critical | File, Network, DB | `pickle.load()`, `yaml.load()`, `torch.load()` | Đặc thù AI Apps. Coi File Object là nguồn Taint nguy hiểm. |
| **CWE-78** | **OS Command Injection** | 🔴 Critical | API Input, `sys.argv` | `os.system()`, `subprocess.run(shell=True)` | Phát hiện ngay cả khi hàm bị alias hoặc import động. |
| **CWE-94** | **Code Injection** | 🔴 Critical | User Input, Config | `eval()`, `exec()`, `compile()` | Sử dụng Speculative Expansion để đoán nội dung chuỗi động. |
| **CWE-1336** | **Template Injection (SSTI)** | 🟠 High | Web Form, URL | `jinja2.Template.render()` | Parser chuyên biệt cho Jinja2/Django Template để nối luồng sang HTML. |
| **CWE-89** | **SQL Injection** | 🟠 High | Web/API Input | `cursor.execute()`, ORM Raw SQL | Phân biệt rõ `Parameterize` (An toàn) và `String Concat` (Lỗi). |

### 1.1. Context-Aware Sanitizer Tags
Hệ thống không chỉ kiểm tra có/không Sanitizer, mà còn kiểm tra **loại** Sanitizer có khớp với Sink không:
*   **Sanitizer_SQLi:** Chỉ vô hiệu hóa Taint đối với SQL Sink (ví dụ: ORM binding).
*   **Sanitizer_XSS:** Chỉ vô hiệu hóa Taint đối với HTML/SSTI Sink (ví dụ: `html.escape`).
*   *Quy tắc chặt chẽ:* `html.escape` (Sanitizer_XSS) sẽ **không** được coi là an toàn cho SQL Sink.

## Nhóm 2: Logic & Configuration Flaws
Sử dụng **Config Inference** và **IaC Scanning** để phát hiện lỗi từ code đến hạ tầng.

*   **Path Traversal (CWE-22):** Truy cập file ngoài qua `../`. Sink: `open()`, `send_file()`.
*   **Insecure Configuration:**
    *   `DEBUG=True` trong Production (quét cả `settings.py` và biến môi trường Docker/K8s).
    *   `SECRET_KEY` yếu hoặc hardcoded.
    *   Thiếu `CSRF`, `CORS` quá rộng.
*   **Secret Leakage:** Module **Secret Scanner** chạy song song phát hiện API Key, Token, Password cứng trong code.

## Nhóm 3: Implicit & Advanced Flows (Điểm mù truyền thống)
V2.3 xử lý các luồng dữ liệu ẩn mà SAST cũ thường bỏ sót:

*   **Async/Concurrency:** Theo dõi dữ liệu qua `await`, `asyncio.gather` bằng Async-Aware CFG.
*   **Implicit Signals:** Lập bản đồ Pub/Sub (Django Signals, Blinker) để tạo các cạnh ảo (Synthetic Edges) nối Sender -> Receiver.
*   **Decorator Unrolling:** "Bóc" lớp vỏ `@app.route`, `@auth` để nhìn thấy logic thực sự bên trong.
*   **Distributed Taint (Heuristic):** Tự động nối luồng qua Message Queue (Kafka/RabbitMQ) nếu trùng Topic Name.

## Nhóm 4: Supply Chain & Malware
Sử dụng **Librarian** với khả năng Version-Aware:

*   **Malicious Packages:** Phát hiện Typosquatting, Exfiltration code trong `setup.py`.
*   **C-Extension Blind Spots:** Cảnh báo các thư viện Binary/C-Extension không thể phân tích tĩnh, đề xuất Manual Modeling.
*   **Modern Dependency:** Hỗ trợ quét `pyproject.toml`, `poetry.lock` bên cạnh `requirements.txt`.

## Nhóm 5: Giới Hạn (Out of Scope)
*   **Business Logic Flaws (IDOR):** Chỉ hỗ trợ qua **Policy Check** (người dùng tự định nghĩa rule).
*   **Obfuscated/Binary Code:** Tự động bỏ qua và cảnh báo (`.so`, `.pyd`, code bị làm rối).
