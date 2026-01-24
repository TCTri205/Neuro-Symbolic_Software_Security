# 06. Chiến Lược Model & Fine-tuning (Hybrid Neuro-Symbolic Architecture)

Tài liệu này xác định lộ trình tuyển chọn, tinh chỉnh (fine-tune) và vận hành mô hình ngôn ngữ lớn (LLM) cho module **Semantic Verifier** chạy trên **Google Colab Server**, phù hợp với kiến trúc Client-Server đã định nghĩa tại `docs/05a_Client_Server_Protocol.md`.

**Mục tiêu nghiên cứu cốt lõi:**
Chứng minh hiệu quả của mô hình **Neuro-Symbolic**: Kết hợp độ phủ rộng của Static Analysis (Client) với khả năng suy luận sâu của Fine-tuned LLM (Server) để giảm thiểu **False Positives** mà không cần hạ tầng phần cứng đắt tiền.

---

## 1. Nghiên Cứu Hiện Trạng & So Sánh (State of the Art)

Để đảm bảo tính khoa học và mới mẻ của đề tài, giải pháp được đặt trong bối cảnh so sánh với các kỹ thuật tiên tiến nhất (2023-2024).

### 1.1. Bảng So Sánh Kỹ Thuật

| Phương pháp | Công cụ đại diện | Cơ chế hoạt động | Điểm yếu (Pain Points) mà dự án giải quyết |
| :--- | :--- | :--- | :--- |
| **Traditional SAST** | CodeQL, Semgrep | Pattern Matching & Taint Analysis | **Báo ảo quá nhiều (>50%):** Không hiểu ngữ cảnh logic (ví dụ: biến đã được validate nhưng tool không nhận ra). |
| **Vanilla LLMs** | GPT-4, Claude 3.5 | Zero-shot Prompting | **Chi phí & Riêng tư:** Gửi toàn bộ code lên API tốn kém và rủi ro lộ mã nguồn. Thường bị "Hallucination" (bịa lỗi). |
| **GNN-based** | Devign, VulDeePecker | Graph Neural Networks | **Hộp đen (Blackbox):** Chỉ đưa ra xác suất lỗi mà không giải thích được lý do (No Explainability) và không gợi ý sửa lỗi (No Auto-fix). |
| **Hybrid Neuro-Symbolic** | **Dự án này** | **Client (SSA) + Server (LLM)** | **Tối ưu toàn diện:** Client lọc thô (nhẹ), Server dùng LLM đã fine-tune để "đọc hiểu" ngữ nghĩa và xác minh lỗi. |

### 1.2. Dẫn chứng khoa học
*   *arXiv:2311.16169:* LLM chưa qua fine-tune chỉ đạt độ chính xác ~62.8% trong việc phát hiện lỗ hổng.
*   *Hướng tiếp cận của dự án:* Thay vì bắt LLM quét toàn bộ dự án (tốn kém, kém hiệu quả), ta dùng SAST để "chỉ điểm" nghi vấn, và dùng LLM đóng vai trò "Senior Security Engineer" để review lại điểm đó.

---

## 2. Lựa Chọn Model (Model Selection)

Dựa trên ràng buộc về tài nguyên (Google Colab Free/Pro - GPU T4 16GB hoặc A100 40GB) và yêu cầu bảo mật.

### 2.1. Tiêu chí
1.  **Instruction Following:** Phải tuân thủ tuyệt đối cấu trúc JSON Output (để Client parse được).
2.  **Coding Capability:** Hiểu sâu về Python và các thư viện bảo mật.
3.  **Size:** Tối ưu cho inference trên 1 GPU đơn lẻ.

### 2.2. Ứng Viên & Quyết Định (Benchmark 2024-2025)

