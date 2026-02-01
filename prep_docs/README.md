# Tài liệu Chuẩn bị & Quy hoạch (Prep Docs)

Thư mục này chứa các tài liệu phục vụ cho quá trình chuẩn bị, nghiên cứu và quy hoạch phát triển hệ thống NSSS.

## 📂 Danh mục tài liệu quan trọng

1.  **[Manifesto (Nguyên tắc)](00_principles/manifesto.md):** "Kim chỉ nam" của dự án (Privacy, Low-spec).
2.  **[Master Roadmap](NSSS_NEXT_PHASES.md):** Lộ trình phát triển tổng thể v2.3+.
3.  **[Decision Log (Nhật ký quyết định)](DECISION_LOG.md):** Nơi tra cứu nhanh các quyết định kỹ thuật quan trọng.
4.  **[Colab Audit Report](01_drafts/colab_notebooks_audit_report.md):** Kết quả rà soát hạ tầng chạy trên Colab.

## 📂 Cấu trúc thư mục

| Thư mục | Mô tả |
|---|---|
| `00_principles/` | Các nguyên tắc cốt lõi không thay đổi. |
| `01_drafts/` | Bản nháp các phương án (AI Model, DevSecOps...). |
| `02_decisions/` | Chi tiết các quyết định đã chốt (ADRs). |
| `templates/` | Mẫu tài liệu chuẩn. |
| `assets/` | File config mẫu, hình ảnh. |

## 🔄 Quy trình làm việc (Workflow)

1.  **Ý tưởng:** Tạo file trong `01_drafts/` (dùng `templates/proposal_template.md`).
2.  **Đối chiếu:** So khớp với `00_principles/manifesto.md`.
3.  **Chốt:** Lưu quyết định vào `02_decisions/` và cập nhật `DECISION_LOG.md`.
4.  **Thực hiện:** Code dựa trên tài liệu đã chốt.

---
*Tài liệu này được duy trì để đảm bảo sự thống nhất và bền vững của dự án.*
