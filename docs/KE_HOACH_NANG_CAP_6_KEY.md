# Kế hoạch nâng cấp ICU Predict theo góp ý mentor

## Key 1 — Giá trị thực tiễn

- [x] Thống nhất định vị: **“Đúng bệnh nhân, đúng lý do, đúng thời điểm; bác sĩ quyết định.”**
- [x] Dashboard và trang giới thiệu xoay quanh ba câu hỏi: ai cần xem trước, vì sao, đã rà soát chưa.

## Key 2 — Quy trình đổi mới

- [x] Hiển thị quy trình sáu bước: nhập dữ liệu → kiểm tra chất lượng → phân loại ưu tiên → giải thích → bác sĩ xác nhận → audit trail.
- [x] Không mô tả sản phẩm như một công cụ tính SOFA đơn thuần.

## Key 3 — Demo thuyết phục

- [x] Có hàng đợi ưu tiên, giải thích lý do, xác nhận bác sĩ, PDF và dashboard cập nhật sau xác nhận.
- [x] Có kịch bản ba ca giả lập trên trang Pilot.
- [x] Bổ sung xác nhận đơn vị và thời điểm lấy mẫu trước khi lưu; dữ liệu thiếu/không hợp lý bị chặn, dữ liệu ngoài phạm vi huấn luyện bị gắn cờ.
- [ ] Trước ngày thi: chuẩn bị sẵn ba ca giả lập trên tài khoản demo và ảnh chụp dự phòng khi mạng yếu.

## Key 4 — Cơ sở khoa học và giới hạn

- [x] SOFA chỉ là ngữ cảnh, không được đưa vào đầu vào AI cùng các thành phần liên quan.
- [x] Công khai phiên bản, nguồn dữ liệu minh họa chưa xác minh và trạng thái chưa xác thực lâm sàng.
- [ ] Cần có cố vấn bác sĩ hồi sức/giảng viên y khoa trước Pilot thực tế.
- [ ] Cần cohort dữ liệu được phê duyệt, outcome và mốc dự báo do chuyên gia định nghĩa trước khi công bố hiệu năng.

## Key 5 — Pilot an toàn

- [x] Đo thời gian rà soát, phản hồi tín hiệu chưa phù hợp và mức hữu ích.
- [x] Định vị Pilot 01 ICU, 10–20 giường, 2–3 tháng, dữ liệu giả lập hoặc chế độ quan sát.
- [ ] Chốt baseline thời gian thao tác, tiêu chuẩn “bị bỏ sót” và khảo sát hài lòng cùng đơn vị Pilot.

## Key 6 — Mô hình kinh doanh

- [x] MVP vẫn có tài khoản tổ chức, key và SePay để chứng minh khả năng thương mại hóa.
- [x] Pitch chuyển trọng tâm sang demo miễn phí → Pilot 2–3 tháng → thuê bao năm theo cơ sở/số giường → phí HIS/EMR và hỗ trợ kỹ thuật.
- [ ] Chốt bảng giá thuê bao năm với chi phí triển khai trước khi ký với bệnh viện; không tự chuyển mức giá hiện có khi chưa có quyết định kinh doanh.