| Model | Size | Context | Đánh giá | Quyết định |
| :--- | :--- | :--- | :--- | :--- |
| **Qwen2.5-Coder-7B-Instruct** | 7.6B | 128K | **Hiệu năng/Kích thước vô đối.** SOTA phân khúc 7B. Load 4-bit chỉ tốn ~5.5GB VRAM (Dư nhiều cho Context dài). JSON cực chuẩn. | **Ưu tiên số 1** (Best Choice). |
| **DeepSeek-Coder-V2-Lite** | 16B (MoE) | 164K | **Mạnh nhưng rủi ro.** Kiến trúc MoE load full weights tốn ~9-10GB VRAM, dư rất ít cho training trên Colab T4. | Dự phòng. |
| **DeepSeek-Coder-6.7B-Instruct (v1)** | 6.7B | 32K | Ổn định nhưng hiệu năng đã bị Qwen2.5 vượt qua. | Dự phòng. |

**Kết luận:** Chuyển đổi sang **Qwen2.5-Coder-7B-Instruct**.
**Lý do cốt lõi:**
1.  **Hiệu năng SOTA:** Vượt trội DeepSeek v1 và tiệm cận GPT-4 ở các bài toán coding (HumanEval, MBPP).
2.  **Tối ưu VRAM:** Kiến trúc Dense 7B load 4-bit rất nhẹ (~5-6GB), để lại khoảng 10GB VRAM trống trên Colab T4. Điều này cho phép tăng **Context Length lên 4096-8192 tokens** (quan trọng để chứa code trace dài) và tăng Batch Size.
3.  **Instruction Following:** Tuân thủ System Prompt tốt hơn, giảm thiểu lỗi format JSON đầu ra.

---

## 3. Chiến Lược Fine-tuning (The "Security Auditor" Persona)

Chúng ta sử dụng kỹ thuật **QLoRA (Quantized Low-Rank Adaptation)** để fine-tune model.

### 3.1. Input/Output Definition (Đồng bộ với Protocol 05a)

Để đảm bảo tính nhất quán giữa Training và Inference (tránh việc Server phải map dữ liệu phức tạp), Schema của dữ liệu huấn luyện phải khớp chính xác với cấu trúc JSON định nghĩa trong `docs/05a_Client_Server_Protocol.md`.

**Training Prompt Logic (Alpaca/ChatML format):**
*   **Instruction:** System prompt định nghĩa vai trò Security Auditor. *Bổ sung constraint: "Do not output markdown code blocks. Start response with '{'"*.
*   **Input:** JSON chứa `function_signature` và `context` (đặc biệt là danh sách `sanitizers_found` từ Client).
*   **Output:** JSON chứa kết quả phân tích chuẩn.

**Target Output Schema (Khớp Protocol 05a):**
```json
{
  "is_vulnerable": true,
  "confidence_score": 0.95,
  "risk_level": "HIGH", 
  "analysis_summary": "Explain clearly why this is a vulnerability. If 'sanitizers_found' contains valid cleaning functions, explain why is_vulnerable is false.",
  "fix_suggestion": "Brief recommendation (e.g., Use parameterized queries).",
  "secure_code_snippet": "Provide the secure version of the code snippet (or null if safe).",
  "constraint_check": {
      "syntax_valid": true,
      "logic_sound": true
  }
}
```

### 3.2. Dataset Strategy (Chiến lược Data Factory)

Chúng ta không dùng dataset thô mà xây dựng một quy trình "Data Factory" để tạo ra dataset chất lượng cao (~2,000 - 5,000 mẫu) tập trung vào "Tư duy bảo mật" (Security Reasoning).

**Nguồn dữ liệu:** **CVEFixes** (Phiên bản lọc Python).

**Quy trình xử lý (Preprocessing Pipeline):**

1.  **Lọc dữ liệu (Filter):** Chỉ lấy Python, loại bỏ mẫu quá dài.
2.  **Tạo mẫu Negative (Hard Negatives):** Code đã fix -> `is_vulnerable: false`.
3.  **Neuro-Symbolic Augmentation (Tối ưu hóa cốt lõi):**
    *   **Simulate Context:** Giả lập field `context: { "sanitizers_found": [...] }`.
    *   **Typed Privacy Masking (Cải tiến):** Thay vì mã hóa vô nghĩa (`var_1`), ta sử dụng **Mặt nạ định danh kiểu (Typed Placeholders)**. Ví dụ: `user_input` -> `USER_STR_1`, `db_connection` -> `DB_OBJ_1`. Điều này giữ lại "manh mối logic" cho LLM mà vẫn bảo mật tên biến thật.
    *   **Slicing Alignment:** Dữ liệu training phải được đi qua bộ lọc **Dependency Slicing** (giống như Client Stage 4) để model học cách xử lý "Code vụn" thay vì code nguyên bản.
    *   **Mục đích:** Giúp model hiểu vai trò của biến (Semantic Role) trong luồng dữ liệu mà không cần biết định danh thực tế.

