from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
import json
import logging
import csv
import io

logger = logging.getLogger(__name__)
from .models import (Job, UserProfile, JobApplication, PhoneVerification, EmailVerification, SavedJob,
                     HiringStage, ApplicationStageHistory, ApplicationNote, ApplicationRating,
                     ApplicationTag, ApplicationTagAssignment, EmailTemplate, Notification,
                     EmailLog, Message, EmployerTeam, TeamMember, TeamInvitation, ActivityLog,
                     ChatLog, TwoFactorCode, SiteVisit)
from .forms import (JobSeekerSignUpForm, EmployerSignUpForm, RecruiterSignUpForm,
                   JobPostForm, JobApplicationForm, JobSeekerProfileForm,
                   EmployerProfileForm, RecruiterProfileForm)
from .utils import (generate_verification_code, generate_verification_token,
                   send_phone_verification_code, send_email_verification,
                   format_phone_number, is_valid_phone_number, generate_2fa_code,
                   send_2fa_code, sanitize_html, verify_turnstile)


# Rate limit exception handler
def ratelimited_error(request, exception):
    """Custom handler for rate-limited requests"""
    return render(request, '429.html', status=429)


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

    # Start with active jobs that are not expired
    jobs = Job.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )

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

    # Job type filter
    job_type_filter = request.GET.get('job_type', '')
    if job_type_filter:
        jobs = jobs.filter(job_type=job_type_filter)

    # Experience level filter
    experience_filter = request.GET.get('experience', '')
    if experience_filter:
        jobs = jobs.filter(experience_level=experience_filter)

    # Remote status filter
    remote_filter = request.GET.get('remote', '')
    if remote_filter:
        jobs = jobs.filter(remote_status=remote_filter)

    # Get unique locations for filter dropdown (exclude expired jobs)
    all_locations = Job.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).values_list('location', flat=True).distinct().order_by('location')

    jobs = jobs.order_by('-posted_date')

    context = {
        'jobs': jobs,
        'search_query': search_query,
        'location_filter': location_filter,
        'salary_filter': salary_filter,
        'date_filter': date_filter,
        'job_type_filter': job_type_filter,
        'experience_filter': experience_filter,
        'remote_filter': remote_filter,
        'all_locations': all_locations,
        'total_results': jobs.count(),
        # Provide choices for filters
        'job_type_choices': Job.JOB_TYPE_CHOICES,
        'experience_level_choices': Job.EXPERIENCE_LEVEL_CHOICES,
        'remote_status_choices': Job.REMOTE_STATUS_CHOICES,
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

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def jobseeker_signup(request):
    if request.method == 'POST':
        # Verify Turnstile CAPTCHA
        turnstile_token = request.POST.get('cf-turnstile-response', '')
        if not verify_turnstile(turnstile_token, get_client_ip(request)):
            messages.error(request, 'Please complete the human verification check.')
            form = JobSeekerSignUpForm(request.POST)
            return render(request, 'jobs/signup.html', {
                'form': form,
                'user_type': 'Job Seeker',
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
            })

        form = JobSeekerSignUpForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data.get('phone_number', '').strip()

            # Validate phone number only if provided
            if phone_number and not is_valid_phone_number(phone_number):
                messages.error(request, 'Please enter a valid phone number or leave it blank.')
                return render(request, 'jobs/signup.html', {
                    'form': form,
                    'user_type': 'Job Seeker',
                    'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
                })

            # Create user
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            # Create phone verification only if phone number provided
            if phone_number:
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
            else:
                messages.success(request, 'Account created! Note: Add a phone number later for full verification.')

            # Create email verification
            verification_token = generate_verification_token()
            EmailVerification.objects.create(
                user=user,
                verification_token=verification_token
            )

            # Send email verification
            send_email_verification(user, verification_token)

            # Redirect to phone verification if phone provided, otherwise to profile
            if phone_number:
                return redirect('verify_phone')
            else:
                return redirect('user_profile')
    else:
        form = JobSeekerSignUpForm()
    return render(request, 'jobs/signup.html', {
        'form': form,
        'user_type': 'Job Seeker',
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
    })

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def employer_signup(request):
    if request.method == 'POST':
        # Verify Turnstile CAPTCHA
        turnstile_token = request.POST.get('cf-turnstile-response', '')
        if not verify_turnstile(turnstile_token, get_client_ip(request)):
            messages.error(request, 'Please complete the human verification check.')
            form = EmployerSignUpForm(request.POST)
            return render(request, 'jobs/signup.html', {
                'form': form,
                'user_type': 'Employer',
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
            })

        form = EmployerSignUpForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data.get('phone_number', '').strip()

            # Validate phone number only if provided
            if phone_number and not is_valid_phone_number(phone_number):
                messages.error(request, 'Please enter a valid phone number or leave it blank.')
                return render(request, 'jobs/signup.html', {
                    'form': form,
                    'user_type': 'Employer',
                    'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
                })

            # Create user
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            # Create phone verification only if phone number provided
            if phone_number:
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
            else:
                messages.success(request, 'Employer account created! Note: Add a phone number later for full verification.')

            # Create email verification
            verification_token = generate_verification_token()
            EmailVerification.objects.create(
                user=user,
                verification_token=verification_token
            )

            # Send email verification
            send_email_verification(user, verification_token)

            # Redirect to phone verification if phone provided, otherwise to profile
            if phone_number:
                return redirect('verify_phone')
            else:
                return redirect('user_profile')
    else:
        form = EmployerSignUpForm()
    return render(request, 'jobs/signup.html', {
        'form': form,
        'user_type': 'Employer',
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
    })


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def recruiter_signup(request):
    if request.method == 'POST':
        # Verify Turnstile CAPTCHA
        turnstile_token = request.POST.get('cf-turnstile-response', '')
        if not verify_turnstile(turnstile_token, get_client_ip(request)):
            messages.error(request, 'Please complete the human verification check.')
            form = RecruiterSignUpForm(request.POST)
            return render(request, 'jobs/signup.html', {
                'form': form,
                'user_type': 'Recruiter',
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
            })

        form = RecruiterSignUpForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data.get('phone_number', '').strip()

            # Validate phone number only if provided
            if phone_number and not is_valid_phone_number(phone_number):
                messages.error(request, 'Please enter a valid phone number or leave it blank.')
                return render(request, 'jobs/signup.html', {
                    'form': form,
                    'user_type': 'Recruiter',
                    'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
                })

            # Create user
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)

            # Create phone verification only if phone number provided
            if phone_number:
                formatted_phone = format_phone_number(phone_number)
                verification_code = generate_verification_code()
                PhoneVerification.objects.create(
                    user=user,
                    phone_number=formatted_phone,
                    verification_code=verification_code
                )

                # Send SMS verification code
                if send_phone_verification_code(formatted_phone, verification_code):
                    messages.success(request, 'Recruiter account created! Please verify your phone number.')
                else:
                    messages.warning(request, 'Account created, but we could not send verification code. Please contact support.')
            else:
                messages.success(request, 'Recruiter account created! Note: Add a phone number later for full verification.')

            # Create email verification
            verification_token = generate_verification_token()
            EmailVerification.objects.create(
                user=user,
                verification_token=verification_token
            )

            # Send email verification
            send_email_verification(user, verification_token)

            # Redirect to phone verification if phone provided, otherwise to profile
            if phone_number:
                return redirect('verify_phone')
            else:
                return redirect('user_profile')
    else:
        form = RecruiterSignUpForm()
    return render(request, 'jobs/signup.html', {
        'form': form,
        'user_type': 'Recruiter',
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
    })


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def user_login(request):
    if request.method == 'POST':
        # Verify Turnstile CAPTCHA
        turnstile_token = request.POST.get('cf-turnstile-response', '')
        if not verify_turnstile(turnstile_token, get_client_ip(request)):
            messages.error(request, 'Please complete the human verification check.')
            return render(request, 'jobs/login.html', {
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
            })

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'jobs/login.html', {
                'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
            })

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if user has a verified phone number for 2FA
            has_verified_phone = False
            phone_number = None
            try:
                if hasattr(user, 'phone_verification') and user.phone_verification.is_verified:
                    has_verified_phone = True
                    phone_number = user.phone_verification.phone_number
            except Exception:
                # User may not have phone_verification record
                pass

            # Check if 2FA is enabled in settings
            two_fa_enabled = getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False)

            if two_fa_enabled and has_verified_phone:
                # Generate and send 2FA code
                code = generate_2fa_code()
                TwoFactorCode.objects.create(
                    user=user,
                    code=code,
                    ip_address=get_client_ip(request)
                )

                if send_2fa_code(phone_number, code):
                    # Store user ID in session for 2FA verification
                    request.session['2fa_user_id'] = user.id
                    request.session['2fa_pending'] = True
                    messages.info(request, f'A verification code has been sent to your phone ending in ...{phone_number[-4:]}')
                    return redirect('verify_2fa')
                else:
                    # If SMS fails, log them in anyway (graceful degradation)
                    logger.warning(f"2FA SMS failed for user {user.username}, proceeding with login")
                    login(request, user)
                    messages.warning(request, 'Logged in successfully. (2FA SMS could not be sent)')
            else:
                # No 2FA - regular login
                login(request, user)
                messages.success(request, 'Logged in successfully!')

            # Redirect based on user type
            if hasattr(user, 'userprofile'):
                if user.userprofile.user_type == 'employer':
                    return redirect('employer_dashboard')
                elif user.userprofile.user_type == 'recruiter':
                    return redirect('recruiter_dashboard')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password. Forgot your password? Use the link below to reset it.')
    return render(request, 'jobs/login.html', {
        'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', '')
    })


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def verify_2fa(request):
    """Verify 2FA code sent via SMS"""
    # Check if there's a pending 2FA
    if not request.session.get('2fa_pending') or not request.session.get('2fa_user_id'):
        messages.error(request, 'No pending 2FA verification. Please log in again.')
        return redirect('login')

    user_id = request.session.get('2fa_user_id')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()

        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)

            # Get the most recent unused 2FA code for this user
            two_fa = TwoFactorCode.objects.filter(
                user=user,
                is_used=False
            ).first()

            if not two_fa:
                messages.error(request, 'No valid verification code found. Please log in again.')
                return redirect('login')

            if two_fa.is_expired():
                messages.error(request, 'Verification code has expired. Please log in again.')
                # Clean up session
                request.session.pop('2fa_user_id', None)
                request.session.pop('2fa_pending', None)
                return redirect('login')

            if two_fa.code == entered_code:
                # Mark code as used
                two_fa.is_used = True
                two_fa.save()

                # Complete login
                login(request, user)

                # Clean up session
                request.session.pop('2fa_user_id', None)
                request.session.pop('2fa_pending', None)

                messages.success(request, 'Logged in successfully!')

                # Redirect based on user type
                if hasattr(user, 'userprofile'):
                    if user.userprofile.user_type == 'employer':
                        return redirect('employer_dashboard')
                    elif user.userprofile.user_type == 'recruiter':
                        return redirect('recruiter_dashboard')
                return redirect('home')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')

        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            messages.error(request, 'An error occurred. Please try again.')

    return render(request, 'jobs/verify_2fa.html')


