from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import os

class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=100)
    salary = models.CharField(max_length=100, blank=True)
    posted_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='posted_jobs')
    
    def __str__(self):
        return f"{self.title} at {self.company}"

class UserProfile(models.Model):
    USER_TYPE_CHOICES = (
        ('job_seeker', 'Job Seeker'),
        ('employer', 'Employer'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    
    # Job Seeker fields with file validation
    resume = models.FileField(
        upload_to='resumes/', 
        blank=True, 
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        help_text='Upload PDF or Word document only'
    )
    skills = models.TextField(blank=True)
    experience_years = models.IntegerField(default=0)
    
    # Employer fields
    company_name = models.CharField(max_length=200, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    company_website = models.URLField(blank=True)
    company_description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.user_type}"
    
    def get_resume_filename(self):
        if self.resume:
            return os.path.basename(self.resume.name)
        return None

class JobApplication(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    applied_date = models.DateTimeField(auto_now_add=True)
    cover_letter = models.TextField(blank=True)
    custom_resume = models.FileField(
        upload_to='resumes/applications/', 
        blank=True, 
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        help_text='Upload a custom resume for this application (optional)'
    )
    status = models.CharField(max_length=20, default='pending', 
                            choices=[('pending', 'Pending'),
                                   ('reviewed', 'Reviewed'),
                                   ('accepted', 'Accepted'),
                                   ('rejected', 'Rejected')])
    
    class Meta:
        unique_together = ['job', 'applicant']
    
    def __str__(self):
        return f"{self.applicant.username} - {self.job.title}"
    
    def get_resume(self):
        """Returns custom resume if uploaded, otherwise user's default resume"""
        if self.custom_resume:
            return self.custom_resume
        elif self.applicant.userprofile.resume:
            return self.applicant.userprofile.resume
        return None
class PhoneVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phone_verification')
    phone_number = models.CharField(max_length=15)
    verification_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.phone_number} - {'Verified' if self.is_verified else 'Pending'}"
    
    def is_code_expired(self):
        from django.conf import settings
        from django.utils import timezone
        from datetime import timedelta
        expiry_time = self.created_at + timedelta(minutes=settings.VERIFICATION_CODE_EXPIRY_MINUTES)
        return timezone.now() > expiry_time

class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    verification_token = models.CharField(max_length=64, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.user.email} - {'Verified' if self.is_verified else 'Pending'}"

    def is_token_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        expiry_time = self.created_at + timedelta(hours=24)  # 24 hour expiry for email
        return timezone.now() > expiry_time

class SavedJob(models.Model):
    """Job bookmarks - allows users to save jobs for later"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by')
    saved_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'job']
        ordering = ['-saved_date']

    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"
