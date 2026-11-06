"""Binary fixtures built in code, so no binary file is committed."""

MP3_FRAME_BYTES = 417  # MPEG-1 Layer III, 128 kbps, 44.1 kHz, no padding
MP3_FRAMES = 40  # about one second of silence


def make_pdf(lines: list[str]) -> bytes:
    """Return a valid one-page PDF whose text layer holds `lines`."""

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    body = " ".join(f"({escape(line)}) Tj T*" for line in lines)
    stream = f"BT /F1 12 Tf 14 TL 72 720 Td {body} ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(out)


def make_mp3() -> bytes:
    """Return about one second of silent MP3 (frames with an empty payload)."""
    frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(MP3_FRAME_BYTES - 4)
    return frame * MP3_FRAMES
