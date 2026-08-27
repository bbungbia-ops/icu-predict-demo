# Hướng dẫn mô hình và phạm vi MVP

## Mô hình hiện tại làm gì

ICU Predict hiện là **nguyên mẫu nghiên cứu/demo** dùng logistic regression có
thể truy xuất để hỗ trợ sắp xếp thứ tự rà soát bản ghi. Đây không phải phần mềm
chẩn đoán, kê đơn, cảnh báo điều trị tự động hay công cụ đã được xác thực lâm
sàng.

Mô hình dùng đúng sáu đầu vào thô: MAP, PaO2/FiO2, Bilirubin, Creatinine, số
lượng tiểu cầu và GCS. SOFA tổng chỉ được hiển thị làm ngữ cảnh; nó không được
đưa vào mô hình vì là chỉ số tổng hợp, chồng lấp với các thông số thô.

Điểm nội bộ của mô hình chỉ được lưu để tái lập bản ghi. Giao diện chỉ hiển thị
ba mức điều phối: **Ưu tiên đánh giá**, **Theo dõi ưu tiên** và **Theo dõi thường
quy**. Đây không phải xác suất lâm sàng, chẩn đoán hoặc mức độ nặng của bệnh
nhân.

## Giới hạn bắt buộc khi trình bày

- Không nói hệ thống dự báo biến cố trong 24 giờ/48 giờ.
- Không nói hệ thống dự báo tử vong, suy hô hấp hay bất kỳ outcome cụ thể nào.
- Không trình bày điểm mô hình là xác suất hoặc hiệu năng lâm sàng.
- Không dùng kết quả để thay thế đánh giá, y lệnh hay quy trình báo động của bác sĩ.

`data.json` chỉ có 100 dòng dữ liệu minh họa. Nguồn gốc chưa được xác minh và
chưa định nghĩa `Outcome=1` là gì hoặc xảy ra lúc nào. Chỉ số phát triển tốt
trên tập này là dấu hiệu dữ liệu demo quá dễ phân tách, **không** là bằng chứng
về hiệu năng thực tế.

## Cách chạy bản demo

Tại thư mục dự án, chạy:

```powershell
python -m unittest discover -s tests -v
python app.py
```

Mở `http://localhost:5000`. Khi đang ở chế độ demo, dùng `admin / admin123`.
Trước khi triển khai phải đặt `SECRET_KEY`, `ICU_PREDICT_ADMIN_USERNAME`,
`ICU_PREDICT_ADMIN_PASSWORD` và tắt `ICU_PREDICT_DEMO_MODE`.

Chỉ khi cần tạo lại mô hình từ dữ liệu minh họa, chạy:

```powershell
python train_icu_model.py
```

Lệnh này tạo `ai_model/icu_risk_model.joblib` và
`ai_model/icu_risk_model_report.json`. Không chạy lại bằng dữ liệu bệnh nhân
thật khi chưa có phê duyệt quản trị dữ liệu và nghiên cứu.

## Quy trình sử dụng ở buổi demo

1. Chọn bệnh nhân demo, nhập sáu thông số và SOFA làm ngữ cảnh.
2. Rà cờ dữ liệu, nhất là thông báo “ngoài phạm vi dữ liệu demo”.
3. Dùng tín hiệu để xếp thứ tự xem bản ghi; bác sĩ tự đối chiếu toàn bộ hồ sơ.
4. Ghi nhận nhận định trước khi xác nhận. Nhật ký kiểm toán giúp làm rõ trách
   nhiệm, không tự động ra quyết định.
5. Xuất PDF nếu cần lưu bản tóm tắt nghiên cứu; PDF hỗ trợ tiếng Việt Unicode.

## Điều kiện trước pilot dùng dữ liệu thật

1. Bác sĩ phụ trách chốt **một** outcome duy nhất, nguồn nhãn và mốc thời gian.
2. Lập từ điển dữ liệu: quần thể, tiêu chí chọn/loại, đơn vị, dữ liệu thiếu và
   cách xử lý dữ liệu bất thường.
3. Dùng dữ liệu lịch sử đã khử định danh trong hạ tầng do bệnh viện kiểm soát.
4. Chia dữ liệu theo thời gian và kiểm định ở cơ sở thứ hai nếu có thể.
5. Báo cáo AUROC, PR-AUC, độ nhạy, độ đặc hiệu, PPV, NPV, calibration/Brier và
   khoảng tin cậy; so sánh với quy trình hiện hành.
6. Chạy song song không hiển thị cảnh báo trước. Hội đồng lâm sàng quyết định
   ngưỡng và quy trình leo thang, không phải đội phát triển.
7. Phiên bản hóa dữ liệu, mô hình, ngưỡng và lần phát hành; theo dõi drift,
   cảnh báo bỏ sót và việc bác sĩ ghi đè sau triển khai.

## Lộ trình sản phẩm

MVP hiện trình diễn luồng ghi nhận → điều phối rà soát → xác nhận bác sĩ → nhật
ký kiểm toán → báo cáo. CSV/Excel, HIS/EMR, đồng bộ thời gian thực và phân tích
xu hướng là hạng mục tiếp theo, chỉ triển khai sau khi có dữ liệu mẫu, quy trình
tích hợp và tiêu chí kiểm thử được phía bệnh viện chấp thuận.
