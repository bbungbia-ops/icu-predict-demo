# Hướng dẫn pitching ICU Predict

> Mục tiêu: thuyết trình 6–7 phút. Đọc tự nhiên, không cần học thuộc từng chữ. Những chỗ đặt trong ngoặc vuông là phần cần thay bằng thông tin đội thi của bạn.

## 1. Một câu phải nhớ

**ICU Predict – Đúng bệnh nhân, đúng lý do, đúng thời điểm; bác sĩ quyết định.** Đây là nền tảng hỗ trợ điều phối để đội ICU biết bệnh nhân nào cần được bác sĩ rà soát trước, vì sao cần xem trước và bản ghi đó đã được xác nhận hay chưa. Hệ thống không thay thế bác sĩ, không chẩn đoán và không đưa y lệnh.

Đây là câu định vị dùng xuyên suốt bài pitch. Khi bị hỏi về AI, luôn quay lại câu này.

---

## 2. Kịch bản pitch 6–7 phút

### Mở đầu — 0:00–0:30

> “Một ca trực ICU có thể phải theo dõi nhiều bệnh nhân cùng lúc, với rất nhiều chỉ số thay đổi liên tục. Rủi ro không chỉ nằm ở việc thiếu dữ liệu, mà ở việc tín hiệu quan trọng bị nhìn thấy quá muộn hoặc không rõ ai đã rà soát nó.
>
> ICU Predict được tạo ra để trả lời thật nhanh ba câu hỏi: bệnh nhân nào cần xem trước, vì sao cần xem trước, và đã được bác sĩ rà soát chưa?”

Đừng mở đầu bằng “đây là một app AI dự đoán tử vong”. Điều đó vừa thiếu an toàn vừa dễ bị giám khảo phản biện.

### Vấn đề — 0:30–1:15

> “Trong ICU, MAP, PaO2/FiO2, bilirubin, creatinine, tiểu cầu, GCS và SOFA thường được xem trong bối cảnh rất phức tạp. Khi bác sĩ và điều dưỡng phải tổng hợp thủ công, khó ưu tiên được bệnh nhân cần xem trước và khó tạo dấu vết rằng cảnh báo đã được ai đối chiếu.
>
> Hiện nay dữ liệu có thể nằm rải rác; quy trình rà soát lại phụ thuộc vào kinh nghiệm và giao tiếp trong ca trực. Điều này làm mất thời gian, khó bàn giao và khó đo hiệu quả vận hành.”

Giải thích chỉ số thật ngắn nếu cần:

- **MAP**: huyết áp động mạch trung bình.
- **PaO2/FiO2**: chỉ số phản ánh khả năng oxy hóa.
- **Bilirubin/creatinine/tiểu cầu/GCS**: dữ liệu liên quan đến gan, thận, đông máu và tri giác.
- **SOFA**: điểm tổng hợp hỗ trợ mô tả suy cơ quan; trong app hiện là ngữ cảnh, không đưa thẳng vào mô hình AI để tránh trùng lặp.

### Giải pháp — 1:15–2:00

> “ICU Predict không thay bác sĩ quyết định. Hệ thống tiếp nhận bản ghi, kiểm tra giới hạn nhập liệu, tạo tín hiệu để sắp xếp ưu tiên, nêu lý do cần rà soát, và buộc phải có xác nhận của bác sĩ trong audit trail.
>
> Như vậy, thay vì nói AI quyết định thay con người, chúng tôi giúp con người điều phối công việc lâm sàng rõ hơn và có trách nhiệm hơn.”

Minh họa luồng trên slide:

`Dữ liệu có thời điểm lấy mẫu → kiểm tra dữ liệu → hàng đợi ưu tiên → bác sĩ rà soát/xác nhận → audit trail → đo hiệu quả Pilot`

### Demo sản phẩm — 2:00–3:15

Mở website, demo theo đúng thứ tự này:

1. **Dashboard “Điều phối đánh giá”**
   > “Đây là hàng đợi ưu tiên. Mỗi dòng không chỉ có nhãn ưu tiên mà còn có lý do để đội ngũ biết cần xem gì trước.”

2. **Tạo bản ghi đánh giá**
   > “Người dùng chọn bệnh nhân, nhập chỉ số và đặc biệt phải nhập thời điểm lấy mẫu. Hệ thống kiểm tra giới hạn hợp lý của dữ liệu trước khi lưu.”

3. **Kết quả bản ghi**
   > “Tại đây, hệ thống hiển thị các lý do hỗ trợ điều phối, trạng thái dữ liệu ngoài phạm vi huấn luyện nếu có và yêu cầu bác sĩ ghi nhận nhận định trước khi hoàn tất.”

4. **Xu hướng 6–12–24 giờ**
   > “Khi cùng bệnh nhân có các mẫu nối tiếp với thời điểm hợp lệ, hệ thống hiển thị chênh lệch số học trong 6, 12 và 24 giờ. Chúng tôi ghi rõ thời lượng quan sát thực tế, không gọi đây là dự báo diễn biến hay khuyến nghị điều trị.”