@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def resend_2fa_code(request):
    """Resend 2FA code"""
    if not request.session.get('2fa_pending') or not request.session.get('2fa_user_id'):
        messages.error(request, 'No pending 2FA verification.')
        return redirect('login')

    user_id = request.session.get('2fa_user_id')

    try:
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)

        if hasattr(user, 'phone_verification') and user.phone_verification.is_verified:
            phone_number = user.phone_verification.phone_number
            code = generate_2fa_code()

            TwoFactorCode.objects.create(
                user=user,
                code=code,
                ip_address=get_client_ip(request)
            )

            if send_2fa_code(phone_number, code):
                messages.success(request, f'A new code has been sent to ...{phone_number[-4:]}')
            else:
                messages.error(request, 'Failed to send verification code. Please try again.')
        else:
            messages.error(request, 'No verified phone number found.')

    except Exception as e:
        logger.error(f"Resend 2FA error: {e}")
        messages.error(request, 'An error occurred. Please try again.')

    return redirect('verify_2fa')

def user_logout(request):
    logout(request)
    return redirect('home')

@login_required
def employer_dashboard(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    profile = request.user.userprofile
    employer_jobs = Job.objects.filter(posted_by=request.user).order_by('-posted_date')

    context = {
        'jobs': employer_jobs,
        'profile': profile,
        'is_verified': profile.is_verified(),
        'verification_level': profile.get_verification_level(),
    }
    return render(request, 'jobs/employer_dashboard.html', context)


@login_required
def recruiter_dashboard(request):
    """Dashboard for recruiter users showing verification status and candidate search access"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'recruiter':
        messages.error(request, 'Access denied. Recruiter account required.')
        return redirect('home')

    profile = request.user.userprofile
    verification_status = profile.get_recruiter_verification_status()
    is_fully_verified = profile.is_recruiter_verified()

    # Count candidates available (only if recruiter is verified)
    candidates_count = 0
    if is_fully_verified:
        candidates_count = UserProfile.objects.filter(
            user_type='job_seeker',
            profile_searchable=True,
            allow_recruiter_contact=True
        ).count()

    context = {
        'profile': profile,
        'verification_status': verification_status,
        'is_fully_verified': is_fully_verified,
        'candidates_count': candidates_count,
    }
    return render(request, 'jobs/recruiter_dashboard.html', context)


def check_duplicate_job(employer, title, company, location):
    """
    Check if the same employer has posted a similar job within the last 7 days.
    Returns the duplicate job if found, None otherwise.
    """
    from datetime import timedelta
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Check for same title (case-insensitive)
    title_match = Job.objects.filter(
        posted_by=employer,
        title__iexact=title,
        posted_date__gte=seven_days_ago
    ).first()

    if title_match:
        return title_match

    # Check for same company and location combination
    location_match = Job.objects.filter(
        posted_by=employer,
        company__iexact=company,
        location__iexact=location,
        posted_date__gte=seven_days_ago
    ).first()

    return location_match


@login_required
def post_job(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Only employers can post jobs.')
        return redirect('home')

    profile = request.user.userprofile

    # Check if employer is verified
    if not profile.is_verified():
        messages.warning(
            request,
            'You must verify your account before posting jobs. Verification helps ensure all listings '
            'come from real employers. <a href="/account/profile/" class="alert-link">Complete verification</a>'
        )
        return redirect('employer_dashboard')

    duplicate_job = None
    confirm_duplicate = request.POST.get('confirm_duplicate') == 'true'

    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            company = form.cleaned_data['company'] or profile.company_name
            location = form.cleaned_data['location']

            # Check for duplicate job (unless user confirmed it's intentional)
            if not confirm_duplicate:
                duplicate_job = check_duplicate_job(request.user, title, company, location)
                if duplicate_job:
                    messages.warning(
                        request,
                        f'We found a similar job posting: "{duplicate_job.title}" posted on '
                        f'{duplicate_job.posted_date.strftime("%B %d, %Y")}. If this is intentional, '
                        'please confirm below.'
                    )
                    return render(request, 'jobs/post_job.html', {
                        'form': form,
                        'duplicate_job': duplicate_job,
                        'show_duplicate_warning': True
                    })

            job = form.save(commit=False)
            job.posted_by = request.user
            if not job.company and profile.company_name:
                job.company = profile.company_name
            # Sanitize HTML in job description to prevent XSS
            job.description = sanitize_html(job.description)
            job.save()
            messages.success(request, 'Job posted successfully!')
            return redirect('employer_dashboard')
    else:
        form = JobPostForm(initial={'company': profile.company_name})

    return render(request, 'jobs/post_job.html', {'form': form})

@login_required
def edit_job(request, job_id):
    """Edit an existing job posting"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can edit
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to edit this job.')
        return redirect('employer_dashboard')

    # Check if employer is verified (for consistency with post_job)
    profile = request.user.userprofile
    if not profile.is_verified():
        messages.warning(
            request,
            'You must verify your account before editing jobs. '
            '<a href="/account/profile/" class="alert-link">Complete verification</a>'
        )
        return redirect('employer_dashboard')

    if request.method == 'POST':
        form = JobPostForm(request.POST, instance=job)
        if form.is_valid():
            edited_job = form.save(commit=False)
            # Sanitize HTML in job description to prevent XSS
            edited_job.description = sanitize_html(edited_job.description)
            edited_job.save()
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
def refresh_job(request, job_id):
    """Refresh/extend a job listing by the default expiration period"""
    job = get_object_or_404(Job, id=job_id)

    # Ensure only the job owner can refresh
    if job.posted_by != request.user:
        messages.error(request, 'You do not have permission to refresh this job.')
        return redirect('employer_dashboard')

    # Refresh the job listing
    job.refresh_listing()
    messages.success(request, f'Job "{job.title}" has been refreshed and will now expire in {Job.DEFAULT_EXPIRATION_DAYS} days.')
    return redirect('employer_dashboard')


def download_job_csv_template(request):
    """Download a CSV template for bulk job uploads"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="job_upload_template.csv"'

    writer = csv.writer(response)
    writer.writerow(['title', 'company', 'description', 'location', 'salary', 'job_type', 'experience_level', 'remote_status', 'is_active'])
    writer.writerow(['Software Engineer', 'Your Company Name', 'Job description goes here. Include requirements, responsibilities, and qualifications.', 'Chicago, IL', '$80,000 - $120,000', 'full_time', 'mid', 'hybrid', 'true'])
    writer.writerow(['Marketing Manager', 'Your Company Name', 'Another job description here.', 'New York, NY', '$60,000 - $80,000', 'full_time', 'senior', 'remote', 'true'])
    writer.writerow(['# Job Type options: full_time, part_time, contract, temporary, internship, freelance', '', '', '', '', '', '', '', ''])
    writer.writerow(['# Experience Level options: entry, mid, senior, lead, executive', '', '', '', '', '', '', '', ''])
    writer.writerow(['# Remote Status options: on_site, remote, hybrid', '', '', '', '', '', '', '', ''])

    return response


@login_required
def bulk_upload_jobs(request):
    """Allow employers to upload multiple jobs via CSV"""
    # Check if user is an employer
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type not in ['employer', 'recruiter']:
        messages.error(request, 'Only employers and recruiters can upload jobs.')
        return redirect('home')

    profile = request.user.userprofile

    # Check if employer is verified
    if not profile.is_verified():
        messages.warning(
            request,
            'You must verify your account before uploading jobs. Verification helps ensure all listings '
            'come from real employers. <a href="/account/profile/" class="alert-link">Complete verification</a>'
        )
        return redirect('employer_dashboard')

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            messages.error(request, 'Please select a CSV file to upload.')
            return render(request, 'jobs/bulk_upload_jobs.html')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a file with .csv extension.')
            return render(request, 'jobs/bulk_upload_jobs.html')

        try:
            # Read and decode the file
            decoded_file = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))

            created_count = 0
            error_count = 0
            errors = []

            # Get company name from profile
            company_name = request.user.userprofile.company_name or request.user.userprofile.agency_name or ''

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Required fields
                    title = row.get('title', '').strip()
                    company = row.get('company', '').strip() or company_name
                    description = row.get('description', '').strip()
                    location = row.get('location', '').strip()

                    if not all([title, description, location]):
                        errors.append(f"Row {row_num}: Missing required field(s) (title, description, or location)")
                        error_count += 1
                        continue

                    if not company:
                        errors.append(f"Row {row_num}: Company name required")
                        error_count += 1
                        continue

                    # Optional fields
                    salary = row.get('salary', '').strip()
                    is_active = row.get('is_active', 'true').lower() in ('true', '1', 'yes', '')

                    # New optional fields
                    job_type = row.get('job_type', '').strip() or 'full_time'
                    experience_level = row.get('experience_level', '').strip()
                    remote_status = row.get('remote_status', '').strip() or 'on_site'

                    # Validate job_type
                    valid_job_types = [choice[0] for choice in Job.JOB_TYPE_CHOICES]
                    if job_type and job_type not in valid_job_types:
                        job_type = 'full_time'

                    # Validate experience_level
                    valid_experience_levels = [choice[0] for choice in Job.EXPERIENCE_LEVEL_CHOICES]
                    if experience_level and experience_level not in valid_experience_levels:
                        experience_level = ''

                    # Validate remote_status
                    valid_remote_statuses = [choice[0] for choice in Job.REMOTE_STATUS_CHOICES]
                    if remote_status and remote_status not in valid_remote_statuses:
                        remote_status = 'on_site'

                    # Sanitize HTML in description to prevent XSS
                    sanitized_description = sanitize_html(description)

                    Job.objects.create(
                        title=title,
                        company=company,
                        description=sanitized_description,
                        location=location,
                        salary=salary,
                        job_type=job_type,
                        experience_level=experience_level,
                        remote_status=remote_status,
                        is_active=is_active,
                        posted_by=request.user
                    )
                    created_count += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1

            if created_count > 0:
                messages.success(request, f'Successfully imported {created_count} job(s)!')
            if error_count > 0:
                error_msg = f'Failed to import {error_count} row(s).'
                if errors:
                    error_msg += ' Errors: ' + '; '.join(errors[:3])
                    if len(errors) > 3:
                        error_msg += f' ... and {len(errors) - 3} more.'
                messages.warning(request, error_msg)

            if created_count > 0:
                return redirect('employer_dashboard')

        except UnicodeDecodeError:
            messages.error(request, 'Could not read the file. Please ensure it is a valid UTF-8 encoded CSV.')
        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')

    return render(request, 'jobs/bulk_upload_jobs.html')


@login_required
def apply_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'employer':
        messages.error(request, 'Employers cannot apply for jobs.')
        return redirect('job_detail', job_id=job_id)

    # Enforce verification before applying
    if hasattr(request.user, 'userprofile'):
        profile = request.user.userprofile
        if not profile.is_verified():
            messages.warning(
                request,
                'You must verify your phone number or email address before applying for jobs. '
                '<a href="/account/profile/" class="alert-link">Complete verification in your profile</a>.'
            )
            return redirect('job_detail', job_id=job_id)
    else:
        messages.error(request, 'Please complete your profile before applying.')
        return redirect('user_profile')

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
    elif profile.user_type == 'recruiter':
        form_class = RecruiterProfileForm
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

def about(request):
    return render(request, 'jobs/about.html')

def employer_guide(request):
    return render(request, 'jobs/employer_guide.html')

def terms_of_service(request):
    return render(request, 'jobs/terms.html')

def contact(request):
    if request.method == 'POST':
        from django.utils.html import escape
        # Get form data and escape to prevent XSS
        name = escape(request.POST.get('name', ''))
        email = escape(request.POST.get('email', ''))
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
@ratelimit(key='user', rate='3/m', method='ALL', block=True)
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


# ============================================
# PHASE 3: TEAM COLLABORATION & PERMISSIONS
# ============================================

def get_user_team(user):
    """Get the team for a user (either as owner or member)"""
    # Check if user owns a team
    try:
        return user.owned_team
    except EmployerTeam.DoesNotExist:
        pass

    # Check if user is a member of a team
    membership = TeamMember.objects.filter(user=user, is_active=True).first()
    if membership:
        return membership.team

    return None


def get_team_permission(user, team):
    """Get the permission level of a user in a team"""
    if team.owner == user:
        return 'owner'
    try:
        member = TeamMember.objects.get(team=team, user=user, is_active=True)
        return member.role
    except TeamMember.DoesNotExist:
        return None


def can_access_job(user, job):
    """Check if user can access a job's applications (owner or team member)"""
    if job.posted_by == user:
        return True

    team = get_user_team(user)
    if team and team.owner == job.posted_by:
        return True

    return False


@login_required
def team_setup(request):
    """Setup a new team"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    # Check if user already has a team
    team = get_user_team(request.user)
    if team:
        return redirect('team_dashboard')

    if request.method == 'POST':
        team_name = request.POST.get('team_name', '').strip()
        if team_name:
            team = EmployerTeam.objects.create(
                name=team_name,
                owner=request.user
            )
            messages.success(request, f'Team "{team_name}" created successfully!')
            return redirect('team_dashboard')
        else:
            messages.error(request, 'Team name is required.')

    return render(request, 'jobs/ats/team_setup.html')


@login_required
def team_dashboard(request):
    """Team management dashboard"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    team = get_user_team(request.user)
    is_owner = team and team.owner == request.user if team else False

    # If no team exists, redirect to setup
    if not team:
        return redirect('team_setup')

    # Get team data
    members = team.members.select_related('user').filter(is_active=True)
    pending_invitations = team.invitations.filter(status='pending')
    recent_activity = team.activity_logs.select_related('user', 'application', 'job')[:20]

    # Get permission for current user
    user_role = get_team_permission(request.user, team)
    can_manage = user_role in ['owner', 'admin']

    is_admin = user_role == 'admin'

    context = {
        'team': team,
        'members': members,
        'pending_invitations': pending_invitations,
        'recent_activity': recent_activity,
        'is_owner': is_owner,
        'is_admin': is_admin,
        'user_role': user_role,
        'can_manage': can_manage,
        'role_choices': TeamMember.ROLE_CHOICES
    }
    return render(request, 'jobs/ats/team_dashboard.html', context)


@login_required
def invite_team_member(request):
    """Send invitation to join team"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'You need to create a team first.')
        return redirect('team_dashboard')

    # Check if user can manage team
    user_role = get_team_permission(request.user, team)
    if user_role not in ['owner', 'admin']:
        messages.error(request, 'You do not have permission to invite team members.')
        return redirect('team_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', 'reviewer')

        if not email:
            messages.error(request, 'Email is required.')
            return redirect('team_dashboard')

        # Check if already a member
        from django.contrib.auth.models import User
        existing_user = User.objects.filter(email=email).first()
        if existing_user and team.is_member(existing_user):
            messages.warning(request, f'{email} is already a team member.')
            return redirect('team_dashboard')

        # Check if there's already a pending invitation
        if TeamInvitation.objects.filter(team=team, email=email, status='pending').exists():
            messages.warning(request, f'An invitation has already been sent to {email}.')
            return redirect('team_dashboard')

        # Create invitation
        invitation = TeamInvitation.create_invitation(
            team=team,
            email=email,
            role=role,
            invited_by=request.user
        )

        # Send invitation email
        from django.core.mail import send_mail
        try:
            invite_url = request.build_absolute_uri(f'/team/join/{invitation.token}/')
            send_mail(
                subject=f'Invitation to join {team.name} on Real Jobs, Real People',
                message=f'''You have been invited to join {team.name} as a {dict(TeamMember.ROLE_CHOICES).get(role, role)}.

Click the link below to accept the invitation:
{invite_url}

This invitation expires in 7 days.

If you don't have an account, you'll need to create one first.

Best regards,
Real Jobs, Real People Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
            messages.success(request, f'Invitation sent to {email}.')
        except Exception:
            messages.success(request, f'Invitation created for {email}. (Email delivery may be delayed)')

        # Log activity
        ActivityLog.log_activity(
            team=team,
            user=request.user,
            action_type='member_invited',
            description=f'Invited {email} as {role}'
        )

    return redirect('team_dashboard')


@login_required
def accept_invitation(request, token):
    """Accept a team invitation"""
    try:
        invitation = TeamInvitation.objects.get(token=token)
    except TeamInvitation.DoesNotExist:
        messages.error(request, 'Invalid invitation link.')
        return redirect('home')

    if not invitation.is_valid():
        if invitation.is_expired():
            messages.error(request, 'This invitation has expired.')
        else:
            messages.error(request, 'This invitation is no longer valid.')
        return redirect('home')

    # Check if user's email matches invitation
    if request.user.email.lower() != invitation.email.lower():
        messages.error(request, f'This invitation was sent to {invitation.email}. Please log in with that email address.')
        return redirect('home')

    # Check if already a member
    if invitation.team.is_member(request.user):
        messages.info(request, 'You are already a member of this team.')
        invitation.status = 'accepted'
        invitation.accepted_by = request.user
        invitation.save()
        return redirect('team_dashboard')

    if request.method == 'POST':
        # Accept the invitation
        TeamMember.objects.create(
            team=invitation.team,
            user=request.user,
            role=invitation.role,
            invited_by=invitation.invited_by
        )

        invitation.status = 'accepted'
        invitation.accepted_by = request.user
        invitation.save()

        # Update user profile to employer if not already
        if hasattr(request.user, 'userprofile'):
            if request.user.userprofile.user_type != 'employer':
                request.user.userprofile.user_type = 'employer'
                request.user.userprofile.save()

        messages.success(request, f'Welcome to {invitation.team.name}!')
        return redirect('team_dashboard')

    context = {
        'invitation': invitation
    }
    return render(request, 'jobs/ats/accept_invitation.html', context)


@login_required
def remove_team_member(request, member_id):
    """Remove a member from the team"""
    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'Team not found.')
        return redirect('home')

    user_role = get_team_permission(request.user, team)
    if user_role not in ['owner', 'admin']:
        messages.error(request, 'You do not have permission to remove team members.')
        return redirect('team_dashboard')

    try:
        member = TeamMember.objects.get(id=member_id, team=team)
    except TeamMember.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('team_dashboard')

    # Can't remove yourself this way
    if member.user == request.user:
        messages.error(request, 'You cannot remove yourself. Leave the team instead.')
        return redirect('team_dashboard')

    # Only owner can remove admins
    if member.role == 'admin' and user_role != 'owner':
        messages.error(request, 'Only the team owner can remove admins.')
        return redirect('team_dashboard')

    if request.method == 'POST':
        member_name = member.user.get_full_name() or member.user.username
        member.is_active = False
        member.save()

        ActivityLog.log_activity(
            team=team,
            user=request.user,
            action_type='member_removed',
            description=f'Removed {member_name} from the team'
        )

        messages.success(request, f'{member_name} has been removed from the team.')

    return redirect('team_dashboard')


@login_required
def update_member_role(request, member_id):
    """Update a team member's role"""
    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'Team not found.')
        return redirect('home')

    user_role = get_team_permission(request.user, team)
    if user_role not in ['owner', 'admin']:
        messages.error(request, 'You do not have permission to update roles.')
        return redirect('team_dashboard')

    try:
        member = TeamMember.objects.get(id=member_id, team=team)
    except TeamMember.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('team_dashboard')

    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role not in dict(TeamMember.ROLE_CHOICES):
            messages.error(request, 'Invalid role.')
            return redirect('team_dashboard')

        # Only owner can promote to admin
        if new_role == 'admin' and user_role != 'owner':
            messages.error(request, 'Only the team owner can promote members to admin.')
            return redirect('team_dashboard')

        old_role = member.get_role_display()
        member.role = new_role
        member.save()

        messages.success(request, f'Updated {member.user.username}\'s role to {member.get_role_display()}.')

    return redirect('team_dashboard')


