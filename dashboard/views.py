from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.conf import settings
import os

# =============================================================================
# PAGE VIEWS (Frontend-only: renders HTML templates)
# =============================================================================

@login_required(login_url='login')
def home(request):
    """Dashboard home page"""
    return render(request, 'dashboard/home.html', {
        'active_page': 'home',
    })


@login_required(login_url='login')
def table_view(request, table_name):
    """Table viewer page"""
    return render(request, 'dashboard/table.html', {
        'active_page': 'table',
        'table_name': table_name,
    })


@login_required(login_url='login')
def schema_view(request, table_name):
    """Schema viewer page"""
    return render(request, 'dashboard/schema.html', {
        'active_page': 'schema',
        'table_name': table_name,
    })


@login_required(login_url='login')
def create_table(request):
    """Create table page"""
    return render(request, 'dashboard/create_table.html', {
        'active_page': 'create_table',
    })


@login_required(login_url='login')
def activity(request):
    """Activity logs page"""
    return render(request, 'dashboard/activity.html', {
        'active_page': 'activity',
    })


@login_required(login_url='login')
def api_keys(request):
    """API Keys management page"""
    return render(request, 'dashboard/api_keys.html', {
        'active_page': 'api_keys',
    })


def docs(request):
    """SDK Documentation page (public, no login required)"""
    docs_path = os.path.join(settings.BASE_DIR, 'docs.html')
    return FileResponse(open(docs_path, 'rb'), content_type='text/html')


def cron_handler(request):
    """Cron job endpoint for keeping the service alive or running tasks"""
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok', 'message': 'Cron job executed successfully'})

