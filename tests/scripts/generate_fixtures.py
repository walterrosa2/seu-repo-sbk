import os
try:
    from PIL import Image
    pillow_installed = True
except ImportError:
    pillow_installed = False

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")

def ensure_fixture_dir():
    os.makedirs(FIXTURE_DIR, exist_ok=True)

def generate_dummy_image(filename="dummy_image.png"):
    path = os.path.join(FIXTURE_DIR, filename)
    if pillow_installed:
        img = Image.new('RGB', (100, 100), color = (73, 109, 137))
        img.save(path)
        print(f"Generated {path}")
    else:
        with open(path, "w") as f:
            f.write("dummy image content")
        print(f"Generated fake image file {path}")

def generate_dummy_pdf(filename="dummy_document.pdf"):
    path = os.path.join(FIXTURE_DIR, filename)
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(path)
        c.drawString(100, 750, "Dummy PDF Content for Testing - Page 1")
        c.drawString(100, 700, "SERASA") # to match an anchor text test
        c.showPage()
        c.drawString(100, 750, "Dummy PDF Content for Testing - Page 2")
        c.showPage()
        c.save()
        print(f"Generated PDF {path}")
    except ImportError:
        with open(path, "w") as f:
            f.write("dummy pdf content")
        print(f"Generated fake PDF file {path} (install reportlab for a real pdf)")

if __name__ == "__main__":
    ensure_fixture_dir()
    generate_dummy_image("dummy_image.png")
    generate_dummy_pdf("dummy_document.pdf")
    generate_dummy_pdf("dummy_document_multipage.pdf")
