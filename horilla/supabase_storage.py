"""
Supabase Storage backend for Rahul HRMS.
Provides secure media and document storage in Supabase Storage buckets.
"""

import io
import os
import mimetypes
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.conf import settings


@deconstructible
class SupabaseStorage(Storage):
    """
    Custom Django Storage backend that integrates with Supabase Storage.
    Supports secure private bucket storage and signed URL generation.
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
        self.supabase_url = supabase_url or getattr(settings, "SUPABASE_URL", "")
        self.supabase_key = (
            getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
            or getattr(settings, "SUPABASE_SECRET_KEY", "")
            or getattr(settings, "SUPABASE_ANON_KEY", "")
            or getattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
        )
        self.signed_url_expires_in = signed_url_expires_in
        self.location = location
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.supabase_url or not self.supabase_key:
                return None
            try:
                from supabase import create_client

                self._client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to initialize Supabase client: {e}")
                return None
        return self._client

    def _get_storage_path(self, name):
        clean_name = str(name).lstrip("/")
        if self.location and not clean_name.startswith(self.location):
            return f"{self.location}/{clean_name}".lstrip("/")
        return clean_name

    def _open(self, name, mode="rb"):
        if not self.client:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            if os.path.exists(local_path):
                return open(local_path, mode)
            raise IOError(f"File {name} not found.")
        path = self._get_storage_path(name)
        try:
            res = self.client.storage.from_(self.bucket_name).download(path)
            return ContentFile(res)
        except Exception as e:
            raise IOError(f"Error opening file {name} from Supabase: {e}")

    def _save(self, name, content):
        path = self._get_storage_path(name)
        if not self.client:
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

        file_options = {
            "content-type": mime_type,
            "upsert": "true",
        }

        try:
            self.client.storage.from_(self.bucket_name).upload(
                file=file_bytes, path=path, file_options=file_options
            )
        except Exception:
            try:
                self.client.storage.from_(self.bucket_name).update(
                    file=file_bytes, path=path, file_options=file_options
                )
            except Exception as update_err:
                import logging
                logging.getLogger(__name__).warning(f"Supabase upload notice for {path}: {update_err}")

        return name

    def delete(self, name):
        if not self.client:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            if os.path.exists(local_path):
                os.remove(local_path)
            return
        path = self._get_storage_path(name)
        try:
            self.client.storage.from_(self.bucket_name).remove([path])
        except Exception:
            pass

    def exists(self, name):
        if not self.client:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            return os.path.exists(local_path)
        path = self._get_storage_path(name)
        folder = os.path.dirname(path)
        filename = os.path.basename(path)
        try:
            files = self.client.storage.from_(self.bucket_name).list(folder)
            return any(f.get("name") == filename for f in files)
        except Exception:
            return False

    def url(self, name):
        if not name:
            return ""
        if not self.client:
            return f"{settings.MEDIA_URL.rstrip('/')}/{str(name).lstrip('/')}"
        path = self._get_storage_path(name)
        try:
            res = self.client.storage.from_(self.bucket_name).create_signed_url(
                path, self.signed_url_expires_in
            )
            if isinstance(res, dict):
                return res.get("signedURL") or res.get("signedUrl") or ""
            return str(res)
        except Exception:
            return f"{settings.MEDIA_URL.rstrip('/')}/{str(name).lstrip('/')}"

    def size(self, name):
        if not self.client:
            local_path = os.path.join(settings.MEDIA_ROOT, name)
            return os.path.getsize(local_path) if os.path.exists(local_path) else 0
        path = self._get_storage_path(name)
        folder = os.path.dirname(path)
        filename = os.path.basename(path)
        try:
            files = self.client.storage.from_(self.bucket_name).list(folder)
            for f in files:
                if f.get("name") == filename:
                    metadata = f.get("metadata", {})
                    return metadata.get("size", 0)
        except Exception:
            pass
        return 0
