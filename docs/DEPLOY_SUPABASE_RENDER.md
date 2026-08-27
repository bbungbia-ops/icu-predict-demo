# Đưa ICU Predict lên Supabase + Render (bản thi miễn phí)

## Kiến trúc triển khai

```text
Người dùng ──────> https://<ten-app>.onrender.com/
                           │
SePay ───────────> /license-admin/webhooks/sepay/payment
                           │
                    PostgreSQL Supabase
                           │
Quản trị license ─> /license-admin/login
```

Website người dùng và cổng quản trị key được chạy trong **một** dịch vụ Render,
nhưng mỗi bên có session riêng. Cả hai cùng dùng `DATABASE_URL` của PostgreSQL
Supabase, nên giá, đơn hàng, key và trạng thái thanh toán luôn đồng bộ.

> Đây là cấu hình phục vụ học tập/cuộc thi. Gói miễn phí không có sao lưu phù
> hợp, có thể tạm dừng khi không hoạt động và không đạt yêu cầu vận hành dữ liệu
> y tế thực tế.

## 1. Tạo database Supabase

1. Đăng nhập [Supabase](https://supabase.com/dashboard), tạo **New project**.
2. Chọn region gần Việt Nam nhất, đặt mật khẩu database riêng và lưu ở nơi an
   toàn. Không dùng mật khẩu tài khoản Supabase làm mật khẩu database.
3. Khi project chạy xong, bấm **Connect** và chọn **Session pooler**.
4. Sao chép chuỗi PostgreSQL cổng `5432`, thêm `?sslmode=require` nếu chuỗi
   chưa có phần SSL. Dạng chuỗi phù hợp là:

   ```text
   postgresql://postgres.<project-ref>:<database-password>@aws-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

Không cần tự tạo bảng SQL: lần chạy đầu tiên của ứng dụng sẽ tạo toàn bộ schema
và dữ liệu demo một cách tự động.

## 2. Đưa source lên GitHub

Render Free lấy mã nguồn từ GitHub, GitLab hoặc Bitbucket. Tạo một repository
**private** mới, đưa toàn bộ thư mục dự án vào đó, và tuyệt đối không thêm
`.env`, file `.db`, mật khẩu hoặc chuỗi `DATABASE_URL` vào Git.

File `render.yaml` đã có sẵn trong dự án. Nó chỉ khai báo tên các biến bí mật,
không chứa giá trị bí mật.

## 3. Tạo dịch vụ Render Free

1. Vào [Render](https://dashboard.render.com/), đăng nhập và kết nối repository.
2. Chọn **New → Blueprint**, chọn repository này. Render tự đọc `render.yaml`.
3. Nhập các giá trị Render yêu cầu:

   | Biến | Giá trị cần đặt |
   |---|---|
   | `DATABASE_URL` | Chuỗi Session pooler của Supabase ở bước 1 |
   | `LICENSE_ADMIN_USERNAME` / `LICENSE_ADMIN_PASSWORD` | Tài khoản quản trị key mới, mạnh |
   | `ICU_PREDICT_ADMIN_USERNAME` / `ICU_PREDICT_ADMIN_PASSWORD` | Tài khoản quản trị demo mới, mạnh |
   | `PAYMENT_BANK_NAME` | Tên ngân hàng đã liên kết SePay |
   | `PAYMENT_ACCOUNT_NUMBER` | Số tài khoản nhận tiền |
   | `PAYMENT_ACCOUNT_NAME` | Tên chủ tài khoản |
   | `LICENSE_VALIDATION_URL` | Để trống lần deploy đầu; điền ở bước 4 |
   | `SEPAY_WEBHOOK_SECRET` | Để trống lần deploy đầu; điền ở bước 5 |

4. Sau khi deploy thành công, Render cấp URL dạng
   `https://icu-predict-demo.onrender.com`. Cập nhật biến
   `LICENSE_VALIDATION_URL` thành:

   ```text
   https://icu-predict-demo.onrender.com/license-admin/api/v1/licenses/validate
   ```

5. Deploy lại sau khi thay biến.

## 4. Kiểm tra sau deploy

- Website người dùng: `https://<ten-app>.onrender.com/login`
- Cổng quản trị key: `https://<ten-app>.onrender.com/license-admin/login`
- Endpoint SePay: `https://<ten-app>.onrender.com/license-admin/webhooks/sepay/payment`

Đăng nhập, tạo một tài khoản tổ chức thử, tạo đơn hàng và kiểm tra key ở trạng
thái **Chờ thanh toán** trước khi thử SePay.

## 5. Cấu hình SePay sau khi đã có URL Render

Trong SePay vào **Tích hợp Webhooks → Tạo webhook**:

1. Chọn tài khoản ngân hàng nhận tiền đã liên kết.
2. Tên: `ICU Predict – kích hoạt key`.
3. URL nhận webhook: endpoint SePay ở bước 4.
4. Chọn **Tiền vào**, định dạng **JSON**, bật tự gửi lại khi lỗi.
5. Chọn quy tắc nhận diện mã thanh toán với tiền tố `ICUP-` và bỏ qua giao dịch
   không có mã.
6. Chọn **HMAC-SHA256**. Sao chép Secret Key vừa sinh và đặt vào biến
   `SEPAY_WEBHOOK_SECRET` trong Render, sau đó deploy lại.

Không gửi Secret Key, database password, thông tin đăng nhập ngân hàng hay OTP
qua chat và không đặt chúng vào source code.

## Giới hạn gói miễn phí

- Render Free có thể sleep khi không có truy cập. Do đó lần webhook đầu tiên
  sau khi sleep có thể chậm; SePay cần bật tự gửi lại khi server báo lỗi.
- Supabase Free có thể pause project sau một thời gian không hoạt động.
- Trước buổi thi, mở website và kiểm tra đăng nhập/đơn hàng để đánh thức dịch
  vụ, đồng thời chuẩn bị một luồng thanh toán mô phỏng dự phòng.
