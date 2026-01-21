from PIL import Image

def fit_subject_center(img, canvas=1080, subject_max=700):
    img = img.convert("RGBA")

    w, h = img.size
    scale = subject_max / max(w, h)

    if scale < 1:
        img = img.resize(
            (int(w*scale), int(h*scale)),
            Image.LANCZOS
        )

    # TRANSPARENT canvas
    square = Image.new("RGBA", (canvas, canvas), (0,0,0,0))

    x = (canvas - img.width)//2
    y = (canvas - img.height)//2

    # IMPORTANT: mask = img
    square.paste(img, (x, y), img)

    return square
