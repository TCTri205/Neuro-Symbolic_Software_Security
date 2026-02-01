# NSSS Next-Phase Roadmap (v2.3+)

## 1. Tầm nhìn & Nguyên tắc
Dự án hướng tới việc xây dựng một hệ thống an ninh phần mềm lai (Neuro-Symbolic) mạnh mẽ, tin cậy và dễ tiếp cận.

*   **Nguyên tắc cốt lõi:** Xem chi tiết tại [Manifesto](00_principles/manifesto.md).
*   **Chiến lược phần cứng:** Xem [ADR-001 (Hybrid Strategy)](02_decisions/adr-001-hybrid-strategy.md).

## 2. Lộ trình Phát triển (Roadmap)

### Giai đoạn 1: Hardened DevSecOps (0-1 tháng)
*   **Mục tiêu:** Tự động hóa hoàn toàn quy trình kiểm tra.
*   **Kế hoạch chi tiết:** Xem [DevSecOps Automation Plan](01_drafts/devsecops_automation_plan.md).
*   **Công cụ:** GitHub Actions, Pre-commit.

### Giai đoạn 2: AI Efficiency & Inference (1-3 tháng)
*   **Mục tiêu:** Tối ưu hóa lớp AI cho máy yếu và tăng độ chính xác.
*   **Kế hoạch chi tiết:** Xem [Hybrid AI Model Experiment](01_drafts/hybrid_ai_model_experiment.md).
*   **Công cụ:** Groq Cloud, Gemini Flash, llama.cpp.

### Giai đoạn 3: Fine-tuning & Data Loop (3-6 tháng)
*   **Mục tiêu:** Tự học từ False Positives/Negatives và chuẩn hóa dữ liệu.
*   **Kế hoạch chi tiết:** Xem [Fine-tuning Data Loop](01_drafts/fine_tuning_data_loop.md).
*   **Chiến lược dữ liệu:** Xem [Real-world Data Strategy](01_drafts/real_world_data_strategy.md).
*   **Công cụ:** Unsloth, Google Colab, Big-Vuln Dataset.

### Giai đoạn 4: Scientific Impact (6+ tháng)
*   **Mục tiêu:** Công bố bài báo khoa học và chuẩn hóa tài liệu.
*   **Kế hoạch chi tiết:** Xem [Scientific Impact Plan](01_drafts/scientific_impact_plan.md).
*   **Giao thức đánh giá:** Xem [Benchmarking Protocol](01_drafts/benchmarking_protocol.md).
*   **Công cụ:** Typst, Zotero, ArXiv.

## 3. Phụ lục & Hỗ trợ kỹ thuật
*   [Hướng dẫn chọn SLM theo RAM](NSSS_NEXT_PHASES.md#13-huong-dan-chon-slm-theo-ram) (Xem bên dưới)
*   [Checklist setup 1 ngày](NSSS_NEXT_PHASES.md#11-checklist-setup-trong-1-ngay-laptop-yeu)

---

### [Phần cũ giữ lại để tra cứu nhanh]
*(Các mục 11, 12, 13 được giữ lại ở đây để tiện tra cứu nhanh)*

## 11. Checklist setup trong 1 ngay (laptop yeu)
- Cai pre-commit va bat 2-3 hook nhe (lint nhanh, check format)
- Tao GitHub Actions workflow lite cho scan chinh
- Kiem tra NSSS chay duoc tren 1 repo mau (1-2 file Python)
- Bat SARIF upload de tong hop ket qua
- Ghi lai FP/FN vao file quy uoc de dung cho data loop

## 12. Mau workflow GitHub Actions nhe nhat
- File: `.github/workflows/nsss-scan-lite.yml`
- Noi dung: setup Python, cai deps, make scan-fast, upload SARIF

## 13. Huong dan chon SLM theo RAM
### RAM 8GB
- Uu tien model 3B-4B, quant 4-bit (GGUF): phi-3-mini, qwen2.5-3b, llama-3.2-3b.
### RAM 16GB
- Co the dung 7B quant 4-bit (GGUF): llama-3.1-8b, qwen2.5-7b, mistral-7b.