@login_required
def cancel_invitation(request, invitation_id):
    """Cancel a pending invitation"""
    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'Team not found.')
        return redirect('home')

    user_role = get_team_permission(request.user, team)
    if user_role not in ['owner', 'admin']:
        messages.error(request, 'You do not have permission to cancel invitations.')
        return redirect('team_dashboard')

    try:
        invitation = TeamInvitation.objects.get(id=invitation_id, team=team, status='pending')
    except TeamInvitation.DoesNotExist:
        messages.error(request, 'Invitation not found.')
        return redirect('team_dashboard')

    if request.method == 'POST':
        invitation.status = 'expired'
        invitation.save()
        messages.success(request, f'Invitation to {invitation.email} has been cancelled.')

    return redirect('team_dashboard')


@login_required
def leave_team(request):
    """Leave the current team"""
    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('home')

    if team.owner == request.user:
        messages.error(request, 'As the team owner, you cannot leave. Transfer ownership or delete the team instead.')
        return redirect('team_dashboard')

    if request.method == 'POST':
        try:
            member = TeamMember.objects.get(team=team, user=request.user)
            member.is_active = False
            member.save()
            messages.success(request, f'You have left {team.name}.')
        except TeamMember.DoesNotExist:
            messages.error(request, 'Membership not found.')

    return redirect('employer_dashboard')


