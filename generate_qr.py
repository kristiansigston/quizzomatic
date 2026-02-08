import socket
import os
try:
    import qrcode
except Exception:
    qrcode = None


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def generate_qr():
    if qrcode is None:
        print("QR generation skipped: qrcode dependency is missing.")
        return
    ip = get_ip()
    url = f"http://{ip}:9145"
    print(f"Generating QR code for: {url}")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    output_path = os.path.join("static", "qr.png")
    img.save(output_path)
    print(f"QR code saved to {output_path}")


if __name__ == "__main__":
    generate_qr()
