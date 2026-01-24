from django.urls import path
from .views import (
    TableListCreateView,
    TableDetailView,
    TableSchemaView,
    TableRowsView,
    TableRowDetailView,
    StatsView,
    ActivityView,
    TableExportView,
    TableImportView,
)
from .api_views import (
    PublicTableListView,
    PublicTableDetailView,
    PublicTableRowsView,
    PublicTableRowDetailView,
    PublicTableColumnsView,
    APIKeyListCreateView,
    APIKeyDetailView,
)

app_name = 'table_logic'

urlpatterns = [
    # =============================================
    # INTERNAL API (Session Auth - Dashboard)
    # =============================================
    path('tables/', TableListCreateView.as_view(), name='api_tables'),
    path('tables/<str:table_name>/', TableDetailView.as_view(), name='api_table_detail'),
    path('tables/<str:table_name>/schema/', TableSchemaView.as_view(), name='api_table_schema'),
    path('tables/<str:table_name>/rows/', TableRowsView.as_view(), name='api_table_rows'),
    path('tables/<str:table_name>/rows/<str:row_id>/', TableRowDetailView.as_view(), name='api_table_row'),
    path('tables/<str:table_name>/export/', TableExportView.as_view(), name='api_table_export'),
    path('tables/<str:table_name>/import/', TableImportView.as_view(), name='api_table_import'),
    
    # Stats API
    path('stats/', StatsView.as_view(), name='api_stats'),
    
    # Activity API
    path('activity/', ActivityView.as_view(), name='api_activity'),
    
    # API Key Management (Session Auth)
    path('keys/', APIKeyListCreateView.as_view(), name='api_keys'),
    path('keys/<int:key_id>/', APIKeyDetailView.as_view(), name='api_key_detail'),
    
    # =============================================
    # PUBLIC API v1 (API Key Auth - External Apps)
    # =============================================
    path('v1/tables/', PublicTableListView.as_view(), name='public_tables'),
    path('v1/tables/<str:table_name>/', PublicTableDetailView.as_view(), name='public_table_detail'),
    path('v1/tables/<str:table_name>/rows/', PublicTableRowsView.as_view(), name='public_table_rows'),
    path('v1/tables/<str:table_name>/rows/<int:row_id>/', PublicTableRowDetailView.as_view(), name='public_table_row'),
    path('v1/tables/<str:table_name>/columns/', PublicTableColumnsView.as_view(), name='public_table_columns'),
]