@login_required
def team_activity_log(request):
    """View full activity log for the team"""
    team = get_user_team(request.user)
    if not team:
        messages.error(request, 'Team not found.')
        return redirect('home')

    activities = team.activity_logs.select_related('user', 'application', 'job').all()

    context = {
        'team': team,
        'activities': activities
    }
    return render(request, 'jobs/ats/activity_log.html', context)


# ============================================
# PHASE 4: ANALYTICS & REPORTING
# ============================================

@login_required
def analytics_dashboard(request):
    """Main analytics dashboard for employers"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    from django.db.models import Count, Avg, Q
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
    from datetime import timedelta

    # Date range filter
    date_range = request.GET.get('range', '30')  # Default 30 days
    try:
        days = int(date_range)
    except ValueError:
        days = 30

    start_date = timezone.now() - timedelta(days=days)

    # Get employer's jobs
    jobs = Job.objects.filter(posted_by=request.user)
    job_ids = jobs.values_list('id', flat=True)

    # Basic stats
    total_jobs = jobs.count()
    active_jobs = jobs.filter(is_active=True).count()
    total_applications = JobApplication.objects.filter(job__in=jobs).count()
    recent_applications = JobApplication.objects.filter(
        job__in=jobs,
        applied_date__gte=start_date
    ).count()

    # Applications over time (for chart)
    applications_by_date = JobApplication.objects.filter(
        job__in=jobs,
        applied_date__gte=start_date
    ).annotate(
        date=TruncDate('applied_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    # Stage distribution
    stages = HiringStage.objects.filter(employer=request.user)
    stage_distribution = []
    for stage in stages:
        count = JobApplication.objects.filter(
            job__in=jobs,
            current_stage=stage
        ).count()
        stage_distribution.append({
            'name': stage.name,
            'color': stage.color,
            'count': count
        })

    # Add applications without a stage
    no_stage_count = JobApplication.objects.filter(
        job__in=jobs,
        current_stage__isnull=True
    ).count()
    if no_stage_count > 0:
        stage_distribution.insert(0, {
            'name': 'No Stage',
            'color': '#e9ecef',
            'count': no_stage_count
        })

    # Conversion rates (stage to stage)
    conversion_rates = []
    ordered_stages = list(stages.order_by('order'))
    for i, stage in enumerate(ordered_stages[:-1]):
        current_count = JobApplication.objects.filter(
            job__in=jobs,
            stage_history__stage=stage
        ).distinct().count()
        next_stage = ordered_stages[i + 1]
        next_count = JobApplication.objects.filter(
            job__in=jobs,
            stage_history__stage=next_stage
        ).distinct().count()

        rate = (next_count / current_count * 100) if current_count > 0 else 0
        conversion_rates.append({
            'from_stage': stage.name,
            'to_stage': next_stage.name,
            'from_count': current_count,
            'to_count': next_count,
            'rate': round(rate, 1)
        })

    # Average time in each stage
    time_in_stage = []
    for stage in stages:
        # Calculate average time spent in this stage
        stage_histories = ApplicationStageHistory.objects.filter(
            stage=stage,
            application__job__in=jobs
        ).order_by('application', 'changed_at')

        total_time = timedelta(0)
        count = 0

        for history in stage_histories:
            # Find when they moved to the next stage
            next_history = ApplicationStageHistory.objects.filter(
                application=history.application,
                changed_at__gt=history.changed_at
            ).order_by('changed_at').first()

            if next_history:
                time_diff = next_history.changed_at - history.changed_at
                total_time += time_diff
                count += 1

        avg_days = (total_time.total_seconds() / 86400 / count) if count > 0 else 0
        time_in_stage.append({
            'stage': stage.name,
            'color': stage.color,
            'avg_days': round(avg_days, 1)
        })

    # Per-job performance
    job_stats = []
    for job in jobs[:10]:  # Top 10 jobs
        app_count = job.applications.count()
        avg_rating = job.applications.aggregate(
            avg=Avg('ratings__overall_rating')
        )['avg']
        job_stats.append({
            'job': job,
            'applications': app_count,
            'avg_rating': round(avg_rating, 1) if avg_rating else None
        })

    # Top rated candidates
    top_candidates = JobApplication.objects.filter(
        job__in=jobs
    ).annotate(
        avg_rating=Avg('ratings__overall_rating')
    ).filter(
        avg_rating__isnull=False
    ).select_related('applicant', 'job', 'current_stage').order_by('-avg_rating')[:5]

    # Activity metrics
    emails_sent = EmailLog.objects.filter(
        sender=request.user,
        created_at__gte=start_date
    ).count()

    notes_added = ApplicationNote.objects.filter(
        author=request.user,
        created_at__gte=start_date
    ).count()

    ratings_given = ApplicationRating.objects.filter(
        rater=request.user,
        created_at__gte=start_date
    ).count()

    context = {
        'date_range': days,
        'start_date': start_date,
        # Basic stats
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'total_applications': total_applications,
        'recent_applications': recent_applications,
        # Charts data
        'applications_by_date': list(applications_by_date),
        'stage_distribution': stage_distribution,
        'conversion_rates': conversion_rates,
        'time_in_stage': time_in_stage,
        # Tables
        'job_stats': job_stats,
        'top_candidates': top_candidates,
        # Activity
        'emails_sent': emails_sent,
        'notes_added': notes_added,
        'ratings_given': ratings_given,
    }
    return render(request, 'jobs/ats/analytics_dashboard.html', context)


@login_required
def analytics_export(request):
    """Export analytics data as CSV"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'employer':
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('home')

    import csv
    from django.http import HttpResponse

    export_type = request.GET.get('type', 'applications')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="rjrp_{export_type}_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)

    jobs = Job.objects.filter(posted_by=request.user)

    if export_type == 'applications':
        writer.writerow([
            'Job Title', 'Applicant Name', 'Applicant Email', 'Applied Date',
            'Current Stage', 'Status', 'Average Rating', 'Tags'
        ])

        applications = JobApplication.objects.filter(
            job__in=jobs
        ).select_related('job', 'applicant', 'current_stage').prefetch_related('tag_assignments__tag')

        for app in applications:
            tags = ', '.join([ta.tag.name for ta in app.tag_assignments.all()])
            writer.writerow([
                app.job.title,
                app.applicant.get_full_name() or app.applicant.username,
                app.applicant.email,
                app.applied_date.strftime('%Y-%m-%d %H:%M'),
                app.current_stage.name if app.current_stage else 'No Stage',
                app.status,
                app.get_average_rating() or 'Not Rated',
                tags
            ])

    elif export_type == 'pipeline':
        writer.writerow([
            'Job Title', 'Stage', 'Applications Count', 'Avg Days in Stage'
        ])

        stages = HiringStage.objects.filter(employer=request.user).order_by('order')

        for job in jobs:
            for stage in stages:
                count = job.applications.filter(current_stage=stage).count()
                # Calculate avg time in stage for this job
                writer.writerow([
                    job.title,
                    stage.name,
                    count,
                    'N/A'  # Could calculate avg time here
                ])

    elif export_type == 'jobs':
        writer.writerow([
            'Job Title', 'Company', 'Location', 'Posted Date', 'Status',
            'Total Applications', 'Pending', 'Reviewed', 'Accepted', 'Rejected'
        ])

        for job in jobs:
            apps = job.applications.all()
            writer.writerow([
                job.title,
                job.company,
                job.location,
                job.posted_date.strftime('%Y-%m-%d'),
                'Active' if job.is_active else 'Inactive',
                apps.count(),
                apps.filter(status='pending').count(),
                apps.filter(status='reviewed').count(),
                apps.filter(status='accepted').count(),
                apps.filter(status='rejected').count(),
            ])

    return response


