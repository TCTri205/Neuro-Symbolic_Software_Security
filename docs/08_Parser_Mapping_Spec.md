# 08. Parser Mapping Spec (Python AST -> IR)

Mục tiêu: chuẩn hóa cách chuyển Python AST sang IR theo `docs/07_IR_Schema.md`. Tài liệu này tập trung vào quy tắc mapping, thứ tự xây node, và các ràng buộc deterministic.

## 1) Nguyên tắc chung

- Deterministic: cùng input tạo cùng output (node order, ids, attrs).
- Stable IDs: `id = f"{kind}:{file}:{line}:{col}:{index}"`.
- Top-down traversal: Module -> Class/Function -> Statements -> Expressions.
- Không tạo node cho `Pass`; `Expr` chỉ giữ node value.

## 2) Scope & Block

- Tạo `scope_id` theo thứ tự: module -> class -> function -> lambda.
- Mỗi Function/Class/Module tạo một `Block` body.
- `If/While/For/Try/With` tạo `Block` con cho body/orelse/handler/finally.

## 3) Node creation order

Thứ tự khuyến nghị:

1. Tạo node cha (Module/Class/Function/If/While/For/Try/With)
2. Tạo Block con và liên kết stmt_ids
3. Tạo statement nodes (Assign/Return/Call...)
4. Tạo expression nodes (Name/Literal/BinOp/Call...)
5. Tạo edges (flow/true/false/exception/await/yield)
6. Ghi symbols (defs/uses)

## 4) Mapping chi tiết (tóm tắt)

Tham chiếu bảng mapping ở `docs/07_IR_Schema.md`.

## 5) CFG edge rules (cốt lõi)

- Mặc định: tạo `flow` edges theo thứ tự statement trong cùng Block.
- `If`: tạo `true/false` edges từ If node -> body/orelse Block.
- `While`: tạo `true/false` edges từ While node -> body/exit Block + edge quay lại `flow`.
- `For`: tạo edges từ iter -> body/exit Block.
- `Try`: tạo `exception` edges từ Try -> handler blocks; sau body/handler đều nối finally.
- `Await/Yield`: tạo edge type `await`/`yield` để ghi nhận điểm chuyển trạng thái.

## 6) Normalization & literals

- Strip docstring/comment trước khi tạo nodes.
- String literal: lưu `value` ngắn (cap), phần còn lại lưu `hash` trong attrs.
- Numeric/Bool/None giữ nguyên trong `value`.

## 7) Symbol table

- Param defs gắn vào Function node.
- Assign tạo def cho target Name.
- Name usage gắn vào `uses` theo scope gần nhất.

## 8) Error handling

- Nếu AST node thiếu span (line/col), gán `-1` và đánh dấu `attrs.missing_span=true`.
- Nếu gặp node chưa hỗ trợ, tạo `Literal` với `value_type="Unknown"` và tag `attrs.unsupported=true`.

## 9) Output format

- Single JSON hoặc JSONL đều hợp lệ.
- Node/edge order theo `span` để ổn định.