4.  **Sinh Reasoning bằng Teacher Model (Synthetic Chain-of-Thought):**
    *   Dùng **Gemini 1.5 Pro / GPT-4o** để sinh ra quy trình suy luận từng bước (`reasoning_steps`) TRƯỚC KHI đưa ra kết quả JSON. Quy trình này sẽ được dùng để fine-tune khả năng "tư duy" của model 7B.

**Cấu trúc mẫu Training (Final Dataset Schema):**
```json
[
  {
    "instruction": "Analyze the following Python code trace for SQL Injection vulnerabilities. Return logic in JSON.",
    "input": "{\n  \"function_signature\": \"def get_user(uid):\\n  sql = 'SELECT * FROM users WHERE id = %s' % uid\\n  cursor.execute(sql)\",\n  \"vulnerability_type\": \"SQL Injection\",\n  \"context\": {\n    \"sanitizers_found\": []\n  }\n}",
    "output": "{\n  \"is_vulnerable\": true,\n  \"confidence_score\": 0.98,\n  \"risk_level\": \"CRITICAL\",\n  \"analysis_summary\": \"The code uses Python string formatting (%) to construct the SQL query...\",\n  \"fix_suggestion\": \"Use parameterized queries.\",\n  \"secure_code_snippet\": \"sql = 'SELECT * FROM users WHERE id = %s'\\ncursor.execute(sql, (uid,))\",\n  \"constraint_check\": {\"syntax_valid\": true, \"logic_sound\": true}\n}"
  },
  {
    "instruction": "Analyze the following Python code trace for SQL Injection vulnerabilities. Return logic in JSON.",
    "input": "{\n  \"function_signature\": \"def get_user(uid):\\n  safe_uid = escape(uid)\\n  sql = f'SELECT... {safe_uid}'\",\n  \"vulnerability_type\": \"SQL Injection\",\n  \"context\": {\n    \"sanitizers_found\": [\"escape\"]\n  }\n}",
    "output": "{\n  \"is_vulnerable\": false,\n  \"confidence_score\": 0.92,\n  \"risk_level\": \"SAFE\",\n  \"analysis_summary\": \"Although f-string is used, the input variable 'uid' is passed through 'escape' function (detected in sanitizers_found), which neutralizes the injection vector.\",\n  \"fix_suggestion\": null,\n  \"secure_code_snippet\": null,\n  \"constraint_check\": {\"syntax_valid\": true, \"logic_sound\": true}\n}"
  }
]
```

### 3.3. Training Pipeline trên Colab

