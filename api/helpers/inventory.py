import time
import random
import os
import io
from flask import  json
from services.image.upload import upload



def upload_variation_img(variations,files):


    variation_images = {}

    for key in files:
        if not key.startswith("images["):
            continue

        try:
            index = int(key.replace("images[", "").replace("]", ""))
        except ValueError:
            continue

        variation_images.setdefault(index, [])

        for file in files.getlist(key):

            if not file or not file.filename:
                continue

            if file.filename.startswith("http"):
                continue

            raw = file.read()
            upload_buf = io.BytesIO(raw)

            ext = os.path.splitext(file.filename)[1]
            new_filename = f"{int(time.time())}_{random.randint(1000,9999)}{ext}"

            inv_url = upload(
                file=upload_buf,
                filename=new_filename,
                content_type=file.content_type,
                subfolder="variation"
            )

            variation_images[index].append(inv_url)


    for i, variation in enumerate(variations):

        existing_images = variation.get("image", [])

        # normalize
        if isinstance(existing_images, str):
            try:
                existing_images = json.loads(existing_images)
            except json.JSONDecodeError:
                existing_images = []

        if i in variation_images and variation_images[i]:
            variation["image"] = json.dumps(variation_images[i])
        else:
            variation["image"] = json.dumps(existing_images)

    return variations

