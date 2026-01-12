from django.shortcuts import render
from django.contrib.auth.decorators import login_required

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