5. **Nhật ký đánh giá/Pilot**
   > “Điểm khác của chúng tôi là có thể kiểm tra bản ghi đã được rà soát hay chưa và đo được thời gian rà soát, phản hồi về tín hiệu và mức hữu ích trong Pilot.”

Nếu mạng chậm, chuẩn bị ảnh chụp 4 màn này trong slide. Đừng phụ thuộc hoàn toàn vào web online.

### AI và an toàn — 3:15–4:05

> “Mô hình hiện tại là prototype nghiên cứu dùng các chỉ số đầu vào đã định nghĩa. Chúng tôi không công bố sensitivity, AUROC hay tuyên bố dự báo một biến cố lâm sàng, vì outcome và cohort xác thực chưa được chốt cùng bệnh viện.
>
> Đây không phải điểm yếu bị che giấu; đây là cách chúng tôi thiết kế sản phẩm y tế có trách nhiệm. Hệ thống có cảnh báo dữ liệu ngoài phạm vi, bác sĩ giữ quyền xác nhận và mọi thao tác được lưu audit trail.”

Nói chậm ở phần này. Nó giúp dự án đáng tin hơn nhiều so với việc tuyên bố AI “dự đoán chính xác 95%”.

### Khách hàng và thị trường — 4:05–4:45

> “Khách hàng đầu tiên của chúng tôi là khoa ICU tại bệnh viện có quy trình số hóa cơ bản, quy mô khoảng 10–20 giường để Pilot. Người dùng trực tiếp là bác sĩ ICU, điều dưỡng điều phối và lãnh đạo khoa; người mua là bệnh viện hoặc đơn vị quản lý vận hành.
>
> Chúng tôi không cố bán ngay cho toàn bộ thị trường. Chúng tôi chứng minh hiệu quả tại một ICU trước, chuẩn hóa quy trình, rồi mới mở rộng sang các khoa và bệnh viện khác.”

### Mô hình kinh doanh — 4:45–5:25

> “ICU Predict cung cấp theo thuê bao B2B theo tháng, gắn với số giường, số tài khoản và mức hỗ trợ. Bản demo đã có quy trình tạo tài khoản tổ chức, chọn gói, thanh toán QR ngân hàng qua SePay và tự kích hoạt license key sau đối soát.
>
> Hiện bảng giá demo gồm Pilot có giám sát 15 triệu đồng/tháng, ICU Cơ bản 9 triệu đồng/tháng, ICU Chuyên sâu 18 triệu đồng/tháng và Enterprise báo giá theo hợp đồng. Gói Pilot cao hơn Core vì có phần hỗ trợ triển khai và rà soát sát hơn.”

Chỉ đưa bảng giá này khi giám khảo hỏi hoặc slide có đủ thời gian. Đừng để giá chiếm trọng tâm hơn giá trị lâm sàng/vận hành.

### Kế hoạch Pilot và đo lường — 5:25–6:10

> “Pilot của chúng tôi kéo dài tại một ICU 10–20 giường. Trước Pilot, đội ngũ chốt nguồn dữ liệu, đơn vị đo, người chịu trách nhiệm và baseline thời gian rà soát thủ công.
>
> Trong Pilot, chúng tôi đo bốn nhóm chỉ số: tỷ lệ bản ghi được bác sĩ xác nhận, thời gian rà soát, tỷ lệ tín hiệu chưa phù hợp theo phản hồi bác sĩ và mức hữu ích 1–5. Sau khi có outcome được bác sĩ định nghĩa và dữ liệu được phê duyệt, chúng tôi mới đánh giá sensitivity, specificity, AUROC và calibration.”

### Kết — 6:10–6:35

> “ICU Predict không cạnh tranh bằng lời hứa thay thế bác sĩ. Chúng tôi tạo ra một lớp điều phối an toàn để tín hiệu quan trọng đến đúng người, đúng lúc, có lý do và có trách nhiệm.
>
> Mục tiêu tiếp theo của đội là triển khai Pilot tại một ICU, chứng minh hiệu quả vận hành bằng dữ liệu thực và từng bước tích hợp HIS/EMR. Chúng tôi mong nhận được cơ hội kết nối với bệnh viện Pilot, cố vấn lâm sàng và đối tác triển khai.”

---

## 3. Bố cục slide đề xuất

| Slide | Tiêu đề | Nội dung nên có |
|---|---|---|
| 1 | ICU Predict | Một câu định vị + tên đội |
| 2 | Vấn đề trong ca trực ICU | 3 vấn đề: nhiều dữ liệu, khó ưu tiên, thiếu dấu vết rà soát |
| 3 | Giải pháp | Sơ đồ 6 bước của luồng làm việc |
| 4 | Sản phẩm đã có | 4 ảnh: dashboard, tạo bản ghi, kết quả, audit trail |
| 5 | AI có trách nhiệm | Giới hạn, cảnh báo dữ liệu, bác sĩ xác nhận, audit trail |
| 6 | Pilot 10–20 giường | Phạm vi, chỉ số đo, kết quả mong chứng minh |
| 7 | Khách hàng và doanh thu | Người dùng, người mua, thuê bao tháng |
| 8 | Lộ trình và lời kêu gọi | Pilot → chuẩn hóa → HIS/EMR → mở rộng; nhu cầu hỗ trợ |

