"""
context_processor.py

This module is used to register context processor`
"""

from employee.models import Employee
from payroll.models import tax_models as models
from payroll.models.models import Deduction


_PAYROLL_SETTINGS_CACHE = {"obj": None, "cached_at": 0}


def default_currency(request):
    """
    This method will return the currency
    """
    import time
    now = time.time()
    ps = _PAYROLL_SETTINGS_CACHE["obj"]
    if ps is None or now - _PAYROLL_SETTINGS_CACHE["cached_at"] > 300:
        ps = models.PayrollSettings.objects.first()
        if ps is None:
            ps = models.PayrollSettings()
            ps.currency_symbol = "$"
            ps.company_id = getattr(request, "selected_company_instance", None)
            try:
                ps.save()
            except Exception:
                pass
        _PAYROLL_SETTINGS_CACHE["obj"] = ps
        _PAYROLL_SETTINGS_CACHE["cached_at"] = now

    symbol = getattr(ps, "currency_symbol", "$")
    position = getattr(ps, "position", "prefix")
    return {
        "currency": request.session.get("currency", symbol),
        "position": request.session.get("position", position),
    }


def host(request):
    """
    This method will return the host
    """
    protocol = "https" if request.is_secure() else "http"
    return {"host": request.get_host(), "protocol": protocol}


def get_deductions(request):
    """
    This method used to return the deduction
    """
    deductions = Deduction.objects.filter(
        only_show_under_employee=False, employer_rate__gt=0
    )
    return {"get_deductions": deductions}


def get_active_employees(request):
    """
    This method used to return the deduction
    """
    employees = Employee.objects.filter(
        is_active=True, contract_set__isnull=False, payslip__isnull=False
    ).distinct()
    return {"get_active_employees": employees}
