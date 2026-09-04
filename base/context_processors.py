"""
context_processor.py

This module is used to register context processor`
"""

import time
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.urls import path
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext_lazy as _

from base.models import (
    Company,
    CompanyLanguageSetting,
    DefaultExportPermission,
    TrackLateComeEarlyOut,
)
from base.urls import urlpatterns
from employee.models import EmployeeGeneralSetting, ProfileEditFeature
from horilla.decorators import hx_request_required, login_required
from horilla.http.response import HorillaRedirect
from horilla.methods import get_horilla_model_class

_CP_CACHE = {}

def _get_cached_setting(key, fetcher, ttl=300):
    now = time.time()
    entry = _CP_CACHE.get(key)
    if entry is not None and (now - entry["time"]) < ttl:
        return entry["val"]
    val = fetcher()
    _CP_CACHE[key] = {"val": val, "time": now}
    return val


class AllCompany:
    """
    Dummy class for the "all companies" switcher entry.
    """

    class Urls:
        url = "https://ui-avatars.com/api/?name=All+Company&background=random"

    company = "All Company"
    icon = Urls()
    text = "All companies"
    id = None


class AllMyCompanies(AllCompany):
    """Non-superuser combined view over assignment companies only."""

    class Urls:
        url = "https://ui-avatars.com/api/?name=All+My+Companies&background=random"

    company = "All my companies"
    icon = Urls()
    text = "All my companies"


def get_companies(request):
    """
    Companies for the header switcher.

    With COMPANY_SCOPED_PERMISSIONS on, non-superusers see assignment companies
    plus their work-info company. "All my companies" appears when they hold
    roles in 2+ companies (combined view over those assignment IDs only).
    """
    from base.auth_backends import (
        company_scoped_active,
        get_allowed_company_ids,
        get_assigned_company_ids,
    )

    scoped = (
        company_scoped_active()
        and request.user.is_authenticated
        and not request.user.is_superuser
    )
    allowed_ids = get_allowed_company_ids(request.user) if scoped else None
    assigned_ids = get_assigned_company_ids(request.user) if scoped else None
    if not scoped:
        raw_list = _get_cached_setting("raw_companies_list", lambda: list(
            [c.id, c.company, c.icon.url] for c in Company.objects.all()
        ), 300)
        companies = [[r[0], r[1], r[2], False] for r in raw_list]
        companies = [
            [
                "all",
                "All Company",
                "https://ui-avatars.com/api/?name=All+Company&background=random",
                False,
            ],
        ] + companies
    else:
        company_qs = Company.objects.all()
        if scoped:
            company_qs = company_qs.filter(id__in=allowed_ids or [])
        companies = list(
            [company.id, company.company, company.icon.url, False] for company in company_qs
        )
        if assigned_ids and len(assigned_ids) >= 2:
            companies = [
                [
                    "all",
                    "All my companies",
                    "https://ui-avatars.com/api/?name=All+My+Companies&background=random",
                    False,
                ],
            ] + companies
    selected_company = request.session.get("selected_company")
    company_selected = False
    if selected_company and selected_company == "all":
        if companies and companies[0][0] == "all":
            companies[0][3] = True
            company_selected = True
    else:
        for company in companies:
            if str(company[0]) == selected_company:
                company[3] = True
                company_selected = True

    if not request.user.is_authenticated:
        show_switcher = False
    elif scoped:
        show_switcher = len(companies) > 1
    else:
        show_switcher = request.user.has_perm("base.change_company")
    return {
        "all_companies": companies,
        "company_selected": company_selected,
        "show_company_switcher": show_switcher,
    }


@login_required
@hx_request_required
def update_selected_company(request):
    """
    This method is used to update the selected company on the session
    """
    from base.auth_backends import (
        company_scoped_active,
        get_allowed_company_ids,
        get_assigned_company_ids,
    )

    company_id = request.GET.get("company_id")
    next_url = request.META.get("HTTP_REFERER") or "/"

    if company_scoped_active() and not request.user.is_superuser:
        allowed = get_allowed_company_ids(request.user)
        assigned = get_assigned_company_ids(request.user)
        if company_id == "all":
            # Combined view over assignment companies only (need 2+ roles)
            target_allowed = len(assigned) >= 2
        else:
            try:
                target_allowed = int(company_id) in allowed
            except (TypeError, ValueError):
                target_allowed = False
        if not target_allowed:
            messages.error(request, _("You do not have access to that company."))
            return HorillaRedirect(request, redirect_to=next_url)
    elif not request.user.has_perm("base.change_company"):
        messages.error(request, _("You do not have permission to switch the company."))
        return HorillaRedirect(request, redirect_to=next_url)
    user = request.user.employee_get
    user_company = getattr(
        getattr(user, "employee_work_info", None), "company_id", None
    )
    request.session["selected_company"] = company_id
    request.session.pop("hlv_selected_ids", None)
    request.session.pop("prev_path", None)
    scoped_all = (
        company_id == "all"
        and company_scoped_active()
        and not request.user.is_superuser
    )
    company = (
        AllMyCompanies()
        if scoped_all
        else (
            AllCompany()
            if company_id == "all"
            else (
                Company.objects.filter(id=company_id).first()
                if Company.objects.filter(id=company_id).first()
                else AllCompany()
            )
        )
    )

    if company_id == "all":
        text = "All my companies" if scoped_all else "All companies"
    elif company_id == user_company:
        text = "My Company"
    else:
        text = "Other Company"

    company = {
        "company": company.company,
        "icon": company.icon.url,
        "text": text,
        "id": company.id,
    }
    request.session["selected_company_instance"] = company
    return HorillaRedirect(request, redirect_to=next_url)


