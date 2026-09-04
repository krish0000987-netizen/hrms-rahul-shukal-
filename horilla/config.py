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


ALL_MENUS = {}


def sidebar(request):

    base_dir_apps = get_apps_in_base_dir()

    if not request.user.is_anonymous:
        request.MENUS = []
        MENUS = request.MENUS

        for app in base_dir_apps:
            if apps.is_installed(app):
                try:
                    sidebar = importlib.import_module(app + ".sidebar")

                except Exception as e:
                    logger.error(e)
                    continue

                if sidebar:
                    accessibility = None
                    if getattr(sidebar, "ACCESSIBILITY", None):
                        accessibility = import_method(sidebar.ACCESSIBILITY)

                    if hasattr(sidebar, "MENU") and (
                        not accessibility
                        or accessibility(
                            request,
                            sidebar.MENU,
                            PermWrapper(request.user),
                        )
                    ):
                        MENU = {}
                        MENU["menu"] = sidebar.MENU
                        MENU["app"] = app
                        MENU["img_src"] = sidebar.IMG_SRC
                        MENU["submenu"] = []
                        MENUS.append(MENU)
                        for submenu in sidebar.SUBMENUS:

                            accessibility = None

                            if submenu.get("accessibility"):
                                accessibility = import_method(submenu["accessibility"])
                            redirect: str = submenu["redirect"]
                            redirect = redirect.split("?")
                            submenu["redirect"] = redirect[0]

                            if not accessibility or accessibility(
                                request,
                                submenu,
                                PermWrapper(request.user),
                            ):
                                MENU["submenu"].append(submenu)
        ALL_MENUS[request.session.session_key] = MENUS


def get_MENUS(request):
    # Rebuild at most once per process / user — accessibility checks hit the DB.
    cached = getattr(request, "_horilla_menus", None)
    if cached is not None:
        return {"sidebar": cached}
    user_id = getattr(getattr(request, "user", None), "id", None)
    cache_key = f"user_{user_id}" if user_id else getattr(request.session, "session_key", "anon")
    if cache_key in ALL_MENUS and ALL_MENUS[cache_key]:
        request._horilla_menus = ALL_MENUS[cache_key]
        return {"sidebar": ALL_MENUS[cache_key]}
    sidebar(request)
    session_key = getattr(request.session, "session_key", None)
    menus = ALL_MENUS.get(session_key) if session_key else request.MENUS
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
