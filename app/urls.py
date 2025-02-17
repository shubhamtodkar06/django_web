# urls.py
from django.urls import path
from . import views  # Import views from the current directory

urlpatterns = [
    path('get_api_key/', views.get_api_key, name='get_api_key'),
    path('manage_files/', views.manage_files, name='manage_files'),
    path('analysis_results/<int:results_id>/', views.analysis_results, name='analysis_results'),
    path('top_resumes/<int:results_id>/', views.display_top_resumes, name='top_resumes'),
    # Add other URL patterns here as needed
]