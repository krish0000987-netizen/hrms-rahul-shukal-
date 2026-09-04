"""
Supabase Storage backend for Rahul HRMS.
Provides high-performance, lightweight secure media and document storage in Supabase Storage.
"""

import io
import os
import mimetypes
import logging
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.conf import settings

logger = logging.getLogger(__name__)


@deconstructible
class SupabaseStorage(Storage):
    """
    Custom Django Storage backend that integrates with Supabase Storage via REST API.
    Supports secure private bucket storage, upserts, and signed URL generation.
    """

    def __init__(
        self,
        bucket_name=None,
        supabase_url=None,
        supabase_key=None,
        signed_url_expires_in=3600,
        location="",
    ):
        self.bucket_name = bucket_name or getattr(
            settings, "SUPABASE_STORAGE_BUCKET", "rahul-hrms"
        )
        self.supabase_url = (supabase_url or getattr(settings, "SUPABASE_URL", "")).rstrip("/")
        self.supabase_key = (
            getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
            or getattr(settings, "SUPABASE_SECRET_KEY", "")
            or getattr(settings, "SUPABASE_ANON_KEY", "")
            or getattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
        )
        self.signed_url_expires_in = signed_url_expires_in
        self.location = location

    @property
    def is_configured(self):
        return bool(self.supabase_url and self.supabase_key and self.bucket_name)

    def _get_headers(self, content_type=None):
        headers = {
            "Authorization": f"Bearer {self.supabase_key}",
            "apikey": self.supabase_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _get_storage_path(self, name):
        clean_name = str(name).lstrip("/")
        if self.location and not clean_name.startswith(self.location):
            return f"{self.location}/{clean_name}".lstrip("/")
        return clean_name

    def _open(self, name, mode="rb"):
        if not self.is_configured:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            if os.path.exists(local_path):
                return open(local_path, mode)
            raise IOError(f"File {name} not found.")
        
        path = self._get_storage_path(name)
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{path}"
        try:
            resp = requests.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                return ContentFile(resp.content)
            raise IOError(f"Supabase download returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            raise IOError(f"Error opening file {name} from Supabase: {e}")

    def _save(self, name, content):
        path = self._get_storage_path(name)
        if not self.is_configured:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                if hasattr(content, "read"):
                    f.write(content.read())
                else:
                    f.write(content)
            return name

        content.seek(0)
        file_bytes = content.read()
        mime_type, _ = mimetypes.guess_type(str(name))
        mime_type = mime_type or "application/octet-stream"

        headers = self._get_headers(mime_type)
        headers["x-upsert"] = "true"

        url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{path}"
        try:
            resp = requests.post(url, headers=headers, data=file_bytes)
            if resp.status_code not in (200, 201):
                # Try PUT if POST fails on existing object
                resp = requests.put(url, headers=headers, data=file_bytes)
        except Exception as e:
            logger.warning(f"Supabase storage upload notice for {path}: {e}")

        return name

    def delete(self, name):
        if not self.is_configured:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            if os.path.exists(local_path):
                os.remove(local_path)
            return

        path = self._get_storage_path(name)
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}"
        try:
            requests.delete(
                url,
                headers=self._get_headers("application/json"),
                json={"prefixes": [path]},
            )
        except Exception:
            pass

    def exists(self, name):
        if not self.is_configured:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            return os.path.exists(local_path)

        path = self._get_storage_path(name)
        folder = os.path.dirname(path)
        filename = os.path.basename(path)
        url = f"{self.supabase_url}/storage/v1/object/list/{self.bucket_name}"
        try:
            resp = requests.post(
                url,
                headers=self._get_headers("application/json"),
                json={"prefix": folder, "limit": 100},
            )
            if resp.status_code == 200:
                files = resp.json()
                return any(f.get("name") == filename for f in files)
        except Exception:
            pass
        return False

    def url(self, name):
        if not name:
            return ""
        if not self.is_configured:
            return f"{settings.MEDIA_URL.rstrip('/')}/{str(name).lstrip('/')}"

        path = self._get_storage_path(name)
        url = f"{self.supabase_url}/storage/v1/object/sign/{self.bucket_name}/{path}"
        try:
            resp = requests.post(
                url,
                headers=self._get_headers("application/json"),
                json={"expiresIn": self.signed_url_expires_in},
            )
            if resp.status_code == 200:
                data = resp.json()
                signed = data.get("signedURL") or data.get("signedUrl")
                if signed:
                    if signed.startswith("http"):
                        return signed
                    return f"{self.supabase_url}/storage/v1{signed}"
            return f"{settings.MEDIA_URL.rstrip('/')}/{str(name).lstrip('/')}"
        except Exception:
            return f"{settings.MEDIA_URL.rstrip('/')}/{str(name).lstrip('/')}"

    def size(self, name):
        if not self.is_configured:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            return os.path.getsize(local_path) if os.path.exists(local_path) else 0
        path = self._get_storage_path(name)
        folder = os.path.dirname(path)
        filename = os.path.basename(path)
        url = f"{self.supabase_url}/storage/v1/object/list/{self.bucket_name}"
        try:
            resp = requests.post(
                url,
                headers=self._get_headers("application/json"),
                json={"prefix": folder, "limit": 100},
            )
            if resp.status_code == 200:
                files = resp.json()
                for f in files:
                    if f.get("name") == filename:
                        metadata = f.get("metadata", {})
                        return metadata.get("size", 0)
        except Exception:
            pass
        return 0
