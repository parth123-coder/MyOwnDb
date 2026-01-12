from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard Home
    path('', views.home, name='home'),
    
    # Table Pages (will need table API from tables app)
    path('table/<str:table_name>/', views.table_view, name='table'),
    path('table/<str:table_name>/schema/', views.schema_view, name='schema'),
    path('create-table/', views.create_table, name='create_table'),
    
    # Activity
    path('activity/', views.activity, name='activity'),
    
    # API Keys
    path('api-keys/', views.api_keys, name='api_keys'),
    
    # Note: API endpoints will be in the tables app
]
