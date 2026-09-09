# Checklist mô hình ICU Predict

Tài liệu này phân biệt rõ giữa chức năng đã có trong demo và bằng chứng cần có trước khi tuyên bố hiệu năng lâm sàng.

## Đã triển khai trong demo

- [x] Kiểm tra phạm vi nhập liệu và cảnh báo giá trị ngoài phạm vi huấn luyện.
- [x] Không đưa điểm SOFA tổng vào vector đầu vào AI để tránh trùng lặp biến.
- [x] Lý do ưu tiên có thể truy xuất, xác nhận bác sĩ và audit trail.
- [x] Bắt buộc lưu thời điểm lấy mẫu cho bản ghi mới.
- [x] Đối chiếu mô tả 6–12–24 giờ từ các mẫu cùng bệnh nhân; hiển thị thời lượng thực tế và chênh lệch số học.
- [x] Trạng thái "chưa xác thực lâm sàng" hiển thị ngay trong bản ghi đánh giá.

## Chưa được tuyên bố — cần dữ liệu Pilot được phê duyệt

- [ ] Outcome lâm sàng và mốc dự báo: phải do bác sĩ/đơn vị Pilot định nghĩa trước.
- [ ] Sensitivity, specificity, PPV, NPV, AUROC và calibration: chỉ tính sau khi có cohort độc lập, nhãn outcome và quy tắc đối chiếu rõ ràng.
- [ ] Temporal/external validation: kiểm tra trên giai đoạn và cơ sở khác với dữ liệu phát triển mô hình.
- [ ] Kết nối HIS/EMR, kiểm tra chất lượng nguồn dữ liệu và theo dõi drift: cần thỏa thuận tích hợp, phân quyền và quy trình bảo mật với bệnh viện.

## Quy trình đề xuất trước khi mở rộng

1. Chốt định nghĩa outcome, thời hạn dự báo, tiêu chuẩn loại trừ và người chịu trách nhiệm lâm sàng.
2. Thu thập dữ liệu đã khử định danh, có phê duyệt phù hợp; đóng băng bộ đánh giá trước khi xem kết quả.
3. Đánh giá discrimination, calibration và ngưỡng vận hành; báo cáo khoảng tin cậy cùng số ca/số biến cố.
4. Rà soát cùng hội đồng chuyên môn, bảo mật và pháp chế trước bất kỳ tuyên bố hoặc sử dụng lâm sàng nào.
