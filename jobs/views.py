from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from .models import (Job, UserProfile, JobApplication, PhoneVerification, EmailVerification, SavedJob,
                     HiringStage, ApplicationStageHistory, ApplicationNote, ApplicationRating,
                     ApplicationTag, ApplicationTagAssignment, EmailTemplate, Notification,
                     EmailLog, Message)
from .forms import JobSeekerSignUpForm, EmployerSignUpForm, JobPostForm, JobApplicationForm
from .forms import (JobSeekerSignUpForm, EmployerSignUpForm, JobPostForm,
                   JobApplicationForm, JobSeekerProfileForm, EmployerProfileForm)
from .utils import (generate_verification_code, generate_verification_token,
                   send_phone_verification_code, send_email_verification,
                   format_phone_number, is_valid_phone_number)


# Your existing views stay the same
def home(request):
    recent_jobs = Job.objects.filter(is_active=True).order_by('-posted_date')[:5]
    total_jobs = Job.objects.filter(is_active=True).count()
    total_companies = Job.objects.values('company').distinct().count(),
    total_seekers = UserProfile.objects.filter(user_type='job_seeker').count()
    context = {
        'recent_jobs': recent_jobs,
        'total_jobs': total_jobs,
        'total_companies': total_companies,
        'total_seekers': total_seekers
    }
    return render(request, 'jobs/home.html', context)

def job_list(request):
    from datetime import timedelta
    
    jobs = Job.objects.filter(is_active=True)
    
    # Search query
    search_query = request.GET.get('search', '')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) | 
            Q(company__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    
    # Location filter
    location_filter = request.GET.get('location', '')
    if location_filter:
        jobs = jobs.filter(location__icontains=location_filter)
    
    # Salary filter (has salary or not)
    salary_filter = request.GET.get('salary', '')
    if salary_filter == 'with_salary':
        jobs = jobs.exclude(salary='')
    
    # Date posted filter
    date_filter = request.GET.get('date_posted', '')
    if date_filter:
        if date_filter == '24h':
            jobs = jobs.filter(posted_date__gte=timezone.now() - timedelta(hours=24))
        elif date_filter == '7d':
            jobs = jobs.filter(posted_date__gte=timezone.now() - timedelta(days=7))
        elif date_filter == '30d':
            jobs = jobs.filter(posted_date__gte=timezone.now() - timedelta(days=30))
    
    # Get unique locations for filter dropdown
    all_locations = Job.objects.filter(is_active=True).values_list('location', flat=True).distinct().order_by('location')
    
    jobs = jobs.order_by('-posted_date')
    
    context = {
        'jobs': jobs,
        'search_query': search_query,
        'location_filter': location_filter,
        'salary_filter': salary_filter,
        'date_filter': date_filter,
        'all_locations': all_locations,
        'total_results': jobs.count()
    }
    return render(request, 'jobs/job_list.html', context)

def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    user_has_applied = False
    job_is_saved = False

    if request.user.is_authenticated:
        user_has_applied = JobApplication.objects.filter(
            job=job,
            applicant=request.user
        ).exists()
        job_is_saved = SavedJob.objects.filter(
            job=job,
            user=request.user
        ).exists()

    context = {
        'job': job,
        'user_has_applied': user_has_applied,
        'job_is_saved': job_is_saved
    }
    return render(request, 'jobs/job_detail.html', context)

# New authentication views
def signup_choice(request):
    return render(request, 'jobs/signup_choice.html')

def jobseeker_signup(request):
    if request.method == 'POST':
        form = JobSeekerSignUpForm(request.POST)
        if form.is_valid():
            # Validate phone number
            phone_number = form.cleaned_data.get('phone_number')
            if not is_valid_phone_number(phone_number):
                messages.error(request, 'Please enter a valid phone number.')
                return render(request, 'jobs/signup.html', {'form': form, 'user_type': 'Job Seeker'})

            # Create user
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            # Create phone verification
            formatted_phone = format_phone_number(phone_number)
            verification_code = generate_verification_code()
            PhoneVerification.objects.create(
                user=user,
                phone_number=formatted_phone,
                verification_code=verification_code
            )

            # Send SMS verification code
            if send_phone_verification_code(formatted_phone, verification_code):
                messages.success(request, 'Account created! Please verify your phone number.')
            else:
                messages.warning(request, 'Account created, but we could not send verification code. Please contact support.')

            # Create email verification
            verification_token = generate_verification_token()
            EmailVerification.objects.create(
                user=user,
                verification_token=verification_token
            )

            # Send email verification
            send_email_verification(user, verification_token)

            # Redirect to phone verification
            return redirect('verify_phone')
    else:
        form = JobSeekerSignUpForm()
    return render(request, 'jobs/signup.html', {'form': form, 'user_type': 'Job Seeker'})

def employer_signup(request):
    if request.method == 'POST':
        form = EmployerSignUpForm(request.POST)
        if form.is_valid():
            # Validate phone number
            phone_number = form.cleaned_data.get('phone_number')
            if not is_valid_phone_number(phone_number):
                messages.error(request, 'Please enter a valid phone number.')
                return render(request, 'jobs/signup.html', {'form': form, 'user_type': 'Employer'})

            # Create user
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            # Create phone verification
            formatted_phone = format_phone_number(phone_number)
            verification_code = generate_verification_code()
            PhoneVerification.objects.create(
                user=user,
                phone_number=formatted_phone,
                verification_code=verification_code
            )

            # Send SMS verification code
            if send_phone_verification_code(formatted_phone, verification_code):
                messages.success(request, 'Employer account created! Please verify your phone number.')
            else:
                messages.warning(request, 'Account created, but we could not send verification code. Please contact support.')

            # Create email verification
            verification_token = generate_verification_token()
            EmailVerification.objects.create(
                user=user,
                verification_token=verification_token
            )

            # Send email verification
            send_email_verification(user, verification_token)

            # Redirect to phone verification
            return redirect('verify_phone')
    else:
        form = EmployerSignUpForm()
    return render(request, 'jobs/signup.html', {'form': form, 'user_type': 'Employer'})

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            
            # Redirect based on user type
            if hasattr(user, 'userprofile'):
                if user.userprofile.user_type == 'employer':
                    return redirect('employer_dashboard')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'jobs/login.html')

