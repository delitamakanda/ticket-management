import qrcode
import io


def generate_qrcode(uri):
    qr = qrcode.make(uri)
    buffer = io.BytesIO()
    qr.save(buffer, 'PNG')
    buffer.seek(0)
    return buffer