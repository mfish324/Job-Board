from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from .models import Job, UserProfile, JobApplication
from .forms import JobSeekerSignUpForm, EmployerSignUpForm, JobPostForm, JobApplicationForm
from .forms import (JobSeekerSignUpForm, EmployerSignUpForm, JobPostForm, 
                   JobApplicationForm, JobSeekerProfileForm, EmployerProfileForm)


# Your existing views stay the same
def home(request):
    recent_jobs = Job.objects.filter(is_active=True).order_by('-posted_date')[:5]
    total_jobs = Job.objects.filter(is_active=True).count()
    context = {
        'recent_jobs': recent_jobs,
        'total_jobs': total_jobs
    }
    return render(request, 'jobs/home.html', context)

def job_list(request):
    jobs = Job.objects.filter(is_active=True)
    search_query = request.GET.get('search', '')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) | 
            Q(company__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    jobs = jobs.order_by('-posted_date')
    context = {
        'jobs': jobs,
        'search_query': search_query
    }
    return render(request, 'jobs/job_list.html', context)

def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    user_has_applied = False
    
    if request.user.is_authenticated:
        user_has_applied = JobApplication.objects.filter(
            job=job, 
            applicant=request.user
        ).exists()
    
    context = {
        'job': job,
        'user_has_applied': user_has_applied
    }
    return render(request, 'jobs/job_detail.html', context)

# New authentication views
def signup_choice(request):
    return render(request, 'jobs/signup_choice.html')

def jobseeker_signup(request):
    if request.method == 'POST':
        form = JobSeekerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = JobSeekerSignUpForm()
    return render(request, 'jobs/signup.html', {'form': form, 'user_type': 'Job Seeker'})

def employer_signup(request):
    if request.method == 'POST':
        form = EmployerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, 'Employer account created successfully!')
            return redirect('employer_dashboard')
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
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'job_seeker':
        user_applications = JobApplication.objects.filter(applicant=request.user).order_by('-applied_date')
    
    context = {
        'user_applications': user_applications
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
        response = HttpResponse(resume.file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{application.applicant.username}_resume.pdf"'
        return response
    else:
        messages.error(request, 'No resume available for this applicant.')
        return redirect('employer_dashboard')

def privacy_policy(request):
    return render(request, 'jobs/privacy_policy.html')

def terms_of_service(request):
    return render(request, 'jobs/terms.html')