Không nên dùng quá 8 slide. Mỗi slide tối đa một ý chính và 20–30 chữ.

---

## 4. Câu hỏi phản biện thường gặp

### “AI của bạn chính xác bao nhiêu phần trăm?”

> “Chúng tôi chưa công bố con số đó vì chưa có cohort lâm sàng được phê duyệt với outcome và mốc thời gian đã định nghĩa. Tuyên bố một con số ở giai đoạn này sẽ không có trách nhiệm. Pilot của chúng tôi được thiết kế để tạo dữ liệu cho sensitivity, specificity, AUROC và calibration sau đó.”

### “Vậy tại sao gọi là AI?”

> “AI trong phiên bản hiện tại tạo tín hiệu hỗ trợ sắp xếp ưu tiên từ các biến đầu vào. Nhưng giá trị thương mại cốt lõi là quy trình điều phối, giải thích tín hiệu, kiểm tra dữ liệu và audit trail — những thứ bệnh viện có thể đo được ngay trong Pilot.”

### “Khác gì Excel hoặc HIS/EMR?”

> “Excel lưu số liệu nhưng không tạo luồng xác nhận, phân quyền, cảnh báo phạm vi dữ liệu, audit trail và theo dõi phản hồi Pilot trong một quy trình. HIS/EMR là nguồn hồ sơ; ICU Predict hướng tới lớp hỗ trợ điều phối kết nối với nguồn đó, không thay thế HIS/EMR.”

### “Bạn xử lý dữ liệu bệnh nhân thế nào?”

> “Ở demo chỉ sử dụng dữ liệu minh họa. Khi Pilot thực tế, chúng tôi chỉ tiếp nhận dữ liệu đã được bệnh viện phê duyệt, tối thiểu hóa dữ liệu, phân quyền theo tổ chức, ghi audit trail và tuân theo yêu cầu bảo mật của đơn vị triển khai.”

### “Mô hình kinh doanh của bạn là gì?”

> “Ở cuộc thi, chúng tôi trình bày theo bốn tầng: demo miễn phí với dữ liệu giả lập; Pilot 2–3 tháng tại một ICU; thuê bao năm theo cơ sở hoặc số giường sau khi chuẩn hóa; và phí tích hợp HIS/EMR cùng hỗ trợ kỹ thuật. Chức năng tạo key và SePay trong MVP chỉ chứng minh năng lực thương mại hóa, không phải trọng tâm giá trị của dự án.”

### “Nếu AI xếp ưu tiên sai thì sao?”

> “Hệ thống không đưa y lệnh và không thay thế bác sĩ. Bác sĩ là người xác nhận; tín hiệu chưa phù hợp được ghi nhận trong Pilot. Chúng tôi cũng cảnh báo khi dữ liệu ngoài phạm vi huấn luyện, thay vì buộc người dùng tin vào điểm số.”

### “Bạn cần gì sau cuộc thi?”

> “Chúng tôi cần một đơn vị ICU Pilot, cố vấn lâm sàng để chốt outcome/quy trình đánh giá, và đối tác HIS/EMR để giảm nhập liệu thủ công.”

---

## 5. Checklist trước khi lên sân khấu

- [ ] Kiểm tra website online, đăng nhập và internet; chụp sẵn ảnh màn hình làm phương án dự phòng.
- [ ] Tạo sẵn một bệnh nhân demo và 2–3 bản ghi có thời điểm lấy mẫu khác nhau để hiển thị xu hướng.
- [ ] Chuẩn bị đúng ba ca giả lập: theo dõi thường quy, theo dõi ưu tiên và ưu tiên đánh giá; thử thêm một lần nhập thiếu hoặc ngoài giới hạn để cho thấy hàng rào dữ liệu.
- [ ] Không dùng dữ liệu bệnh nhân thật trong demo.
- [ ] Không nói “chẩn đoán”, “điều trị”, “dự đoán tử vong”, “độ chính xác 95%” hoặc bất kỳ chỉ số hiệu năng không có validation.
- [ ] Chuẩn bị 8 slide, font lớn, ít chữ; một người điều khiển demo.
- [ ] Tập đúng 3 lần, bấm giờ dưới 7 phút.
- [ ] Nếu có nhiều thành viên: người 1 nói vấn đề/giải pháp; người 2 demo/công nghệ; người 3 thương mại/Pilot/lời kêu gọi.

## 6. Phiên bản siêu ngắn 30 giây

> “ICU Predict là nền tảng hỗ trợ điều phối cho ICU. Chúng tôi giúp đội ngũ trả lời nhanh bệnh nhân nào cần rà soát trước, vì sao và đã được xác nhận chưa. Thay vì thay thế bác sĩ, hệ thống kiểm tra dữ liệu, tạo hàng đợi ưu tiên có giải thích và lưu audit trail. Chúng tôi bắt đầu bằng Pilot 10–20 giường, đo thời gian rà soát và mức hữu ích, rồi mới đánh giá mô hình trên dữ liệu được bệnh viện phê duyệt.”
