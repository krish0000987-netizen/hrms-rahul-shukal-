"""
Global template context for the tour engine.

Exposes a lightweight flag so the base template can render the "Help / Take a
tour" launcher (and an optional "pending" dot) without each page having to
know about tours. The heavy lifting — resolving which tour/steps apply — is
done lazily by the JS controller via the ``tour-active`` API.
"""

import logging
import time

logger = logging.getLogger(__name__)

_TOURS_CACHE = {"has_published": None, "checked_at": 0}


def pending_tours_flag(request):
    """Return launcher availability + whether the user has an unfinished tour."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"tour_launcher_enabled": False, "tour_has_pending": False}

    has_pending = False
    now = time.time()
    try:
        from horilla_tour.models import Tour, TourProgress

        # Cache whether any published tours exist (valid for 5 minutes)
        if _TOURS_CACHE["has_published"] is None or now - _TOURS_CACHE["checked_at"] > 300:
            _TOURS_CACHE["has_published"] = Tour.objects.filter(is_active=True, is_published=True).exists()
            _TOURS_CACHE["checked_at"] = now

        if _TOURS_CACHE["has_published"]:
            published = Tour.objects.filter(is_active=True, is_published=True)
            done_ids = set(
                TourProgress.objects.filter(
                    user=user, status__in=["completed", "skipped"]
                ).values_list("tour_id", flat=True)
            )
            has_pending = (
                published.filter(trigger="auto_once").exclude(id__in=done_ids).exists()
            )
    except Exception as exc:  # never let the launcher break a page render
        logger.debug("pending_tours_flag skipped: %s", exc)

    return {"tour_launcher_enabled": True, "tour_has_pending": has_pending}
