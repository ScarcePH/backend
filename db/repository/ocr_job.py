from task.ocr import enqueue_ocr
from db.models.ocrjob import OCRJob
from services.image.upload import upload
import io
import time
import random
import os
from db.database import db


def ocr_job(file_bytes: bytes, filename: str, content_type: str):

    upload_buf = io.BytesIO(file_bytes)

    ext = os.path.splitext(filename)[1] or ".jpg"
    new_filename = f"{int(time.time())}_{random.randint(1000,9999)}{ext}"

    path = upload(
        file=upload_buf,
        filename=new_filename,
        content_type=content_type,
        subfolder="payment"
    )

    job = OCRJob(
        status="PENDING",
        image_path=path
    )

    db.session.add(job)
    db.session.commit()

    enqueue_ocr(str(job.id), path)

    return {
        "job_id": str(job.id),
        "path": path
    }


def wait_for_ocr(job_id, timeout=8, interval=0.5):

    deadline = time.time() + timeout

    while time.time() < deadline:
        job = OCRJob.query.get(job_id)

        if not job:
            return {"status": "FAILED"}

        if job.status == "DONE":
            return {"is_valid": job.result}


        if job.status == "FAILED":
            return {"status": "FAILED"}

        time.sleep(interval)

    return {"status": "TIMEOUT"}