urlpatterns.append(
    path(
        "update-selected-company/",
        update_selected_company,
        name="update-selected-company",
    )
)


def white_labelling_company(request):
    white_labelling = getattr(settings, "WHITE_LABELLING", False)
    if white_labelling:
        hq = Company.objects.filter(hq=True).last()
        try:
            company = (
                request.user.employee_get.get_company()
                if request.user.employee_get.get_company()
                else hq
            )
        except:
            company = hq

        return {
            "white_label_company_name": company.company if company else getattr(settings, "APP_NAME", "Rahul HRMS"),
            "white_label_company": company,
            "app_name": getattr(settings, "APP_NAME", "Rahul HRMS"),
            "app_subtitle": getattr(settings, "APP_SUBTITLE", "Human Resource Management System"),
        }
    else:
        return {
            "white_label_company_name": getattr(settings, "APP_NAME", "Rahul HRMS"),
            "white_label_company": None,
            "app_name": getattr(settings, "APP_NAME", "Rahul HRMS"),
            "app_subtitle": getattr(settings, "APP_SUBTITLE", "Human Resource Management System"),
        }


def doc_base_url(request):
    """
    Base domain for in-app help/doc links. Templates build the full link as
    "{{ DOC_BASE_URL }}<path>" so only this one setting needs to change for
    white-labelled deployments.
    """
    return {
        "DOC_BASE_URL": getattr(settings, "DOC_BASE_URL", "#"),
        "APP_NAME": getattr(settings, "APP_NAME", "Rahul HRMS"),
        "APP_SUBTITLE": getattr(settings, "APP_SUBTITLE", "Human Resource Management System"),
    }


def resignation_request_enabled(request):
    """
    Check weather resignation_request enabled of not in offboarding
    """
    selected_company = request.session.get("selected_company")
    def _fetch():
        if not apps.is_installed("offboarding"):
            return False
        OffboardingGeneralSetting = get_horilla_model_class(
            app_label="offboarding", model="offboardinggeneralsetting"
        )
        if selected_company and selected_company != "all":
            first = OffboardingGeneralSetting.objects.filter(
                company_id=selected_company
            ).first()
        else:
            first = OffboardingGeneralSetting.objects.first()
        return bool(first and first.resignation_request)

    return {"enabled_resignation_request": _get_cached_setting(f"resignation_{selected_company}", _fetch, 300)}


def timerunner_enabled(request):
    """
    Whether Time Runner (at-work tracker) is enabled for the selected company.
    Prefers the company-specific AttendanceGeneralSetting, then the global
    (company_id=None) row, then defaults to enabled.
    """
    selected_company = request.session.get("selected_company")
    def _fetch():
        if not apps.is_installed("attendance"):
            return True
        AttendanceGeneralSetting = get_horilla_model_class(
            app_label="attendance", model="attendancegeneralsetting"
        )
        if selected_company and selected_company != "all":
            company = Company.objects.filter(id=selected_company).first()
        else:
            company = None
        setting = AttendanceGeneralSetting.objects.filter(company_id=company).first()
        if not setting and company is not None:
            setting = AttendanceGeneralSetting.objects.filter(company_id=None).first()
        if setting:
            return bool(setting.time_runner)
        return True

    return {"enabled_timerunner": _get_cached_setting(f"timerunner_{selected_company}", _fetch, 300)}


def intial_notice_period(request):
    """
    Check weather resignation_request enabled of not in offboarding
    """
    selected_company = request.session.get("selected_company")
    def _fetch():
        if not apps.is_installed("payroll"):
            return 30
        PayrollGeneralSetting = get_horilla_model_class(
            app_label="payroll", model="payrollgeneralsetting"
        )
        if selected_company and selected_company != "all":
            first = PayrollGeneralSetting.objects.filter(
                company_id=selected_company
            ).first()
            if not first:
                first = PayrollGeneralSetting.objects.filter(company_id=None).first()
        else:
            first = PayrollGeneralSetting.objects.first()
        if first:
            return first.notice_period
        return 30

    return {"get_initial_notice_period": _get_cached_setting(f"notice_period_{selected_company}", _fetch, 300)}