1.  **Environment:** Google Colab (T4 GPU - 16GB VRAM).
2.  **Library:** `unsloth` (Hỗ trợ Qwen2.5, tăng tốc 2x, giảm VRAM).
3.  **Cấu hình Fine-tuning (QLoRA):**
    *   **Model:** `Qwen/Qwen2.5-Coder-7B-Instruct`
    *   **Quantization:** 4-bit (NF4).
    *   **LoRA Rank (r):** 16.
    *   **LoRA Alpha:** 32.
    *   **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` (Train toàn bộ các lớp linear để model thông minh nhất).
    *   **Max Seq Length:** 4096 hoặc 8192 (Tận dụng VRAM dư để xử lý context dài).
    *   **Batch Size:** Điều chỉnh tùy thực tế (tận dụng phần VRAM còn lại).

---

## 4. Tích Hợp Vào Quy Trình Vận Hành (Inference Workflow)

Sau khi fine-tune, model (Adapter) sẽ được load tại **Colab Server**. Quy trình cần xử lý các rủi ro về format output:

1.  **Client (Laptop):** Gửi Request JSON chứa `function_signature` và `context`.
2.  **Server (Colab):**
    *   Nhận JSON. Kiểm tra độ dài context.
    *   Convert thành Prompt theo template.
    *   **Inference:** Chạy model.
    *   **Constrained Decoding (Giải pháp triệt để):** Thay vì để model sinh text tự do rồi sửa lỗi JSON, Server sử dụng thư viện **Outlines** hoặc **Guidance** để ép model chỉ sinh ra các token khớp với JSON Schema. Điều này đảm bảo xác suất JSON valid là 100% mà không cần hậu xử lý.
    *   **Chain-of-Thought Prompting:** Cấu trúc Prompt yêu cầu model trình bày suy luận trong thẻ `<thinking>` trước khi mở ngoặc nhọn `{` của JSON. Kết quả trả về cho Client sẽ được trích xuất phần JSON sau khi model đã hoàn tất suy luận.
    *   Trả kết quả về Client.

---

## 5. Đánh Giá Hiệu Quả (Evaluation Metrics)

Để chứng minh luận điểm nghiên cứu, cần đo lường:

*   **False Positive Rate (FPR):** Mục tiêu giảm FPR từ 50% xuống < 10%.
*   **Blind Test Score:** Đánh giá trên bộ dữ liệu 100 mẫu tự biên soạn (không có trên GitHub/CVEFixes) để đo khả năng suy luận thực tế, tránh việc model "học vẹt" từ tập pre-train.
*   **Fix Rate:** Tỷ lệ code gợi ý (Auto-fix) chạy được và hết lỗi.
*   **Reliability:** Tỷ lệ thành công của Constrained Decoding (Mục tiêu 100% Valid JSON).

---

## 6. Quản Lý Rủi Ro & Ràng Buộc Kỹ Thuật (Blind Spots & Risk Management)

Để đảm bảo tính khả thi khi triển khai thực tế (đặc biệt trên môi trường giới hạn như Colab), các rủi ro sau cần được kiểm soát:

### 6.1. Context Window & Token Limit
*   **Vấn đề:** Input bao gồm `function_signature` + `context` + System Prompt + JSON Schema dễ vượt quá giới hạn tokens.
*   **Giải pháp:**
    *   **AST Pruning:** Client loại bỏ comment, docstring, và khoảng trắng thừa trước khi gửi.
    *   **Context Compression:** Thay thế các hàm trung gian không nhạy cảm bằng **Semantic Signatures** thay vì gửi toàn bộ Raw Code.
    *   **No-Skip Policy:** Ưu tiên tóm tắt (Summarization) hơn là bỏ qua (Skip) để đảm bảo độ phủ bảo mật.

### 6.2. Privacy vs Accuracy (Lưu ý đặc biệt)
*   **Vấn đề:** Model AI cần ngữ nghĩa để phân tích, nhưng Privacy Masking xóa bỏ thông tin này.
*   **Giải pháp:** Áp dụng **Typed-Masking Map**. Ví dụ: `process_payment(amount)` -> `SENSITIVE_FUNC_1(USER_INT_1)`. Client giữ bản đồ (map) để hoàn nguyên tên gốc sau khi nhận kết quả.

### 6.3. JSON Reliability (Output Format)
*   **Vấn đề:** Model 4-bit dễ sinh lỗi format.
*   **Giải pháp:** Sử dụng **Constrained Decoding (Logit Warping)** để ngăn chặn việc sinh token sai cấu trúc ngay từ tầng xác suất của model.

### 6.4. Hallucination (Bịa đặt thư viện)
*   **Vấn đề:** Model tự chế ra các hàm hoặc import thư viện không có trong dự án.
*   **Giải pháp:** Bổ sung ràng buộc vào Prompt: *"Do not import new libraries unless absolutely necessary. Use existing coding style."*

### 6.5. Hardware Constraints
*   **Vấn đề:** Training trên Colab T4 dễ bị OOM (Out of Memory).
*   **Giải pháp:** Giảm `batch_size` xuống 1, tăng `gradient_accumulation_steps` lên 4. Sử dụng `unsloth` để tối ưu memory.

---
*Tài liệu này là hướng dẫn kỹ thuật chi tiết để xây dựng "bộ não" AI cho hệ thống Neuro-Symbolic Security.*
