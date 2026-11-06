"""Generate icon.ico (and icon.png preview) for Text Typer.

Needs Pillow:  py -m pip install pillow
Run:           py make_icon.py
"""

from PIL import Image, ImageDraw

SS = 4  # supersampling factor for smooth edges
SIZE = 256
S = SIZE * SS

TOP = (59, 130, 246)  # blue-500
BOTTOM = (30, 64, 175)  # blue-800
TEXT = (255, 255, 255)
CARET = (251, 191, 36)  # amber-400


def px(v):
    return int(v * SS)


def make() -> Image.Image:
    # Diagonal gradient background
    grad = Image.new("RGB", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        color = tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        gd.line([(0, y), (S, y)], fill=color)

    # Rounded-square mask
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([px(8), px(8), px(248), px(248)], radius=px(56), fill=255)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # "Typed text" lines
    h = 26
    lines = [(52, 64, 204), (52, 115, 176), (52, 166, 132)]  # (x, y, end_x)
    for x, y, x2 in lines:
        d.rounded_rectangle([px(x), px(y), px(x2), px(y + h)], radius=px(h / 2), fill=TEXT)

    # Text cursor after the last line
    cx = 150
    d.rounded_rectangle([px(cx), px(152), px(cx + 16), px(206)], radius=px(8), fill=CARET)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


if __name__ == "__main__":
    icon = make()
    icon.save("icon.png")
    icon.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Wrote icon.ico and icon.png")
