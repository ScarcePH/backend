import boto3
from botocore.client import Config
import os

access_key = os.environ.get("BUCKET_ACCESS_KEY")
secret_key = os.environ.get("BUCKET_SECRET_KEY")
endpoint_url = os.environ.get("BUCKER_API_URL")
img_base_url = os.environ.get("IMAGE_BASE_URL")


s3 = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

def upload(file, filename, content_type, subfolder=None):

    key = f"{subfolder}/{filename}" if subfolder else filename

    s3.upload_fileobj(
        file,
        "scarce-images",
        key,
        ExtraArgs={
            "ContentType": content_type,
            "ACL": "public-read"
        }
    )

    return f"{img_base_url}/{key}"

