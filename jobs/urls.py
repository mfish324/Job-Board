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
    path('signup/recruiter/', views.recruiter_signup, name='recruiter_signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Password Reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='jobs/password_reset.html',
             email_template_name='jobs/password_reset_email.html',
             subject_template_name='jobs/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='jobs/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='jobs/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='jobs/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # Employer URLs
    path('employer/dashboard/', views.employer_dashboard, name='employer_dashboard'),

    # Recruiter URLs
    path('recruiter/dashboard/', views.recruiter_dashboard, name='recruiter_dashboard'),
    path('employer/post-job/', views.post_job, name='post_job'),
    path('employer/job/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('employer/job/<int:job_id>/delete/', views.delete_job, name='delete_job'),
    path('employer/job/<int:job_id>/toggle-status/', views.toggle_job_status, name='toggle_job_status'),
    
    # Job Application
    path('jobs/<int:job_id>/apply/', views.apply_job, name='apply_job'),

    # Privacy & Info Pages
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),

    path('account/privacy/', views.privacy_settings, name='privacy_settings'),
    path('account/profile/', views.user_profile, name='user_profile'),

    path('account/profile/edit/', views.edit_profile, name='edit_profile'),
    path('application/<int:application_id>/', views.view_application, name='view_application'),
    path('application/<int:application_id>/resume/', views.download_resume, name='download_resume'),

    # Verification URLs
    path('verify-phone/', views.verify_phone_code, name='verify_phone'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-code/', views.resend_verification_code, name='resend_code'),

    # Saved Jobs URLs
    path('jobs/<int:job_id>/save/', views.save_job, name='save_job'),
    path('jobs/<int:job_id>/unsave/', views.unsave_job, name='unsave_job'),
    path('saved-jobs/', views.saved_jobs_list, name='saved_jobs'),

    # Application Status Update
    path('application/<int:application_id>/update-status/', views.update_application_status, name='update_application_status'),

    # ATS (Applicant Tracking System) URLs
    path('employer/job/<int:job_id>/pipeline/', views.ats_pipeline, name='ats_pipeline'),
    path('employer/application/<int:application_id>/', views.application_detail_ats, name='application_detail_ats'),
    path('employer/application/<int:application_id>/move-stage/', views.move_application_stage, name='move_application_stage'),
    path('employer/application/<int:application_id>/note/', views.add_application_note, name='add_application_note'),
    path('employer/note/<int:note_id>/delete/', views.delete_application_note, name='delete_application_note'),
    path('employer/application/<int:application_id>/rate/', views.rate_application, name='rate_application'),
    path('employer/application/<int:application_id>/tags/', views.manage_application_tags, name='manage_application_tags'),
    path('employer/tags/', views.manage_tags, name='manage_tags'),
    path('employer/stages/', views.manage_stages, name='manage_stages'),

    # ATS Phase 2: Email Templates & Communication
    path('employer/email-templates/', views.manage_email_templates, name='manage_email_templates'),
    path('employer/email-templates/create/', views.create_email_template, name='create_email_template'),
    path('employer/email-templates/<int:template_id>/edit/', views.edit_email_template, name='edit_email_template'),
    path('employer/email-templates/<int:template_id>/delete/', views.delete_email_template, name='delete_email_template'),
    path('employer/application/<int:application_id>/send-email/', views.send_email_to_applicant, name='send_email_to_applicant'),
    path('employer/email-history/', views.email_history, name='email_history'),
    path('employer/application/<int:application_id>/email-history/', views.email_history, name='application_email_history'),
    path('employer/application/<int:application_id>/messages/', views.application_messages, name='application_messages'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/notifications/count/', views.get_unread_notification_count, name='notification_count'),

    # Applicant Messages (for job seekers)
    path('application/<int:application_id>/messages/', views.application_messages, name='applicant_messages'),

    # ATS Phase 3: Team Management
    path('employer/team/', views.team_dashboard, name='team_dashboard'),
    path('employer/team/setup/', views.team_setup, name='team_setup'),
    path('employer/team/invite/', views.invite_team_member, name='invite_team_member'),
    path('employer/team/member/<int:member_id>/remove/', views.remove_team_member, name='remove_team_member'),
    path('employer/team/member/<int:member_id>/role/', views.update_member_role, name='update_member_role'),
    path('employer/team/invitation/<int:invitation_id>/cancel/', views.cancel_invitation, name='cancel_invitation'),
    path('employer/team/leave/', views.leave_team, name='leave_team'),
    path('employer/team/activity/', views.team_activity_log, name='team_activity_log'),
    path('invitation/<str:token>/', views.accept_invitation, name='accept_invitation'),

    # ATS Phase 4: Analytics & Reporting
    path('employer/analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('employer/analytics/export/', views.analytics_export, name='analytics_export'),
    path('employer/job/<int:job_id>/analytics/', views.job_analytics, name='job_analytics'),

    # Candidate Search (for employers)
    path('employer/candidates/', views.candidate_search, name='candidate_search'),
    path('employer/candidates/<int:profile_id>/', views.candidate_detail, name='candidate_detail'),

    # Chatbot API
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
]
