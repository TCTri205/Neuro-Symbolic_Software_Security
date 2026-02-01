# [Draft] Kế hoạch Công bố Khoa học & Ảnh hưởng

**Người đề xuất:** NSSS Team
**Ngày:** 01/02/2026
**Trạng thái:** Draft

## 1. Mục tiêu (Objectives)
*   Nâng tầm NSSS từ một công cụ kỹ thuật thành một đóng góp khoa học (Scientific Contribution).
*   Công bố phương pháp tiếp cận Neuro-Symbolic Hybrid (kết hợp SSA tĩnh + LLM ngữ nghĩa) cho cộng đồng.

## 2. Sản phẩm Đầu ra (Deliverables)
### A. Technical Report (Báo cáo Kỹ thuật)
*   **Tiêu đề:** "NSSS: A Hybrid Neuro-Symbolic Approach for Securing Dynamic Languages"
*   **Nội dung:**
    *   Kiến trúc 6 lớp (6-layer architecture).
    *   Thuật toán Hybrid Router (ADR-001).
    *   Kết quả Benchmark so với Semgrep và Bandit.
*   **Định dạng:** Sử dụng **Typst** (hiện đại, đẹp hơn LaTeX) hoặc Markdown chuẩn bị cho ArXiv.

### B. Reproducibility Package (Gói Tái lập)
*   Code, Dataset, và Script để bất kỳ ai cũng có thể chạy lại thí nghiệm và ra kết quả y hệt.
*   Docker container chứa sẵn môi trường thí nghiệm.

## 3. Lộ trình Công bố
1.  **Tháng 1-2:** Hoàn thiện Benchmark Protocol và thu thập số liệu (Metric Collection).
2.  **Tháng 3:** Viết bản nháp Technical Report.
3.  **Tháng 4:** Public lên ArXiv (Preprint).
4.  **Tháng 6+:** (Tùy chọn) Gửi bài tới các hội thảo SE/Security (như MSR, ICSE-SEIP).

## 4. Công cụ Hỗ trợ (Research Stack)
*   **Viết lách:** Typst (Web app miễn phí), Obsidian.
*   **Quản lý trích dẫn:** Zotero (Free, Open Source).
*   **Vẽ hình:** Mermaid.js (cho sơ đồ luồng), Excalidraw (cho kiến trúc high-level).
*   **Lưu trữ:** GitHub Pages (cho Documentation/Project Website).

## 5. Checklist Triển khai
- [ ] Chọn Template Typst phù hợp cho báo cáo.
- [ ] Tạo thư mục `research/` trong repo (để chứa các script đo đạc riêng biệt).
- [ ] Viết README hướng dẫn "How to reproduce benchmarks".