def user_logout(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')

@login_required
def employer_dashboard(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')
    
    employer_jobs = Job.objects.filter(posted_by=request.user).order_by('-posted_date')
    context = {
        'jobs': employer_jobs
    }
    return render(request, 'jobs/employer_dashboard.html', context)

@login_required
def post_job(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Only employers can post jobs.')
        return redirect('home')
    
    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            if not job.company and request.user.userprofile.company_name:
                job.company = request.user.userprofile.company_name
            job.save()
            messages.success(request, 'Job posted successfully!')
            return redirect('employer_dashboard')
    else:
        form = JobPostForm(initial={'company': request.user.userprofile.company_name})
    
    return render(request, 'jobs/post_job.html', {'form': form})

@login_required
def edit_job(request, job_id):
    """Edit an existing job posting"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can edit
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to edit this job.')
        return redirect('employer_dashboard')

    if request.method == 'POST':
        form = JobPostForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job updated successfully!')
            return redirect('employer_dashboard')
    else:
        form = JobPostForm(instance=job)

    context = {
        'form': form,
        'job': job,
        'is_edit': True
    }
    return render(request, 'jobs/post_job.html', context)

@login_required
def delete_job(request, job_id):
    """Delete a job posting"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can delete
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to delete this job.')
        return redirect('employer_dashboard')

    if request.method == 'POST':
        job_title = job.title
        job.delete()
        messages.success(request, f'Job "{job_title}" has been deleted.')
        return redirect('employer_dashboard')

    return render(request, 'jobs/delete_job_confirm.html', {'job': job})

@login_required
def toggle_job_status(request, job_id):
    """Toggle job active/inactive status"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can toggle status
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to modify this job.')
        return redirect('employer_dashboard')

    job.is_active = not job.is_active
    job.save()

    status = "activated" if job.is_active else "deactivated"
    messages.success(request, f'Job "{job.title}" has been {status}.')
    return redirect('employer_dashboard')

@login_required
def apply_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'employer':
        messages.error(request, 'Employers cannot apply for jobs.')
        return redirect('job_detail', job_id=job_id)
    
    if JobApplication.objects.filter(job=job, applicant=request.user).exists():
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', job_id=job_id)
    
    if request.method == 'POST':
        form = JobApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.applicant = request.user
            application.save()

            # Notify employer of new application
            if job.posted_by:
                Notification.create_notification(
                    recipient=job.posted_by,
                    notification_type='application_received',
                    title=f'New Application - {job.title}',
                    message=f'{request.user.get_full_name() or request.user.username} has applied for {job.title}.',
                    link=f'/employer/application/{application.id}/',
                    application=application,
                    job=job
                )

            messages.success(request, 'Application submitted successfully!')
            return redirect('job_detail', job_id=job_id)
    else:
        form = JobApplicationForm()
    
    return render(request, 'jobs/apply_job.html', {'form': form, 'job': job})

@login_required
def privacy_settings(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'download_data':
            # In a real app, you'd generate a data export here
            messages.success(request, 'Your data download will be prepared and emailed to you.')
        
        elif action == 'delete_account':
            # Add confirmation step in real implementation
            messages.warning(request, 'Please contact support to delete your account.')
        
        return redirect('privacy_settings')
    
    return render(request, 'jobs/privacy_settings.html')

@login_required
def user_profile(request):
    user_applications = None
    application_stats = {
        'pending_count': 0,
        'reviewed_count': 0,
        'accepted_count': 0,
        'rejected_count': 0
    }

    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'job_seeker':
        user_applications = JobApplication.objects.filter(applicant=request.user).order_by('-applied_date')

        # Calculate statistics
        application_stats['pending_count'] = user_applications.filter(status='pending').count()
        application_stats['reviewed_count'] = user_applications.filter(status='reviewed').count()
        application_stats['accepted_count'] = user_applications.filter(status='accepted').count()
        application_stats['rejected_count'] = user_applications.filter(status='rejected').count()

    context = {
        'user_applications': user_applications,
        'application_stats': application_stats
    }
    return render(request, 'jobs/profile.html', context)

# Add these imports at the top

# Add these new views after your existing views

@login_required
def edit_profile(request):
    profile = request.user.userprofile
    
    if profile.user_type == 'job_seeker':
        form_class = JobSeekerProfileForm
    else:
        form_class = EmployerProfileForm
    
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_profile')
    else:
        form = form_class(instance=profile)
    
    return render(request, 'jobs/edit_profile.html', {
        'form': form, 
        'user_type': profile.user_type
    })

@login_required
def view_application(request, application_id):
    application = get_object_or_404(JobApplication, id=application_id)
    
    # Only the employer who posted the job or the applicant can view the application
    if request.user != application.job.posted_by and request.user != application.applicant:
        messages.error(request, 'You do not have permission to view this application.')
        return redirect('home')
    
    return render(request, 'jobs/view_application.html', {'application': application})

@login_required
def download_resume(request, application_id):
    application = get_object_or_404(JobApplication, id=application_id)

    # Only the employer who posted the job can download resumes
    if request.user != application.job.posted_by:
        messages.error(request, 'You do not have permission to download this resume.')
        return redirect('home')

    resume = application.get_resume()
    if resume:
        import os
        from django.utils.encoding import escape_uri_path

        # Get the original filename or construct a safe one
        original_filename = os.path.basename(resume.name)
        if not original_filename:
            # Construct filename from applicant info and job title
            safe_job_title = "".join(c for c in application.job.title if c.isalnum() or c in (' ', '-', '_')).strip()
            original_filename = f"{application.applicant.username}_{safe_job_title}_resume.pdf"

        response = HttpResponse(resume.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{escape_uri_path(original_filename)}"'
        return response
    else:
        messages.error(request, 'No resume available for this applicant.')
        return redirect('employer_dashboard')

def privacy_policy(request):
    return render(request, 'jobs/privacy_policy.html')

def terms_of_service(request):
    return render(request, 'jobs/terms.html')

def contact(request):
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        user_type = request.POST.get('user_type')

        # For now, just show a success message
        # In production, you would send an email or save to database
        messages.success(request, f'Thank you {name}! Your message has been received. We will get back to you at {email} soon.')
        return redirect('contact')

    return render(request, 'jobs/contact.html')


# Verification Views
@login_required
def verify_phone_code(request):
    """View for entering phone verification code"""
    try:
        phone_verification = PhoneVerification.objects.get(user=request.user)
    except PhoneVerification.DoesNotExist:
        messages.error(request, 'No phone verification record found.')
        return redirect('home')

    # If already verified, redirect
    if phone_verification.is_verified:
        messages.info(request, 'Your phone is already verified.')
        return redirect('user_profile')

    if request.method == 'POST':
        entered_code = request.POST.get('verification_code', '').strip()

        # Check if code is expired
        if phone_verification.is_code_expired():
            messages.error(request, 'Verification code has expired. Please request a new code.')
            return render(request, 'jobs/verify_phone.html', {
                'phone_number': phone_verification.phone_number,
                'expired': True
            })

        # Verify the code
        if entered_code == phone_verification.verification_code:
            phone_verification.is_verified = True
            phone_verification.verified_at = timezone.now()
            phone_verification.save()
            messages.success(request, 'Phone verified successfully!')
            return redirect('user_profile')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')

    return render(request, 'jobs/verify_phone.html', {
        'phone_number': phone_verification.phone_number
    })


def verify_email(request, token):
    """View for email verification via link"""
    try:
        email_verification = EmailVerification.objects.get(verification_token=token)
    except EmailVerification.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('home')

    # Check if already verified
    if email_verification.is_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('home')

    # Check if token is expired
    if email_verification.is_token_expired():
        messages.error(request, 'Verification link has expired. Please request a new one.')
        return redirect('home')

    # Verify the email
    email_verification.is_verified = True
    email_verification.verified_at = timezone.now()
    email_verification.save()

    # Log the user in if not already logged in
    if not request.user.is_authenticated:
        login(request, email_verification.user, backend='django.contrib.auth.backends.ModelBackend')

    return render(request, 'jobs/verify_email_success.html', {
        'user': email_verification.user
    })


@login_required
def resend_verification_code(request):
    """Resend phone verification code"""
    try:
        phone_verification = PhoneVerification.objects.get(user=request.user)
    except PhoneVerification.DoesNotExist:
        messages.error(request, 'No phone verification record found.')
        return redirect('home')

    if phone_verification.is_verified:
        messages.info(request, 'Your phone is already verified.')
        return redirect('user_profile')

    # Generate new code
    new_code = generate_verification_code()
    phone_verification.verification_code = new_code
    phone_verification.created_at = timezone.now()  # Reset expiry time
    phone_verification.save()

    # Send new code
    if send_phone_verification_code(phone_verification.phone_number, new_code):
        messages.success(request, 'A new verification code has been sent to your phone.')
    else:
        messages.error(request, 'Failed to send verification code. Please try again later.')

    return redirect('verify_phone')


# Saved Jobs Views
@login_required
def save_job(request, job_id):
    """Save/bookmark a job for later"""
    job = get_object_or_404(Job, id=job_id)

    # Check if already saved
    saved, created = SavedJob.objects.get_or_create(user=request.user, job=job)

    if created:
        messages.success(request, f'"{job.title}" saved to your bookmarks!')
    else:
        messages.info(request, 'This job is already in your saved jobs.')

    return redirect('job_detail', job_id=job_id)


@login_required
def unsave_job(request, job_id):
    """Remove a job from saved/bookmarks"""
    job = get_object_or_404(Job, id=job_id)

    try:
        saved_job = SavedJob.objects.get(user=request.user, job=job)
        saved_job.delete()
        messages.success(request, f'"{job.title}" removed from your bookmarks.')
    except SavedJob.DoesNotExist:
        messages.warning(request, 'This job was not in your saved jobs.')

    return redirect('job_detail', job_id=job_id)


@login_required
def saved_jobs_list(request):
    """View all saved/bookmarked jobs"""
    saved_jobs = SavedJob.objects.filter(user=request.user).select_related('job')

    context = {
        'saved_jobs': saved_jobs
    }
    return render(request, 'jobs/saved_jobs.html', context)


@login_required
def update_application_status(request, application_id):
    """Update the status of a job application (employer only)"""
    application = get_object_or_404(JobApplication, id=application_id)

    # Only the employer who posted the job can update status
    if request.user != application.job.posted_by:
        messages.error(request, 'You do not have permission to update this application.')
        return redirect('home')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = ['pending', 'reviewed', 'accepted', 'rejected']

        if new_status in valid_statuses:
            application.status = new_status
            application.save()

            status_messages = {
                'pending': 'Application marked as pending.',
                'reviewed': 'Application marked as reviewed.',
                'accepted': 'Application accepted!',
                'rejected': 'Application rejected.'
            }

            messages.success(request, status_messages.get(new_status, 'Application status updated.'))
        else:
            messages.error(request, 'Invalid status.')

    return redirect('employer_dashboard')


# ============================================
# APPLICANT TRACKING SYSTEM (ATS) VIEWS
# ============================================

@login_required
def ats_pipeline(request, job_id):
    """Kanban-style pipeline view for a specific job's applications"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can view the pipeline
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to view this pipeline.')
        return redirect('employer_dashboard')

    # Ensure employer has hiring stages, create defaults if not
    if not HiringStage.objects.filter(employer=request.user).exists():
        HiringStage.create_default_stages_for_employer(request.user)

    stages = HiringStage.objects.filter(employer=request.user)
    applications = job.applications.select_related('applicant', 'current_stage').prefetch_related('ratings', 'tag_assignments__tag')

    # Assign applications without a stage to the first stage (Applied)
    first_stage = stages.first()
    for app in applications:
        if app.current_stage is None and first_stage:
            app.current_stage = first_stage
            app.save()

    # Group applications by stage
    pipeline_data = []
    for stage in stages:
        stage_apps = [app for app in applications if app.current_stage_id == stage.id]
        pipeline_data.append({
            'stage': stage,
            'applications': stage_apps,
            'count': len(stage_apps)
        })

    # Get tags for the filter dropdown
    tags = ApplicationTag.objects.filter(employer=request.user)

    context = {
        'job': job,
        'pipeline_data': pipeline_data,
        'stages': stages,
        'tags': tags,
        'total_applications': applications.count()
    }
    return render(request, 'jobs/ats/pipeline.html', context)


@login_required
def move_application_stage(request, application_id):
    """Move an application to a different stage (AJAX endpoint)"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    application = get_object_or_404(JobApplication, id=application_id)

    # Ensure only the job owner can move applications
    if application.job.posted_by != request.user:
        return HttpResponse(status=403)

    stage_id = request.POST.get('stage_id')
    notes = request.POST.get('notes', '')

    try:
        new_stage = HiringStage.objects.get(id=stage_id, employer=request.user)
    except HiringStage.DoesNotExist:
        return HttpResponse(status=400)

    old_stage = application.current_stage
    application.current_stage = new_stage
    application.save()

    # Record the stage change in history
    ApplicationStageHistory.objects.create(
        application=application,
        stage=new_stage,
        changed_by=request.user,
        notes=notes
    )

    # Update legacy status field based on stage name
    stage_to_status = {
        'Applied': 'pending',
        'Screening': 'reviewed',
        'Interview': 'reviewed',
        'Offer': 'accepted',
        'Hired': 'accepted',
        'Rejected': 'rejected'
    }
    if new_stage.name in stage_to_status:
        application.status = stage_to_status[new_stage.name]
        application.save()

    # Create notification for applicant about stage change
    notification_type = 'stage_change'
    if new_stage.name == 'Rejected':
        notification_type = 'application_rejected'
    elif new_stage.name == 'Offer':
        notification_type = 'offer_received'
    elif new_stage.name == 'Interview':
        notification_type = 'interview_scheduled'

    Notification.create_notification(
        recipient=application.applicant,
        notification_type=notification_type,
        title=f'Application Update - {application.job.title}',
        message=f'Your application for {application.job.title} at {application.job.company} has moved to the {new_stage.name} stage.',
        link=f'/application/{application.id}/',
        application=application,
        job=application.job
    )

    messages.success(request, f'Moved {application.applicant.get_full_name() or application.applicant.username} to {new_stage.name}')

    # If AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'success': True, 'new_stage': new_stage.name})

    return redirect('ats_pipeline', job_id=application.job.id)


@login_required
def application_detail_ats(request, application_id):
    """Enhanced application detail view with ATS features"""
    application = get_object_or_404(JobApplication, id=application_id)

    # Only the employer who posted the job or the applicant can view
    if request.user != application.job.posted_by and request.user != application.applicant:
        messages.error(request, 'You do not have permission to view this application.')
        return redirect('home')

    is_employer = request.user == application.job.posted_by

    # Get related ATS data for employers
    notes = []
    ratings = []
    tags = []
    stages = []
    stage_history = []
    user_rating = None
    all_tags = []

    if is_employer:
        notes = application.notes.select_related('author').all()
        ratings = application.ratings.select_related('rater').all()
        tags = application.get_tags()
        stages = HiringStage.objects.filter(employer=request.user)
        stage_history = application.stage_history.select_related('stage', 'changed_by').all()
        all_tags = ApplicationTag.objects.filter(employer=request.user)

        # Get current user's rating if exists
        try:
            user_rating = application.ratings.get(rater=request.user)
        except ApplicationRating.DoesNotExist:
            pass

    context = {
        'application': application,
        'is_employer': is_employer,
        'notes': notes,
        'ratings': ratings,
        'tags': tags,
        'stages': stages,
        'stage_history': stage_history,
        'user_rating': user_rating,
        'all_tags': all_tags,
        'average_rating': application.get_average_rating()
    }
    return render(request, 'jobs/ats/application_detail.html', context)


@login_required
def add_application_note(request, application_id):
    """Add a note to an application"""
    if request.method != 'POST':
        return redirect('application_detail_ats', application_id=application_id)

    application = get_object_or_404(JobApplication, id=application_id)

    # Ensure only the job owner can add notes
    if application.job.posted_by != request.user:
        messages.error(request, 'You do not have permission to add notes.')
        return redirect('home')

    content = request.POST.get('content', '').strip()
    is_private = request.POST.get('is_private') == 'on'

    if content:
        ApplicationNote.objects.create(
            application=application,
            author=request.user,
            content=content,
            is_private=is_private
        )
        messages.success(request, 'Note added successfully.')
    else:
        messages.error(request, 'Note content cannot be empty.')

    return redirect('application_detail_ats', application_id=application_id)


@login_required
def delete_application_note(request, note_id):
    """Delete a note from an application"""
    note = get_object_or_404(ApplicationNote, id=note_id)

    # Only the note author can delete their own notes
    if note.author != request.user:
        messages.error(request, 'You can only delete your own notes.')
        return redirect('application_detail_ats', application_id=note.application.id)

    application_id = note.application.id
    note.delete()
    messages.success(request, 'Note deleted successfully.')

    return redirect('application_detail_ats', application_id=application_id)


@login_required
def rate_application(request, application_id):
    """Add or update a rating for an application"""
    if request.method != 'POST':
        return redirect('application_detail_ats', application_id=application_id)

    application = get_object_or_404(JobApplication, id=application_id)

    # Ensure only the job owner can rate applications
    if application.job.posted_by != request.user:
        messages.error(request, 'You do not have permission to rate this application.')
        return redirect('home')

    overall_rating = request.POST.get('overall_rating')
    skills_rating = request.POST.get('skills_rating') or None
    experience_rating = request.POST.get('experience_rating') or None
    culture_fit_rating = request.POST.get('culture_fit_rating') or None
    comments = request.POST.get('comments', '').strip()

    if not overall_rating:
        messages.error(request, 'Overall rating is required.')
        return redirect('application_detail_ats', application_id=application_id)

    # Update or create rating
    rating, created = ApplicationRating.objects.update_or_create(
        application=application,
        rater=request.user,
        defaults={
            'overall_rating': int(overall_rating),
            'skills_rating': int(skills_rating) if skills_rating else None,
            'experience_rating': int(experience_rating) if experience_rating else None,
            'culture_fit_rating': int(culture_fit_rating) if culture_fit_rating else None,
            'comments': comments
        }
    )

    if created:
        messages.success(request, 'Rating added successfully.')
    else:
        messages.success(request, 'Rating updated successfully.')

    return redirect('application_detail_ats', application_id=application_id)


@login_required
def manage_application_tags(request, application_id):
    """Add or remove tags from an application"""
    if request.method != 'POST':
        return redirect('application_detail_ats', application_id=application_id)

    application = get_object_or_404(JobApplication, id=application_id)

    # Ensure only the job owner can manage tags
    if application.job.posted_by != request.user:
        messages.error(request, 'You do not have permission to manage tags.')
        return redirect('home')

    action = request.POST.get('action')
    tag_id = request.POST.get('tag_id')

    if action == 'add' and tag_id:
        try:
            tag = ApplicationTag.objects.get(id=tag_id, employer=request.user)
            ApplicationTagAssignment.objects.get_or_create(
                application=application,
                tag=tag,
                defaults={'assigned_by': request.user}
            )
            messages.success(request, f'Tag "{tag.name}" added.')
        except ApplicationTag.DoesNotExist:
            messages.error(request, 'Invalid tag.')

    elif action == 'remove' and tag_id:
        try:
            tag = ApplicationTag.objects.get(id=tag_id, employer=request.user)
            ApplicationTagAssignment.objects.filter(application=application, tag=tag).delete()
            messages.success(request, f'Tag "{tag.name}" removed.')
        except ApplicationTag.DoesNotExist:
            messages.error(request, 'Invalid tag.')

    return redirect('application_detail_ats', application_id=application_id)


@login_required
def manage_tags(request):
    """Manage employer's tag library"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            color = request.POST.get('color', '#007bff')

            if name:
                tag, created = ApplicationTag.objects.get_or_create(
                    name=name,
                    employer=request.user,
                    defaults={'color': color}
                )
                if created:
                    messages.success(request, f'Tag "{name}" created.')
                else:
                    messages.warning(request, f'Tag "{name}" already exists.')
            else:
                messages.error(request, 'Tag name is required.')

        elif action == 'delete':
            tag_id = request.POST.get('tag_id')
            try:
                tag = ApplicationTag.objects.get(id=tag_id, employer=request.user)
                tag_name = tag.name
                tag.delete()
                messages.success(request, f'Tag "{tag_name}" deleted.')
            except ApplicationTag.DoesNotExist:
                messages.error(request, 'Invalid tag.')

        return redirect('manage_tags')

    tags = ApplicationTag.objects.filter(employer=request.user)
    context = {'tags': tags}
    return render(request, 'jobs/ats/manage_tags.html', context)


@login_required
def manage_stages(request):
    """Manage employer's hiring stages"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    # Create default stages if none exist
    if not HiringStage.objects.filter(employer=request.user).exists():
        HiringStage.create_default_stages_for_employer(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            color = request.POST.get('color', '#6c757d')

            if name:
                max_order = HiringStage.objects.filter(employer=request.user).count()
                stage, created = HiringStage.objects.get_or_create(
                    name=name,
                    employer=request.user,
                    defaults={'color': color, 'order': max_order}
                )
                if created:
                    messages.success(request, f'Stage "{name}" created.')
                else:
                    messages.warning(request, f'Stage "{name}" already exists.')
            else:
                messages.error(request, 'Stage name is required.')

        elif action == 'delete':
            stage_id = request.POST.get('stage_id')
            try:
                stage = HiringStage.objects.get(id=stage_id, employer=request.user)
                stage_name = stage.name
                # Move applications from deleted stage to the first available stage
                first_stage = HiringStage.objects.filter(employer=request.user).exclude(id=stage_id).first()
                JobApplication.objects.filter(current_stage=stage).update(current_stage=first_stage)
                stage.delete()
                messages.success(request, f'Stage "{stage_name}" deleted.')
            except HiringStage.DoesNotExist:
                messages.error(request, 'Invalid stage.')

        elif action == 'reorder':
            stage_ids = request.POST.getlist('stage_order')
            for index, stage_id in enumerate(stage_ids):
                HiringStage.objects.filter(id=stage_id, employer=request.user).update(order=index)
            messages.success(request, 'Stages reordered successfully.')

        return redirect('manage_stages')

    stages = HiringStage.objects.filter(employer=request.user)
    context = {'stages': stages}
    return render(request, 'jobs/ats/manage_stages.html', context)


# ============================================
# PHASE 2: EMAIL TEMPLATES & NOTIFICATIONS
# ============================================

def send_application_email(sender, application, template, custom_subject=None, custom_body=None):
    """Helper function to send email to applicant and log it"""
    from django.core.mail import send_mail

    # Build context for template rendering
    context = {
        'applicant_name': application.applicant.get_full_name() or application.applicant.username,
        'job_title': application.job.title,
        'company_name': application.job.company,
        'stage_name': application.current_stage.name if application.current_stage else 'Under Review',
    }

    if custom_subject and custom_body:
        subject = custom_subject
        body = custom_body
        # Replace placeholders in custom content too
        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
    else:
        subject, body = template.render(context)

    # Create email log
    email_log = EmailLog.objects.create(
        sender=sender,
        recipient_email=application.applicant.email,
        recipient_user=application.applicant,
        subject=subject,
        body=body,
        template=template if not custom_subject else None,
        application=application,
        status='pending'
    )

    # Try to send email
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.applicant.email],
            fail_silently=False,
        )
        email_log.status = 'sent'
        email_log.sent_at = timezone.now()
        email_log.save()
        return True
    except Exception as e:
        email_log.status = 'failed'
        email_log.error_message = str(e)
        email_log.save()
        return False


@login_required
def manage_email_templates(request):
    """Manage employer's email templates"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    # Create default templates if none exist
    if not EmailTemplate.objects.filter(employer=request.user).exists():
        EmailTemplate.create_default_templates_for_employer(request.user)

    templates = EmailTemplate.objects.filter(employer=request.user)

    context = {
        'templates': templates,
        'template_types': EmailTemplate.TEMPLATE_TYPES
    }
    return render(request, 'jobs/ats/manage_email_templates.html', context)


@login_required
def create_email_template(request):
    """Create a new email template"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        template_type = request.POST.get('template_type', 'custom')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()

        if name and subject and body:
            template, created = EmailTemplate.objects.get_or_create(
                name=name,
                employer=request.user,
                defaults={
                    'template_type': template_type,
                    'subject': subject,
                    'body': body
                }
            )
            if created:
                messages.success(request, f'Template "{name}" created successfully.')
            else:
                messages.warning(request, f'Template "{name}" already exists.')
        else:
            messages.error(request, 'All fields are required.')

        return redirect('manage_email_templates')

    context = {
        'template_types': EmailTemplate.TEMPLATE_TYPES
    }
    return render(request, 'jobs/ats/create_email_template.html', context)


@login_required
def edit_email_template(request, template_id):
    """Edit an existing email template"""
    template = get_object_or_404(EmailTemplate, id=template_id, employer=request.user)

    if request.method == 'POST':
        template.name = request.POST.get('name', '').strip()
        template.template_type = request.POST.get('template_type', 'custom')
        template.subject = request.POST.get('subject', '').strip()
        template.body = request.POST.get('body', '').strip()
        template.is_active = request.POST.get('is_active') == 'on'
        template.save()
        messages.success(request, f'Template "{template.name}" updated successfully.')
        return redirect('manage_email_templates')

    context = {
        'template': template,
        'template_types': EmailTemplate.TEMPLATE_TYPES
    }
    return render(request, 'jobs/ats/edit_email_template.html', context)


@login_required
def delete_email_template(request, template_id):
    """Delete an email template"""
    template = get_object_or_404(EmailTemplate, id=template_id, employer=request.user)

    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'Template "{template_name}" deleted.')

    return redirect('manage_email_templates')


@login_required
def send_email_to_applicant(request, application_id):
    """Send an email to an applicant using a template or custom content"""
    application = get_object_or_404(JobApplication, id=application_id)

    if application.job.posted_by != request.user:
        messages.error(request, 'You do not have permission to contact this applicant.')
        return redirect('home')

    # Ensure employer has email templates
    if not EmailTemplate.objects.filter(employer=request.user).exists():
        EmailTemplate.create_default_templates_for_employer(request.user)

    templates = EmailTemplate.objects.filter(employer=request.user, is_active=True)

    if request.method == 'POST':
        template_id = request.POST.get('template_id')
        custom_subject = request.POST.get('custom_subject', '').strip()
        custom_body = request.POST.get('custom_body', '').strip()

        if template_id and template_id != 'custom':
            try:
                template = EmailTemplate.objects.get(id=template_id, employer=request.user)
                success = send_application_email(request.user, application, template)
            except EmailTemplate.DoesNotExist:
                messages.error(request, 'Invalid template selected.')
                return redirect('send_email_to_applicant', application_id=application_id)
        elif custom_subject and custom_body:
            success = send_application_email(request.user, application, None, custom_subject, custom_body)
        else:
            messages.error(request, 'Please select a template or provide custom content.')
            return redirect('send_email_to_applicant', application_id=application_id)

        if success:
            messages.success(request, f'Email sent to {application.applicant.email}')
            # Create notification for applicant
            Notification.create_notification(
                recipient=application.applicant,
                notification_type='message_received',
                title=f'New message from {application.job.company}',
                message=f'You have received a message regarding your application for {application.job.title}.',
                link=f'/application/{application.id}/',
                application=application,
                job=application.job
            )
        else:
            messages.error(request, 'Failed to send email. Please try again later.')

        return redirect('application_detail_ats', application_id=application_id)

    # Preview context for template rendering
    preview_context = {
        'applicant_name': application.applicant.get_full_name() or application.applicant.username,
        'job_title': application.job.title,
        'company_name': application.job.company,
        'stage_name': application.current_stage.name if application.current_stage else 'Under Review',
    }

    context = {
        'application': application,
        'templates': templates,
        'preview_context': preview_context
    }
    return render(request, 'jobs/ats/send_email.html', context)


@login_required
def email_history(request, application_id=None):
    """View email history for an application or all emails"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    if application_id:
        application = get_object_or_404(JobApplication, id=application_id)
        if application.job.posted_by != request.user:
            messages.error(request, 'Access denied.')
            return redirect('home')
        emails = EmailLog.objects.filter(application=application)
        context = {
            'emails': emails,
            'application': application
        }
    else:
        emails = EmailLog.objects.filter(sender=request.user)
        context = {
            'emails': emails,
            'application': None
        }

    return render(request, 'jobs/ats/email_history.html', context)


@login_required
def notifications_list(request):
    """View all notifications for the current user"""
    notifications = Notification.objects.filter(recipient=request.user)
    unread_count = notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count
    }
    return render(request, 'jobs/ats/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()

    if notification.link:
        return redirect(notification.link)

    return redirect('notifications_list')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications_list')


@login_required
def application_messages(request, application_id):
    """View and send messages for an application"""
    application = get_object_or_404(JobApplication, id=application_id)

    # Only employer or applicant can access
    if request.user != application.job.posted_by and request.user != application.applicant:
        messages.error(request, 'Access denied.')
        return redirect('home')

    is_employer = request.user == application.job.posted_by

    # Mark unread messages as read
    unread_messages = application.messages.exclude(sender=request.user).filter(is_read=False)
    for msg in unread_messages:
        msg.mark_as_read()

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            message = Message.objects.create(
                application=application,
                sender=request.user,
                content=content
            )

            # Create notification for recipient
            if is_employer:
                recipient = application.applicant
                title = f'New message from {application.job.company}'
            else:
                recipient = application.job.posted_by
                title = f'New message from {application.applicant.get_full_name() or application.applicant.username}'

            Notification.create_notification(
                recipient=recipient,
                notification_type='message_received',
                title=title,
                message=f'You have a new message regarding the {application.job.title} position.',
                link=f'/employer/application/{application.id}/messages/' if not is_employer else f'/application/{application.id}/messages/',
                application=application,
                job=application.job
            )

            messages.success(request, 'Message sent.')
        else:
            messages.error(request, 'Message cannot be empty.')

        return redirect('application_messages', application_id=application_id)

    all_messages = application.messages.select_related('sender').all()

    context = {
        'application': application,
        'messages_list': all_messages,
        'is_employer': is_employer
    }
    return render(request, 'jobs/ats/messages.html', context)


def get_unread_notification_count(request):
    """API endpoint to get unread notification count"""
    if not request.user.is_authenticated:
        return HttpResponse('0')
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    from django.http import JsonResponse
    return JsonResponse({'count': count})
