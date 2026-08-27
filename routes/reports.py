from flask import Blueprint, current_app, send_file
from routes.auth import login_required
from models.database import get_db_connection
from models.signal_presentation import describe_signal
from fpdf import FPDF
import io
import os
from datetime import datetime
from pathlib import Path

reports_bp = Blueprint('reports', __name__)


def resolve_unicode_fonts() -> tuple[Path, Path, Path]:
    """Return Unicode-capable fonts, with a project bundle taking precedence.

    Segoe UI ships with Windows and supports Vietnamese plus common clinical
    symbols such as subscript digits. A deployment can provide bundled Noto Sans
    files in assets/fonts or override the regular font through ICU_PREDICT_PDF_FONT.
    """
    project_dir = Path(__file__).resolve().parents[1]
    bundled_dir = project_dir / 'assets' / 'fonts'
    candidates = [
        (bundled_dir / 'NotoSans-Regular.ttf', bundled_dir / 'NotoSans-Bold.ttf', bundled_dir / 'NotoSans-Italic.ttf'),
        (Path(os.environ.get('ICU_PREDICT_PDF_FONT', '')), Path('C:/Windows/Fonts/arialbd.ttf'), Path('C:/Windows/Fonts/ariali.ttf')),
        (Path('C:/Windows/Fonts/segoeui.ttf'), Path('C:/Windows/Fonts/segoeuib.ttf'), Path('C:/Windows/Fonts/segoeuii.ttf')),
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf'), Path('C:/Windows/Fonts/ariali.ttf')),
    ]
    for regular, bold, italic in candidates:
        if str(regular) != '.' and regular.is_file() and bold.is_file() and italic.is_file():
            return regular, bold, italic
    raise RuntimeError(
        'Không tìm thấy font Unicode cho báo cáo PDF. Hãy thêm Noto Sans vào assets/fonts hoặc đặt ICU_PREDICT_PDF_FONT.'
    )