@login_required
def job_analytics(request, job_id):
    """Detailed analytics for a specific job"""
    job = get_object_or_404(Job, id=job_id)

    if job.posted_by != request.user:
        messages.error(request, 'Access denied.')
        return redirect('home')

    from django.db.models import Count, Avg
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    # Applications over time
    applications_by_date = job.applications.annotate(
        date=TruncDate('applied_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    # Stage distribution for this job
    stages = HiringStage.objects.filter(employer=request.user)
    stage_distribution = []
    for stage in stages:
        count = job.applications.filter(current_stage=stage).count()
        stage_distribution.append({
            'name': stage.name,
            'color': stage.color,
            'count': count
        })

    # Status distribution
    status_distribution = {
        'pending': job.applications.filter(status='pending').count(),
        'reviewed': job.applications.filter(status='reviewed').count(),
        'accepted': job.applications.filter(status='accepted').count(),
        'rejected': job.applications.filter(status='rejected').count(),
    }

    # Rating distribution
    rating_distribution = job.applications.filter(
        ratings__isnull=False
    ).values('ratings__overall_rating').annotate(
        count=Count('id')
    ).order_by('ratings__overall_rating')

    # Top candidates for this job
    top_candidates = job.applications.annotate(
        avg_rating=Avg('ratings__overall_rating')
    ).filter(
        avg_rating__isnull=False
    ).select_related('applicant', 'current_stage').order_by('-avg_rating')[:10]

    # Recent activity
    recent_stage_changes = ApplicationStageHistory.objects.filter(
        application__job=job
    ).select_related('application__applicant', 'stage', 'changed_by').order_by('-changed_at')[:10]

    context = {
        'job': job,
        'total_applications': job.applications.count(),
        'applications_by_date': list(applications_by_date),
        'stage_distribution': stage_distribution,
        'status_distribution': status_distribution,
        'rating_distribution': list(rating_distribution),
        'top_candidates': top_candidates,
        'recent_stage_changes': recent_stage_changes,
    }
    return render(request, 'jobs/ats/job_analytics.html', context)


# ============================================
# CANDIDATE SEARCH (FOR EMPLOYERS)
# ============================================

@login_required
def candidate_search(request):
    """Search for candidates/job seekers (employer or verified recruiter)"""
    # Verify user is an employer or verified recruiter
    if not hasattr(request.user, 'userprofile'):
        messages.error(request, 'Access denied. Employer or recruiter account required.')
        return redirect('home')

    profile = request.user.userprofile
    is_employer = profile.user_type == 'employer'
    is_recruiter = profile.user_type == 'recruiter'

    if not is_employer and not is_recruiter:
        messages.error(request, 'Access denied. Employer or recruiter account required.')
        return redirect('home')

    # Recruiters must be fully verified and approved
    if is_recruiter and not profile.is_recruiter_verified():
        messages.warning(request, 'Your recruiter account must be fully verified and approved to search candidates.')
        return redirect('recruiter_dashboard')

    # Base queryset: only verified job seekers with searchable profiles
    candidates = UserProfile.objects.filter(
        user_type='job_seeker',
        profile_searchable=True
    ).select_related('user')

    # For recruiters, only show candidates who opted-in to recruiter contact
    if is_recruiter:
        candidates = candidates.filter(allow_recruiter_contact=True)

    # Only show candidates who have verified (at least email or phone)
    verified_candidates = []
    for profile in candidates:
        if profile.is_verified():
            verified_candidates.append(profile.id)
    candidates = candidates.filter(id__in=verified_candidates)

    # Search query (name, skills, title, bio)
    search_query = request.GET.get('search', '')
    if search_query:
        candidates = candidates.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(skills__icontains=search_query) |
            Q(desired_title__icontains=search_query) |
            Q(bio__icontains=search_query)
        )

    # Location filter
    location_filter = request.GET.get('location', '')
    if location_filter:
        candidates = candidates.filter(location__icontains=location_filter)

    # Skills filter
    skills_filter = request.GET.get('skills', '')
    if skills_filter:
        candidates = candidates.filter(skills__icontains=skills_filter)

    # Experience filter
    min_experience = request.GET.get('min_experience', '')
    if min_experience:
        try:
            candidates = candidates.filter(experience_years__gte=int(min_experience))
        except ValueError:
            pass

    max_experience = request.GET.get('max_experience', '')
    if max_experience:
        try:
            candidates = candidates.filter(experience_years__lte=int(max_experience))
        except ValueError:
            pass

    # Has resume filter
    has_resume = request.GET.get('has_resume', '')
    if has_resume == 'yes':
        candidates = candidates.exclude(resume='')

    # Has LinkedIn filter
    has_linkedin = request.GET.get('has_linkedin', '')
    if has_linkedin == 'yes':
        candidates = candidates.exclude(linkedin_url='')

    # Get unique locations for filter dropdown
    all_locations = UserProfile.objects.filter(
        user_type='job_seeker',
        profile_searchable=True
    ).exclude(location='').values_list('location', flat=True).distinct().order_by('location')

    # Order by most recently updated (using user's date_joined as proxy)
    candidates = candidates.order_by('-user__date_joined')

    context = {
        'candidates': candidates,
        'search_query': search_query,
        'location_filter': location_filter,
        'skills_filter': skills_filter,
        'min_experience': min_experience,
        'max_experience': max_experience,
        'has_resume': has_resume,
        'has_linkedin': has_linkedin,
        'all_locations': all_locations,
        'total_results': candidates.count(),
        'is_recruiter': is_recruiter,
    }
    return render(request, 'jobs/candidate_search.html', context)


@login_required
def candidate_detail(request, profile_id):
    """View candidate profile details (employer or verified recruiter)"""
    # Verify user is an employer or verified recruiter
    if not hasattr(request.user, 'userprofile'):
        messages.error(request, 'Access denied. Employer or recruiter account required.')
        return redirect('home')

    user_profile = request.user.userprofile
    is_employer = user_profile.user_type == 'employer'
    is_recruiter = user_profile.user_type == 'recruiter'

    if not is_employer and not is_recruiter:
        messages.error(request, 'Access denied. Employer or recruiter account required.')
        return redirect('home')

    # Recruiters must be fully verified and approved
    if is_recruiter and not user_profile.is_recruiter_verified():
        messages.warning(request, 'Your recruiter account must be fully verified and approved to view candidates.')
        return redirect('recruiter_dashboard')

    candidate_profile = get_object_or_404(UserProfile, id=profile_id, user_type='job_seeker')

    # Check if profile is searchable
    if not candidate_profile.profile_searchable:
        messages.error(request, 'This candidate profile is not available.')
        return redirect('candidate_search')

    # For recruiters, also check if candidate opted-in to recruiter contact
    if is_recruiter and not candidate_profile.allow_recruiter_contact:
        messages.error(request, 'This candidate has not opted-in to recruiter contact.')
        return redirect('candidate_search')

    # Check if candidate is verified
    if not candidate_profile.is_verified():
        messages.error(request, 'This candidate has not completed verification.')
        return redirect('candidate_search')

    # Get employer's jobs for potential "invite to apply" feature (employers only)
    employer_jobs = []
    applied_jobs = []
    if is_employer:
        employer_jobs = Job.objects.filter(posted_by=request.user, is_active=True)
        # Check if this candidate has applied to any of the employer's jobs
        applied_jobs = JobApplication.objects.filter(
            applicant=candidate_profile.user,
            job__posted_by=request.user
        ).select_related('job')

    context = {
        'candidate': candidate_profile,
        'employer_jobs': employer_jobs,
        'applied_jobs': applied_jobs,
        'is_recruiter': is_recruiter,
        'recruiter_display_name': user_profile.get_recruiter_display_name() if is_recruiter else None,
    }
    return render(request, 'jobs/candidate_detail.html', context)


# =============================================================================
# CHATBOT API
# =============================================================================

@require_POST
@ratelimit(key='ip', rate='20/m', method='POST', block=True)
def chatbot_api(request):
    """AI-powered chatbot using Claude API"""
    import hashlib
    import time

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', '')

        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        if len(user_message) > 1000:
            return JsonResponse({'error': 'Message too long (max 1000 characters)'}, status=400)

        # Get IP hash for anonymous tracking
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:32] if ip_address else ''

        # Check if Anthropic API key is configured
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            return JsonResponse({
                'response': "I'm sorry, the chat assistant is currently unavailable. Please email us at contact@realjobsrealpeople.net for help.",
                'is_ai': False
            })

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # System prompt for the chatbot
        system_prompt = """You are a helpful assistant for Real Jobs, Real People - a job board platform that connects job seekers with employers.

Your role is to help users with:
- How to create an account (job seeker or employer)
- How to search and apply for jobs
- How to post jobs (for employers)
- Understanding the verification process (phone and email verification required)
- General questions about the platform

Key information about the platform:
- Job seekers can create a free account, search jobs, and apply
- Employers can post jobs and use the Applicant Tracking System (ATS)
- All users must verify their phone number and email address
- The platform is currently in beta testing

Be friendly, concise, and helpful. If you don't know the answer or if the user needs human assistance, suggest they email contact@realjobsrealpeople.net or use the Contact Us page.

Keep responses brief (2-3 sentences when possible). Do not make up features that don't exist."""

        # Call Claude API and measure response time
        start_time = time.time()
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        response_time_ms = int((time.time() - start_time) * 1000)

        response_text = message.content[0].text

        # Log the conversation
        try:
            ChatLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                session_id=session_id,
                user_message=user_message,
                ai_response=response_text,
                ip_hash=ip_hash,
                response_time_ms=response_time_ms
            )
        except Exception as log_error:
            logger.warning(f"Failed to log chat: {log_error}")

        return JsonResponse({
            'response': response_text,
            'is_ai': True
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return JsonResponse({
            'response': "I'm having trouble right now. Please try again or email contact@realjobsrealpeople.net for help.",
            'is_ai': False
        })
