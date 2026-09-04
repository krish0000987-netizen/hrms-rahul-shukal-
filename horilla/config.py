"""
horilla/config.py

Horilla app configurations
"""

import importlib
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth.context_processors import PermWrapper

logger = logging.getLogger(__name__)


def get_apps_in_base_dir():
    return settings.SIDEBARS


def import_method(accessibility):
    module_path, method_name = accessibility.rsplit(".", 1)
    module = __import__(module_path, fromlist=[method_name])
    accessibility_method = getattr(module, method_name)
    return accessibility_method


import time

ALL_MENUS = {}
_MENUS_CACHE = {}


def sidebar(request):
    base_dir_apps = get_apps_in_base_dir()

    if not request.user.is_anonymous:
        request.MENUS = []
        MENUS = request.MENUS
        is_superuser = getattr(request.user, "is_superuser", False)

        for app in base_dir_apps:
            if apps.is_installed(app):
                try:
                    sidebar_mod = importlib.import_module(app + ".sidebar")
                except Exception as e:
                    logger.error(e)
                    continue

                if sidebar_mod:
                    accessibility = None
                    if not is_superuser and getattr(sidebar_mod, "ACCESSIBILITY", None):
                        accessibility = import_method(sidebar_mod.ACCESSIBILITY)

                    if hasattr(sidebar_mod, "MENU") and (
                        is_superuser
                        or not accessibility
                        or accessibility(
                            request,
                            sidebar_mod.MENU,
                            PermWrapper(request.user),
                        )
                    ):
                        MENU = {}
                        MENU["menu"] = sidebar_mod.MENU
                        MENU["app"] = app
                        MENU["img_src"] = sidebar_mod.IMG_SRC
                        MENU["submenu"] = []
                        MENUS.append(MENU)
                        for submenu in sidebar_mod.SUBMENUS:
                            redirect: str = submenu["redirect"]
                            redirect = redirect.split("?")
                            submenu["redirect"] = redirect[0]

                            if is_superuser:
                                MENU["submenu"].append(submenu)
                                continue

                            accessibility = None
                            if submenu.get("accessibility"):
                                accessibility = import_method(submenu["accessibility"])

                            if not accessibility or accessibility(
                                request,
                                submenu,
                                PermWrapper(request.user),
                            ):
                                MENU["submenu"].append(submenu)
        session = getattr(request, "session", None)
        session_key = getattr(session, "session_key", None) if session else None
        if session_key:
            ALL_MENUS[session_key] = MENUS


def get_MENUS(request):
    # Rebuild at most once per process / user — accessibility checks hit the DB.
    cached = getattr(request, "_horilla_menus", None)
    if cached is not None:
        return {"sidebar": cached}
    user = getattr(request, "user", None)
    if not user or getattr(user, "is_anonymous", True):
        return {"sidebar": []}

    user_id = getattr(user, "id", None)
    session = getattr(request, "session", None)
    session_key = getattr(session, "session_key", None) if session else None
    cache_key = f"user_{user_id}" if user_id else (session_key or "anon")

    now = time.time()
    if cache_key in _MENUS_CACHE:
        ts, cached_menus = _MENUS_CACHE[cache_key]
        if (now - ts) < 300:  # 5 min cache
            request._horilla_menus = cached_menus
            return {"sidebar": cached_menus}

    sidebar(request)
    menus = getattr(request, "MENUS", [])
    if not menus and session_key and session_key in ALL_MENUS:
        menus = ALL_MENUS[session_key]
    _MENUS_CACHE[cache_key] = (now, menus)
    ALL_MENUS[cache_key] = menus
    request._horilla_menus = menus
    return {"sidebar": menus}


def load_ldap_settings():
    """
    Fetch LDAP settings dynamically from the database after Django is ready.
    """
    try:
        from django.db import connection

        from horilla_ldap.models import LDAPSettings

        # Ensure DB is ready before querying
        if not connection.introspection.table_names():
            print("⚠️ Database is empty. Using default LDAP settings.")
            return settings.DEFAULT_LDAP_CONFIG

        ldap_config = LDAPSettings.objects.first()
        if ldap_config:
            return {
                "LDAP_SERVER": ldap_config.ldap_server,
                "BIND_DN": ldap_config.bind_dn,
                "BIND_PASSWORD": ldap_config.bind_password,
                "BASE_DN": ldap_config.base_dn,
            }
    except Exception as e:
        print(f"⚠️ Warning: Could not load LDAP settings ({e})")
        return settings.DEFAULT_LDAP_CONFIG  # Return default on error

    return settings.DEFAULT_LDAP_CONFIG  # Fallback in case of an issue
