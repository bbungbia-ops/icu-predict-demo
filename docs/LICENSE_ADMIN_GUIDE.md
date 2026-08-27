# Hướng dẫn vận hành License Admin

## 1. Hệ thống gồm những gì

`license_admin` là cổng nội bộ, tách biệt với ICU Predict. Nó tạo license key,
quản lý đơn hàng, nhận xác nhận chuyển khoản và mở/khóa quyền sử dụng.

```text
Khách hàng -> ICU Predict -> License Admin -> webhook ngân hàng -> kích hoạt key
                   |                  |
             tạo tài khoản       cùng danh mục gói/giá
                   |
           xem đơn và key của tổ chức
```

Hệ thống chỉ trao đổi license key, mã định danh ứng dụng và phiên bản app.
Không gửi bệnh nhân, chỉ số sinh tồn hay bản ghi đánh giá sang cổng license.

## 2. Chạy demo trên máy

Mở hai cửa sổ PowerShell tại thư mục dự án.

Ở cửa sổ thứ nhất chạy cổng quản trị:

```powershell
python run_license_admin.py
```

Mở `http://localhost:5050`. Tài khoản demo mặc định là
`license_admin / admin123`. Trước khi trình diễn bên ngoài, đổi thông tin này
bằng biến môi trường.

Ở cửa sổ thứ hai chạy ICU Predict:

```powershell
python app.py
```

Mở `http://localhost:5000`.

## 3. Luồng demo nên trình bày

1. Trên ICU Predict, vào **Tạo tài khoản tổ chức & mua key**, điền thông tin
   người phụ trách rồi chọn gói. Giá, thời hạn và mã gói được lấy trực tiếp từ
   `license_admin/plans.py`, nên không thể lệch giữa hai website.
2. Hệ thống tạo đơn hàng, license key và nội dung chuyển khoản duy nhất ở
   License Admin. Khách chỉ thấy hướng dẫn thanh toán; key chưa được hiển thị
   đầy đủ hoặc kích hoạt trước khi nhận giao dịch hợp lệ.
3. Trong môi trường demo, quản trị viên mở đơn trong License Admin và bấm
   **Mô phỏng thanh toán**. Hệ thống đổi đơn hàng thành **Đã thanh toán**,
   kích hoạt key và tính ngày hết hạn theo gói.
4. Khách mở lại chi tiết đơn trên ICU Predict để thấy trạng thái mới và key
   đang hoạt động. License Admin đồng thời có nhật ký đối soát và xác thực.
5. Bật kiểm tra key theo phần 5 khi muốn khóa các màn hình lâm sàng cho tổ
   chức chưa có key hoạt động.

## 4. Tích hợp SePay để tự động xác nhận chuyển khoản

ICU Predict đã có endpoint riêng cho SePay:

```text
POST https://license-admin.ten-mien-cua-ban.com/webhooks/sepay/payment
```

Endpoint dùng **HMAC-SHA256** (không dùng chế độ không xác thực hoặc API key
đơn giản). SePay gửi `X-SePay-Signature` và `X-SePay-Timestamp`; hệ thống kiểm
tra chữ ký trên raw body, chặn webhook quá 5 phút, chặn giao dịch trùng, chỉ
nhận `transferType = in`, và chỉ kích hoạt license nếu mã chuyển khoản cùng số
tiền khớp tuyệt đối.

### Cấu hình tại SePay

1. Liên kết tài khoản nhận tiền trong SePay và kiểm tra nó ở trạng thái hoạt
   động.
2. Vào **Tích hợp → Webhooks → Thêm webhook**.
3. Dán URL endpoint ở trên. Môi trường thật bắt buộc dùng URL HTTPS công khai;
   `localhost` không thể nhận webhook từ SePay.
4. Chọn **Tiền vào**, `application/json`, bật tự gửi lại khi có lỗi, và chọn
   đúng tài khoản ngân hàng nhận tiền.
5. Trong cấu hình mã thanh toán, cho SePay nhận diện tiền tố **`ICUP-`**; bật
   **Bỏ qua giao dịch không có mã**. Tiền tố này phải viết hoa đúng như vậy.
6. Ở bước bảo mật chọn **HMAC-SHA256**, tạo/copy Secret Key và đặt nó trong
   Environment của License Admin — không gửi secret vào chat, không commit vào
   Git:

   ```text
   SEPAY_WEBHOOK_SECRET=<secret-hmac-tu-sepay>
   SEPAY_WEBHOOK_MAX_AGE_SECONDS=300
   ```

7. Dùng **Gửi thử** trong SePay để kiểm tra endpoint trả `{"success": true}`.
   Sau đó tạo một đơn chờ thanh toán và chuyển một khoản nhỏ theo đúng mã/số
   tiền ở môi trường Test mode hoặc tài khoản thử trước khi dùng tiền thật.

Payload SePay được hỗ trợ trực tiếp gồm `id`, `code`, `content`,
`transferType`, `transferAmount`, `description` và `referenceCode`. Mã `id`
của SePay được lưu làm khóa chống trùng; cùng một webhook replay sẽ không thể
kích hoạt hoặc ghi tiền cho đơn lần hai.

> Chức năng này là **webhook nhận biến động số dư** để kích hoạt key, không có
> quyền trích tiền từ tài khoản khách. Nếu sau này cần màn hình tra cứu/đối soát
> chủ động từ SePay API v2, hãy thêm API token ở một service backend riêng,
> không đưa token ra trình duyệt.

