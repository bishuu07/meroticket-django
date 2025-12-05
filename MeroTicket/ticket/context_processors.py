# core/context_processors.py
from .models import SiteSettings

def footer_settings(request):
    try:
        settings = SiteSettings.objects.first()
    except:
        settings = None

    return {
        'footer_settings': settings
    }