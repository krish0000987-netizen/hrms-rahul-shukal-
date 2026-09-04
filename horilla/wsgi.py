"""
WSGI config for horilla project.
"""

import os
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "horilla.settings")

try:
    from django.core.wsgi import get_wsgi_application
    django_application = get_wsgi_application()
except Exception as exc:
    traceback.print_exc(file=sys.stderr)
    django_application = None
    _init_error = traceback.format_exc()
else:
    _init_error = None


def application(environ, start_response):
    if _init_error:
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"Django Init Error:\n{_init_error}".encode("utf-8")]
    try:
        return django_application(environ, start_response)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        err_msg = traceback.format_exc()
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"WSGI Handler Error:\n{err_msg}".encode("utf-8")]


app = application
