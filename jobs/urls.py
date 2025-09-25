from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),
    
    # Authentication URLs
    path('signup/', views.signup_choice, name='signup_choice'),
    path('signup/jobseeker/', views.jobseeker_signup, name='jobseeker_signup'),
    path('signup/employer/', views.employer_signup, name='employer_signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Employer URLs
    path('employer/dashboard/', views.employer_dashboard, name='employer_dashboard'),
    path('employer/post-job/', views.post_job, name='post_job'),
    
    # Job Application
    path('jobs/<int:job_id>/apply/', views.apply_job, name='apply_job'),

    # Privacy
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),

    path('account/privacy/', views.privacy_settings, name='privacy_settings'),
    path('account/profile/', views.user_profile, name='user_profile'),

    path('account/profile/edit/', views.edit_profile, name='edit_profile'),
    path('application/<int:application_id>/', views.view_application, name='view_application'),
    path('application/<int:application_id>/resume/', views.download_resume, name='download_resume'),
]
