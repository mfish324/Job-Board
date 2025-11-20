from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from .models import Job, UserProfile, JobApplication, PhoneVerification, EmailVerification, SavedJob
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