## 5. Webhook ngân hàng tổng quát (tùy chọn)

Endpoint dành cho ngân hàng hoặc bên đối soát:

```text
POST /webhooks/bank/payment
Header: X-Bank-Signature: <HMAC-SHA256 của raw JSON body>
```

Payload chuẩn mà adapter hiện hỗ trợ:

```json
{
  "event_id": "bank-event-unique-001",
  "transaction_id": "ma-giao-dich-ngan-hang",
  "status": "success",
  "amount": 108000000,
  "transfer_content": "ICUP-ABC123",
  "payer_name": "Nguyen Van A"
}
```

License chỉ được kích hoạt khi chữ ký hợp lệ, `status` là `success`, nội dung
chuyển khoản khớp chính xác và số tiền đúng tuyệt đối. Webhook trùng lặp được
bỏ qua an toàn nhờ `event_id`; giao dịch dùng lại bị từ chối.

Chuyển khoản thiếu/sai nội dung hoặc sai số tiền được ghi là `unmatched` hoặc
`amount_mismatch`, **không** tự động kích hoạt key. Quản trị viên cần đối soát
và tạo/điều chỉnh đơn đúng, thay vì sửa tay key đang chờ thanh toán.

Mỗi ngân hàng/cổng đối soát có cấu trúc JSON và cách ký khác nhau. Khi chọn
nhà cung cấp, chỉ cần thêm adapter biến payload của họ về sáu trường phía trên
và dùng secret do họ cung cấp. Không dùng chế độ “Mô phỏng thanh toán” trong
môi trường thật.

## 6. Bật kiểm tra key cho ICU Predict

Sau khi có một key đã kích hoạt, khai báo các biến sau trước khi chạy ICU
Predict. `ICU_INTEGRATION_SHARED_SECRET` phải giống hệt ở cả hai ứng dụng.
Với luồng tự đăng ký, key của tổ chức được gắn tự động vào tài khoản khách;
`ICU_LICENSE_KEY` chỉ là key dự phòng cho mô hình một bệnh viện/một instance.

```powershell
$env:ICU_LICENSE_ENFORCEMENT_ENABLED = 'true'
$env:ICU_LICENSE_KEY = 'ICU-XXXXXX-XXXXXX-XXXXXX-XXXXXX'
$env:LICENSE_VALIDATION_URL = 'http://127.0.0.1:5050/api/v1/licenses/validate'
$env:ICU_INTEGRATION_SHARED_SECRET = 'mot-bi-mat-chung-dai-va-ngau-nhien'
$env:LICENSE_ADMIN_DATABASE_PATH = 'D:\du-lieu-an-toan\license_admin.db'
python app.py
```

Khi bật chế độ này, các màn hình lâm sàng chỉ mở nếu license đang hoạt động.
Nếu key hết hạn, bị thu hồi, chưa thanh toán hoặc không thể xác thực với cổng
license, tổ chức chỉ được vào phần **Tài khoản & gói dịch vụ** để xem/hoàn tất
đơn hàng; các chức năng lâm sàng bị chặn. Đây là cơ chế **fail closed**.

## 7. Hết hạn, thu hồi và lỗi thường gặp

- Key quá ngày `expires_at` sẽ tự đổi thành **Đã hết hạn** khi có kiểm tra từ
  cổng admin hoặc từ ICU Predict.
- Quản trị viên có thể **Thu hồi key** đang hoạt động từ trang chi tiết.
- Webhook sai chữ ký nhận HTTP 401 và không được xử lý.
- Webhook SePay quá 5 phút, sai `X-SePay-Signature`, sai số tiền, sai nội dung
  hoặc là giao dịch tiền ra đều không kích hoạt key; trạng thái được ghi trong
  nhật ký webhook để đối soát.
- Key chưa thanh toán/hết hạn/thu hồi không qua được API xác thực.

## 8. Chuẩn bị đưa online

SQLite chỉ phù hợp demo cục bộ. Để chạy online, cần một cơ sở dữ liệu bền vững
(ví dụ PostgreSQL/Supabase), HTTPS, tên miền riêng và một nhà cung cấp webhook
ngân hàng đã ký hợp đồng. Không lưu secret trong source code hoặc Git.

Trong bản demo cục bộ, website người dùng đọc kho license chung qua
`LICENSE_ADMIN_DATABASE_PATH` để đảm bảo trạng thái và giá đồng bộ tức thì.
Khi tách hai dịch vụ online, **không chia sẻ file SQLite qua mạng**: thay bằng
PostgreSQL/Supabase cùng lớp phân quyền, hoặc API nội bộ có HMAC/mTLS cho tạo
đơn và tra cứu trạng thái. Endpoint công khai không được phép trả key của tổ
chức khác.

Khi dùng cấu hình Render trong dự án này, hai website được đóng gói thành **một
dịch vụ**. Các URL và lệnh chạy tương ứng là:

```text
Website khách:   https://<ten-app>.onrender.com/
License Admin:   https://<ten-app>.onrender.com/license-admin/login
Gunicorn:         gunicorn --workers 1 --bind 0.0.0.0:$PORT deployment:application
```

Khai báo các biến trong `.env.example` vào mục Environment của Render. Trên môi
trường thật phải đặt `LICENSE_ADMIN_DEMO_MODE=false`, dùng URL HTTPS công khai
cho webhook và thay toàn bộ secret/mật khẩu demo. Hướng dẫn đầy đủ ở
`docs/DEPLOY_SUPABASE_RENDER.md`.