def check_candidate_recruitment_setting(request):
    """
    This method is used to resolve the RecruitmentGeneralSetting for the current request
    """
    if hasattr(request, "_recruitment_general_setting_cache"):
        return request._recruitment_general_setting_cache

    RecruitmentGeneralSetting = get_horilla_model_class(
        app_label="recruitment", model="recruitmentgeneralsetting"
    )
    candidate_id = request.session.get("candidate_id")
    setting = None
    # Anonymous candidate sessions never carry selected_company, so resolve via
    # the candidate's own company instead of the company_id IS NULL fallback.
    if not request.user.is_authenticated and candidate_id:
        Candidate = get_horilla_model_class(app_label="recruitment", model="candidate")
        candidate = Candidate.objects.filter(pk=candidate_id).first()
        company_id = getattr(
            getattr(candidate, "recruitment_id", None), "company_id_id", None
        )
        if company_id:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id_id=company_id
            ).first()
        if not setting:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id__isnull=True
            ).first()
    else:
        selected_company = request.session.get("selected_company")
        if selected_company and selected_company != "all":
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id_id=selected_company
            ).first()
        else:
            setting = RecruitmentGeneralSetting.objects.filter(
                company_id__isnull=True
            ).first()

    request._recruitment_general_setting_cache = setting
    return setting


def check_candidate_self_tracking(request):
    """
    This method is used to get the candidate self tracking is enabled or not
    """

    def _resolve():
        if not apps.is_installed("recruitment"):
            return False
        first = check_candidate_recruitment_setting(request)
        return bool(first and first.candidate_self_tracking)

    return {"check_candidate_self_tracking": SimpleLazyObject(_resolve)}


def check_candidate_self_tracking_rating(request):
    """
    This method is used to check enabled/disabled of rating option
    """

    def _resolve():
        if not apps.is_installed("recruitment"):
            return False
        first = check_candidate_recruitment_setting(request)
        return bool(first and first.show_overall_rating)

    return {"check_candidate_self_tracking_rating": SimpleLazyObject(_resolve)}


def get_initial_prefix(request):
    """
    This method is used to get the initial prefix
    """
    def _fetch():
        settings = EmployeeGeneralSetting.objects.first()
        instance_id = None
        prefix = "PEP"
        if settings:
            instance_id = settings.id
            prefix = settings.badge_id_prefix
        return {"get_initial_prefix": prefix, "prefix_instance_id": instance_id}
    return _get_cached_setting("initial_prefix", _fetch, 300)


def biometric_app_exists(request):
    from django.conf import settings

    biometric_app_exists = "biometric" in settings.INSTALLED_APPS
    return {"biometric_app_exists": biometric_app_exists}


def enable_late_come_early_out_tracking(request):
    selected_company = request.session.get("selected_company") if request else None
    def _fetch():
        if not selected_company or selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()
        tracking = TrackLateComeEarlyOut.objects.filter(company_id=company).first()
        return tracking.is_enable if tracking else True

    enable = _get_cached_setting(f"late_come_{selected_company}", _fetch, 300)
    return {"tracking": enable, "late_come_early_out_tracking": enable}


def enable_profile_edit(request):
    from accessibility.accessibility import ACCESSBILITY_FEATURE

    def _fetch():
        profile_edit = ProfileEditFeature.objects.filter().first()
        return bool(profile_edit and profile_edit.is_enabled)

    enable = _get_cached_setting("profile_edit", _fetch, 300)
    if enable:
        if not any(item[0] == "profile_edit" for item in ACCESSBILITY_FEATURE):
            ACCESSBILITY_FEATURE.append(("profile_edit", _("Profile Edit Access")))

    return {"profile_edit_enabled": enable}


def export_access_enabled(request):
    """
    Exposes whether the "Default Export Access" setting is enabled for
    the user's current company, so templates can decide whether to show
    export buttons/menu options without requiring per-view context.
    Superusers always see export actions regardless of the setting.
    """
    if request.user.is_superuser:
        return {"export_access_enabled": True}

    selected_company = request.session.get("selected_company")
    def _fetch():
        if not selected_company or selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()
        setting = DefaultExportPermission.objects.filter(company_id=company).first()
        return setting is None or bool(setting.is_enabled)

    enabled = _get_cached_setting(f"export_access_{selected_company}", _fetch, 300)
    return {"export_access_enabled": enabled}


def navbar_languages(request):
    """
    Exposes the list of languages available in the navbar language
    switcher for the user's current company. The switcher is only shown
    when a company has explicitly enabled more than one language; with
    zero or one language enabled, there is nothing to switch to, so it
    stays hidden.
    """
    selected_company = request.session.get("selected_company")
    def _fetch():
        if not selected_company or selected_company == "all":
            company = None
        else:
            company = Company.objects.filter(id=selected_company).first()

        setting = CompanyLanguageSetting.objects.filter(company_id=company).first()
        if setting and setting.enabled_languages:
            enabled_codes = set(setting.enabled_languages)
            languages = [
                language for language in settings.LANGUAGES if language[0] in enabled_codes
            ]
            if len(languages) > 1:
                return {"navbar_languages": languages, "show_language_switcher": True}

        return {"navbar_languages": [], "show_language_switcher": False}

    return _get_cached_setting(f"navbar_languages_{selected_company}", _fetch, 300)