class ICUReport(FPDF):
    """Unicode-safe PDF report for ICU research records."""

    def __init__(self):
        super().__init__()
        regular, bold, italic = resolve_unicode_fonts()
        self.add_font('Vietnamese', '', str(regular))
        self.add_font('Vietnamese', 'B', str(bold))
        self.add_font('Vietnamese', 'I', str(italic))

    def header(self):
        self.set_font('Vietnamese', 'B', 16)
        self.cell(0, 10, 'ICU PREDICT', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Vietnamese', '', 10)
        self.cell(0, 6, 'Bản ghi nghiên cứu hỗ trợ quy trình lâm sàng', align='C', new_x='LMARGIN', new_y='NEXT')
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Vietnamese', 'I', 8)
        self.cell(0, 10, f'ICU Predict - Bản ghi nghiên cứu - Trang {self.page_no()}/{{nb}}', align='C')


@reports_bp.route('/report/<int:prediction_id>')
@login_required
def generate_report(prediction_id):
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    prediction = conn.execute('''
        SELECT pr.*, p.name as patient_name, p.patient_code, p.age, p.gender, p.ward,
               p.admission_date, u.full_name as doctor_name
        FROM predictions pr
        LEFT JOIN patients p ON pr.patient_id = p.id
        LEFT JOIN users u ON pr.predicted_by = u.id
        WHERE pr.id = ?
    ''', (prediction_id,)).fetchone()

    conn.close()

    if not prediction:
        return 'Không tìm thấy dữ liệu', 404

    # Create PDF
    pdf = ICUReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Patient info section
    pdf.set_font('Vietnamese', 'B', 14)
    pdf.cell(0, 10, 'THÔNG TIN BỆNH NHÂN', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Vietnamese', '', 11)
    info_data = [
        ('Mã bệnh nhân:', prediction['patient_code'] or 'N/A'),
        ('Họ và tên:', prediction['patient_name'] or 'N/A'),
        ('Tuổi:', str(prediction['age']) if prediction['age'] else 'N/A'),
        ('Giới tính:', prediction['gender'] or 'N/A'),
        ('Khoa:', prediction['ward'] or 'N/A'),
        ('Ngày nhập viện:', prediction['admission_date'] or 'N/A'),
        ('Bác sĩ:', prediction['doctor_name'] or 'N/A'),
        ('Thời gian tạo bản ghi:', prediction['predicted_at'] or 'N/A'),
    ]

    for label, value in info_data:
        pdf.set_font('Vietnamese', 'B', 11)
        pdf.cell(55, 8, label)
        pdf.set_font('Vietnamese', '', 11)
        pdf.cell(0, 8, value, new_x='LMARGIN', new_y='NEXT')

    pdf.ln(5)

    # Clinical indicators table
    pdf.set_font('Vietnamese', 'B', 14)
    pdf.cell(0, 10, 'CÁC CHỈ SỐ LÂM SÀNG', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    # Table header
    pdf.set_fill_color(0, 128, 128)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Vietnamese', 'B', 10)
    col_widths = [60, 40, 45, 45]
    headers = ['Chỉ số', 'Giá trị', 'Đơn vị', 'Ngưỡng hiển thị']
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align='C')
    pdf.ln()

    # Table data
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Vietnamese', '', 10)

    indicators = [
        ('SOFA', prediction['sofa'], 'điểm', '0 - 24 (ngữ cảnh)'),
        ('MAP', prediction['map_value'], 'mmHg', '70 - 100'),
        ('PaO2/FiO2', prediction['pao2_fio2'], '', '300 - 500'),
        ('Bilirubin', prediction['bilirubin'], 'mg/dL', '0.1 - 1.2'),
        ('Creatinine', prediction['creatinine'], 'mg/dL', '0.6 - 1.2'),
        ('Tiểu cầu', prediction['platelet'], 'x10^9/L', '150 - 400'),
        ('GCS', prediction['gcs'], 'điểm', '13 - 15'),
    ]

    for i, (name, val, unit, normal) in enumerate(indicators):
        if i % 2 == 0:
            pdf.set_fill_color(240, 248, 248)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.cell(col_widths[0], 7, name, border=1, fill=True, align='L')
        pdf.cell(col_widths[1], 7, str(val), border=1, fill=True, align='C')
        pdf.cell(col_widths[2], 7, unit, border=1, fill=True, align='C')
        pdf.cell(col_widths[3], 7, normal, border=1, fill=True, align='C')
        pdf.ln()

    pdf.ln(8)

    # Research assessment section
    pdf.set_font('Vietnamese', 'B', 14)
    pdf.cell(0, 10, 'TRẠNG THÁI BẢN GHI NGHIÊN CỨU', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Vietnamese', '', 11)
    review_status = 'Đã có người dùng xác nhận đánh giá' if prediction['acknowledged_at'] else 'Cần bác sĩ đánh giá'
    pdf.cell(0, 7, f'Trạng thái quy trình: {review_status}', new_x='LMARGIN', new_y='NEXT')
    signal = describe_signal(prediction['risk_level'])
    pdf.cell(0, 7, f'Tín hiệu mô hình nghiên cứu: {signal["label"]}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f'Phiên bản mô hình: {prediction["model_version"] or "bản ghi demo cũ"}', new_x='LMARGIN', new_y='NEXT')
    if prediction['acknowledged_at']:
        pdf.cell(0, 7, f'Thời điểm xác nhận: {prediction["acknowledged_at"]}', new_x='LMARGIN', new_y='NEXT')
        if prediction['acknowledgement_note']:
            pdf.multi_cell(0, 7, f'Ghi chú đánh giá: {prediction["acknowledgement_note"]}')

        # Bản ghi đã có xác nhận điện tử nên không cần dành thêm một trang chỉ
        # để ký tay. Giữ phần lưu ý ngay sau nhận định để tránh trang trống.
        pdf.ln(2)
    else:
        # Bản ghi chưa được xác nhận vẫn có chỗ ký khi cần in ra để rà soát.
        pdf.ln(12)
        pdf.set_font('Vietnamese', '', 11)
        pdf.cell(95, 7, '', align='C')
        pdf.cell(95, 7, 'Bác sĩ phụ trách', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(20)
        pdf.cell(95, 7, '', align='C')
        pdf.cell(95, 7, prediction['doctor_name'] or '_______________', align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(8)

    # Disclaimer
    pdf.set_font('Vietnamese', 'I', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.multi_cell(0, 4,
        'Lưu ý: Đây là bản ghi nghiên cứu/demo, không phải chẩn đoán, xác suất lâm sàng '
        'hay khuyến nghị điều trị. Quyết định lâm sàng cuối cùng phải do bác sĩ chuyên khoa '
        'thực hiện theo quy trình của cơ sở y tế.')

    # Output to bytes
    pdf_bytes = pdf.output()

    patient_code = prediction['patient_code'] or 'unknown'
    filename = f'ICU_Report_{patient_code}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
