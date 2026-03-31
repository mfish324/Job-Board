from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.conf import settings
import os

class Job(models.Model):
    # Job type choices
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('internship', 'Internship'),
        ('freelance', 'Freelance'),
    ]

    # Experience level choices
    EXPERIENCE_LEVEL_CHOICES = [
        ('entry', 'Entry Level'),
        ('mid', 'Mid Level'),
        ('senior', 'Senior Level'),
        ('lead', 'Lead/Manager'),
        ('executive', 'Executive'),
    ]

    # Remote status choices
    REMOTE_STATUS_CHOICES = [
        ('on_site', 'On-site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    ]

    # Default expiration period in days
    DEFAULT_EXPIRATION_DAYS = 60

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=100)
    salary = models.CharField(max_length=100, blank=True)
    posted_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='posted_jobs')

    # New fields for job type, experience, and remote status
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, blank=True)
    remote_status = models.CharField(max_length=20, choices=REMOTE_STATUS_CHOICES, default='on_site')
    application_deadline = models.DateField(null=True, blank=True, help_text='Optional deadline for applications')

    # Expiration fields
    expires_at = models.DateTimeField(null=True, blank=True, help_text='When this job listing expires')
    last_refreshed = models.DateTimeField(null=True, blank=True, help_text='When the employer last confirmed this job is still active')

    def __str__(self):
        return f"{self.title} at {self.company}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('job_detail', args=[self.pk])

    def save(self, *args, **kwargs):
        # Set expiration date on creation if not already set
        if not self.pk and not self.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=self.DEFAULT_EXPIRATION_DAYS)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if the job listing has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def days_until_expiration(self):
        """Get the number of days until this job expires"""
        if not self.expires_at:
            return None
        from django.utils import timezone
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def refresh_listing(self, days=None):
        """Refresh/extend the job listing by a given number of days"""
        from django.utils import timezone
        from datetime import timedelta
        if days is None:
            days = self.DEFAULT_EXPIRATION_DAYS
        self.expires_at = timezone.now() + timedelta(days=days)
        self.last_refreshed = timezone.now()
        self.save()

    def is_expiring_soon(self, days=14):
        """Check if the job is expiring within the specified number of days"""
        remaining = self.days_until_expiration()
        if remaining is None:
            return False
        return remaining <= days and remaining > 0

class UserProfile(models.Model):
    USER_TYPE_CHOICES = (
        ('job_seeker', 'Job Seeker'),
        ('employer', 'Employer'),
        ('recruiter', 'Recruiter'),
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
    linkedin_url = models.URLField(
        blank=True,
        help_text='Your LinkedIn profile URL (e.g., https://linkedin.com/in/yourname)'
    )

    # Candidate search fields
    desired_title = models.CharField(max_length=200, blank=True, help_text='Job title you are looking for')
    location = models.CharField(max_length=100, blank=True, help_text='Your location (city, state)')
    profile_searchable = models.BooleanField(
        default=True,
        help_text='Allow employers to find your profile in candidate search'
    )
    bio = models.TextField(blank=True, help_text='Brief summary about yourself')

    # Employer fields
    company_name = models.CharField(max_length=200, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    company_website = models.URLField(blank=True)
    company_description = models.TextField(blank=True)
    company_linkedin = models.URLField(blank=True, help_text='Company LinkedIn page URL')

    # Recruiter fields
    is_independent_recruiter = models.BooleanField(
        default=False,
        help_text='Check if you are an independent recruiter without a company affiliation'
    )
    agency_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Name of your recruiting agency or company'
    )
    agency_website = models.URLField(blank=True, help_text='Your agency or company website')
    recruiter_linkedin_url = models.URLField(
        blank=True,
        help_text='Your personal LinkedIn profile URL (required for recruiter verification)'
    )
    is_recruiter_approved = models.BooleanField(
        default=False,
        help_text='Admin approval status for recruiter accounts'
    )
    recruiter_approved_at = models.DateTimeField(null=True, blank=True)

    # Job seeker opt-in for recruiter contact
    allow_recruiter_contact = models.BooleanField(
        default=False,
        help_text='Allow verified recruiters to contact you about job opportunities'
    )

    # SMS consent for Twilio compliance
    sms_consent = models.BooleanField(
        default=False,
        help_text='User has consented to receive SMS notifications'
    )

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

    def get_resume_filename(self):
        if self.resume:
            return os.path.basename(self.resume.name)
        return None

    def is_phone_verified(self):
        """Check if user has verified their phone"""
        try:
            return self.user.phone_verification.is_verified
        except:
            return False

    def is_email_verified(self):
        """Check if user has verified their email"""
        try:
            return self.user.email_verification.is_verified
        except:
            return False

    def is_verified(self):
        """Check if user has verified at least phone OR email"""
        return self.is_phone_verified() or self.is_email_verified()

    def has_linkedin(self):
        """Check if user has added their LinkedIn profile"""
        return bool(self.linkedin_url)

    def get_verification_level(self):
        """
        Returns verification level:
        - 'none': No verification
        - 'basic': Email OR Phone verified
        - 'enhanced': Email AND Phone verified
        - 'complete': Email AND Phone AND LinkedIn
        """
        phone = self.is_phone_verified()
        email = self.is_email_verified()
        linkedin = self.has_linkedin()

        if phone and email and linkedin:
            return 'complete'
        elif phone and email:
            return 'enhanced'
        elif phone or email:
            return 'basic'
        return 'none'

    def get_verification_badges(self):
        """Returns list of verification badges for display"""
        badges = []
        if self.is_email_verified():
            badges.append({'type': 'email', 'label': 'Email Verified', 'icon': 'bi-envelope-check', 'color': 'success'})
        if self.is_phone_verified():
            badges.append({'type': 'phone', 'label': 'Phone Verified', 'icon': 'bi-phone-fill', 'color': 'success'})
        if self.has_linkedin():
            badges.append({'type': 'linkedin', 'label': 'LinkedIn Added', 'icon': 'bi-linkedin', 'color': 'primary'})
        return badges

    # Recruiter-specific methods
    def is_recruiter_verified(self):
        """Check if recruiter meets all verification requirements"""
        if self.user_type != 'recruiter':
            return False
        return (
            self.is_phone_verified() and
            self.is_email_verified() and
            bool(self.recruiter_linkedin_url) and
            (bool(self.agency_name) or self.is_independent_recruiter) and
            self.is_recruiter_approved
        )

    def get_recruiter_display_name(self):
        """Get the display name for recruiter (agency/company name or personal name)"""
        if self.user_type != 'recruiter':
            return None
        if self.is_independent_recruiter:
            return f"{self.user.get_full_name()} (Independent Recruiter)"
        return self.agency_name or self.user.get_full_name()

    def get_recruiter_verification_status(self):
        """Returns dict with recruiter verification status for each requirement"""
        if self.user_type != 'recruiter':
            return None
        return {
            'phone': self.is_phone_verified(),
            'email': self.is_email_verified(),
            'linkedin': bool(self.recruiter_linkedin_url),
            'agency': bool(self.agency_name) or self.is_independent_recruiter,
            'approved': self.is_recruiter_approved,
        }


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

    # ATS Fields
    current_stage = models.ForeignKey(
        'HiringStage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applications'
    )

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

    def get_average_rating(self):
        """Get average rating across all raters"""
        ratings = self.ratings.all()
        if not ratings:
            return None
        total = sum(r.overall_rating for r in ratings)
        return round(total / len(ratings), 1)

    def get_tags(self):
        """Get all tags assigned to this application"""
        return [ta.tag for ta in self.tag_assignments.select_related('tag').all()]
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


class TwoFactorCode(models.Model):
    """Stores 2FA codes sent during login"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_codes')
    code = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - 2FA - {'Used' if self.is_used else 'Active'}"

    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        expiry_time = self.created_at + timedelta(minutes=5)  # 5 minute expiry for 2FA
        return timezone.now() > expiry_time

    class Meta:
        ordering = ['-created_at']


class SiteVisit(models.Model):
    """Tracks site visits for admin notifications"""
    ip_address = models.GenericIPAddressField()
    path = models.CharField(max_length=500)
    user_agent = models.TextField(blank=True)
    referer = models.URLField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    notified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ip_address} - {self.path} - {self.visited_at}"

    class Meta:
        ordering = ['-visited_at']

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


# ============================================
# APPLICANT TRACKING SYSTEM (ATS) MODELS
# ============================================

class HiringStage(models.Model):
    """Custom hiring pipeline stages per employer"""
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default='#6c757d')  # Hex color code
    employer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hiring_stages')
    is_default = models.BooleanField(default=False)  # Default stages created for new employers
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ['name', 'employer']

    def __str__(self):
        return f"{self.name} ({self.employer.username})"

    @classmethod
    def get_default_stages(cls):
        """Returns default stage definitions for new employers"""
        return [
            {'name': 'Applied', 'order': 0, 'color': '#6c757d'},
            {'name': 'Screening', 'order': 1, 'color': '#17a2b8'},
            {'name': 'Interview', 'order': 2, 'color': '#ffc107'},
            {'name': 'Offer', 'order': 3, 'color': '#28a745'},
            {'name': 'Hired', 'order': 4, 'color': '#007bff'},
            {'name': 'Rejected', 'order': 5, 'color': '#dc3545'},
        ]

    @classmethod
    def create_default_stages_for_employer(cls, employer):
        """Create default hiring stages for a new employer"""
        stages = []
        for stage_def in cls.get_default_stages():
            stage, created = cls.objects.get_or_create(
                name=stage_def['name'],
                employer=employer,
                defaults={
                    'order': stage_def['order'],
                    'color': stage_def['color'],
                    'is_default': True
                }
            )
            stages.append(stage)
        return stages


class ApplicationStageHistory(models.Model):
    """Track stage transitions for applications"""
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='stage_history')
    stage = models.ForeignKey(HiringStage, on_delete=models.SET_NULL, null=True, related_name='applications_history')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = 'Application stage histories'

    def __str__(self):
        return f"{self.application} -> {self.stage.name if self.stage else 'Unknown'}"


class ApplicationNote(models.Model):
    """Internal notes on applications (visible only to employer team)"""
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_notes')
    content = models.TextField()
    is_private = models.BooleanField(default=True)  # Private notes visible only to author
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note by {self.author.username} on {self.application}"


class ApplicationRating(models.Model):
    """Rating/scoring for applications"""
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Below Average'),
        (3, '3 - Average'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    ]

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='ratings')
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_ratings')
    overall_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    skills_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    experience_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    culture_fit_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['application', 'rater']
        ordering = ['-created_at']

    def __str__(self):
        return f"Rating {self.overall_rating}/5 by {self.rater.username} for {self.application}"

    @property
    def average_rating(self):
        """Calculate average of all rating categories"""
        ratings = [self.overall_rating]
        if self.skills_rating:
            ratings.append(self.skills_rating)
        if self.experience_rating:
            ratings.append(self.experience_rating)
        if self.culture_fit_rating:
            ratings.append(self.culture_fit_rating)
        return sum(ratings) / len(ratings)


class ApplicationTag(models.Model):
    """Tags/labels for categorizing applications"""
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    employer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_tags')

    class Meta:
        unique_together = ['name', 'employer']

    def __str__(self):
        return self.name


class ApplicationTagAssignment(models.Model):
    """Many-to-many relationship between applications and tags"""
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(ApplicationTag, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['application', 'tag']

    def __str__(self):
        return f"{self.tag.name} on {self.application}"


# ============================================
# PHASE 2: EMAIL TEMPLATES & NOTIFICATIONS
# ============================================

class EmailTemplate(models.Model):
    """Reusable email templates for employer communication"""
    TEMPLATE_TYPES = [
        ('application_received', 'Application Received'),
        ('stage_change', 'Stage Change'),
        ('interview_invite', 'Interview Invitation'),
        ('offer', 'Job Offer'),
        ('rejection', 'Rejection'),
        ('custom', 'Custom'),
    ]

    employer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_templates')
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, default='custom')
    subject = models.CharField(max_length=200)
    body = models.TextField(help_text='Use placeholders: {{applicant_name}}, {{job_title}}, {{company_name}}, {{stage_name}}')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['template_type', 'name']
        unique_together = ['employer', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render(self, context):
        """Render the template with the given context"""
        subject = self.subject
        body = self.body

        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return subject, body

    @classmethod
    def get_default_templates(cls):
        """Returns default template definitions for new employers"""
        return [
            {
                'name': 'Application Received',
                'template_type': 'application_received',
                'subject': 'Application Received - {{job_title}} at {{company_name}}',
                'body': '''Dear {{applicant_name}},

Thank you for applying for the {{job_title}} position at {{company_name}}.

We have received your application and our team will review it shortly. If your qualifications match our requirements, we will contact you to discuss the next steps.

Thank you for your interest in joining our team.

Best regards,
{{company_name}} Hiring Team'''
            },
            {
                'name': 'Interview Invitation',
                'template_type': 'interview_invite',
                'subject': 'Interview Invitation - {{job_title}} at {{company_name}}',
                'body': '''Dear {{applicant_name}},

Congratulations! After reviewing your application for the {{job_title}} position, we would like to invite you for an interview.

Please reply to this email with your availability for the coming week, and we will schedule a convenient time.

We look forward to speaking with you.

Best regards,
{{company_name}} Hiring Team'''
            },
            {
                'name': 'Job Offer',
                'template_type': 'offer',
                'subject': 'Job Offer - {{job_title}} at {{company_name}}',
                'body': '''Dear {{applicant_name}},

We are pleased to extend an offer for the {{job_title}} position at {{company_name}}.

We were impressed with your qualifications and believe you would be a valuable addition to our team. Please find the offer details attached.

Please let us know your decision within the next 5 business days.

Best regards,
{{company_name}} Hiring Team'''
            },
            {
                'name': 'Application Update',
                'template_type': 'stage_change',
                'subject': 'Application Update - {{job_title}} at {{company_name}}',
                'body': '''Dear {{applicant_name}},

We wanted to update you on the status of your application for the {{job_title}} position at {{company_name}}.

Your application has been moved to the {{stage_name}} stage of our hiring process.

We will be in touch with more information soon.

Best regards,
{{company_name}} Hiring Team'''
            },
            {
                'name': 'Application Rejected',
                'template_type': 'rejection',
                'subject': 'Application Status - {{job_title}} at {{company_name}}',
                'body': '''Dear {{applicant_name}},

Thank you for your interest in the {{job_title}} position at {{company_name}} and for taking the time to apply.

After careful consideration, we have decided to move forward with other candidates whose qualifications more closely match our current needs.

We encourage you to apply for future openings that match your skills and experience. We wish you the best in your job search.

Best regards,
{{company_name}} Hiring Team'''
            },
        ]

    @classmethod
    def create_default_templates_for_employer(cls, employer):
        """Create default email templates for a new employer"""
        templates = []
        for template_def in cls.get_default_templates():
            template, created = cls.objects.get_or_create(
                name=template_def['name'],
                employer=employer,
                defaults={
                    'template_type': template_def['template_type'],
                    'subject': template_def['subject'],
                    'body': template_def['body']
                }
            )
            templates.append(template)
        return templates


class Notification(models.Model):
    """In-app notifications for users"""
    NOTIFICATION_TYPES = [
        ('application_received', 'New Application'),
        ('application_viewed', 'Application Viewed'),
        ('stage_change', 'Stage Changed'),
        ('message_received', 'Message Received'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('offer_received', 'Offer Received'),
        ('application_rejected', 'Application Rejected'),
        ('general', 'General'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='general')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)  # URL to relevant page
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional references
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"

    @classmethod
    def create_notification(cls, recipient, notification_type, title, message, link='', application=None, job=None):
        """Helper method to create a notification"""
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            application=application,
            job=job
        )


class EmailLog(models.Model):
    """Log of all emails sent through the system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_emails')
    recipient_email = models.EmailField()
    recipient_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_emails')
    subject = models.CharField(max_length=200)
    body = models.TextField()
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    application = models.ForeignKey(JobApplication, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Email to {self.recipient_email} - {self.subject[:50]}"


class Message(models.Model):
    """Direct messages between employers and applicants"""
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} - {self.application}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save()


# ============================================
# PHASE 3: TEAM COLLABORATION & PERMISSIONS
# ============================================

class EmployerTeam(models.Model):
    """Team/organization for employer accounts"""
    name = models.CharField(max_length=200)
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='owned_team')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_members(self):
        """Get all team members including owner"""
        return TeamMember.objects.filter(team=self).select_related('user')

    def get_member_count(self):
        """Get total number of team members including owner"""
        return self.members.count() + 1  # +1 for owner

    def is_member(self, user):
        """Check if user is a member of this team (including owner)"""
        if user == self.owner:
            return True
        return self.members.filter(user=user, is_active=True).exists()

    def get_user_role(self, user):
        """Get the role of a user in this team"""
        if user == self.owner:
            return 'owner'
        try:
            member = self.members.get(user=user)
            return member.role
        except TeamMember.DoesNotExist:
            return None


class TeamMember(models.Model):
    """Team member with role-based permissions"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),           # Full access, can manage team
        ('recruiter', 'Recruiter'),   # Can manage applications, send emails
        ('reviewer', 'Reviewer'),      # Can view applications, add notes/ratings
        ('viewer', 'Viewer'),          # Read-only access
    ]

    team = models.ForeignKey(EmployerTeam, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reviewer')
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_invitations')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['team', 'user']
        ordering = ['role', 'joined_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} at {self.team.name}"

    def can_manage_team(self):
        """Check if member can add/remove team members"""
        return self.role == 'admin'

    def can_manage_applications(self):
        """Check if member can move stages, send emails"""
        return self.role in ['admin', 'recruiter']

    def can_review_applications(self):
        """Check if member can add notes and ratings"""
        return self.role in ['admin', 'recruiter', 'reviewer']

    def can_view_applications(self):
        """Check if member can view application details"""
        return self.role in ['admin', 'recruiter', 'reviewer', 'viewer']


class TeamInvitation(models.Model):
    """Pending team invitations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    team = models.ForeignKey(EmployerTeam, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=TeamMember.ROLE_CHOICES, default='reviewer')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_invitations_sent')
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_invitations')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation to {self.email} for {self.team.name}"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_valid(self):
        return self.status == 'pending' and not self.is_expired()

    @classmethod
    def create_invitation(cls, team, email, role, invited_by, days_valid=7):
        """Create a new invitation with auto-generated token"""
        import secrets
        from django.utils import timezone
        from datetime import timedelta

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=days_valid)

        return cls.objects.create(
            team=team,
            email=email,
            role=role,
            invited_by=invited_by,
            token=token,
            expires_at=expires_at
        )


class ActivityLog(models.Model):
    """Audit log for team activities"""
    ACTION_TYPES = [
        ('application_viewed', 'Viewed Application'),
        ('stage_changed', 'Changed Stage'),
        ('note_added', 'Added Note'),
        ('rating_added', 'Added Rating'),
        ('email_sent', 'Sent Email'),
        ('message_sent', 'Sent Message'),
        ('tag_added', 'Added Tag'),
        ('tag_removed', 'Removed Tag'),
        ('member_invited', 'Invited Team Member'),
        ('member_removed', 'Removed Team Member'),
        ('job_posted', 'Posted Job'),
        ('job_edited', 'Edited Job'),
    ]

    team = models.ForeignKey(EmployerTeam, on_delete=models.CASCADE, related_name='activity_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    description = models.TextField()
    application = models.ForeignKey(JobApplication, on_delete=models.SET_NULL, null=True, blank=True)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activity logs'

    def __str__(self):
        return f"{self.user.username if self.user else 'System'}: {self.get_action_type_display()}"

    @classmethod
    def log_activity(cls, team, user, action_type, description, application=None, job=None):
        """Helper to create activity log entry"""
        return cls.objects.create(
            team=team,
            user=user,
            action_type=action_type,
            description=description,
            application=application,
            job=job
        )


class ChatLog(models.Model):
    """Log of chatbot conversations for review and improvement"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=64, blank=True, help_text="Anonymous session identifier")
    user_message = models.TextField()
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True, help_text="Hashed IP for anonymous tracking")
    response_time_ms = models.IntegerField(null=True, blank=True, help_text="API response time in milliseconds")
    was_helpful = models.BooleanField(null=True, blank=True, help_text="User feedback if provided")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Chat Log'
        verbose_name_plural = 'Chat Logs'

    def __str__(self):
        user_str = self.user.username if self.user else f"Anonymous ({self.session_id[:8]}...)"
        return f"{user_str}: {self.user_message[:50]}..."


# =============================================================================
# HIRING ACTIVITY SCORE (HAS) MODELS
# =============================================================================

class Company(models.Model):
    """
    Normalized company entity for aggregating company-level data.
    Links to both verified employer accounts and scraped listings.
    """
    name = models.CharField(max_length=255, unique=True)
    normalized_name = models.CharField(max_length=255, db_index=True)

    # Link to verified employer if claimed
    verified_employer = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_company',
        limit_choices_to={'userprofile__user_type': 'employer'}
    )

    # Company metadata
    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True, help_text="e.g., 51-200, 1001-5000")
    headquarters = models.CharField(max_length=200, blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Normalize company name for matching
        self.normalized_name = self.name.lower().strip()
        super().save(*args, **kwargs)

    @classmethod
    def find_or_create(cls, company_name, threshold=0.85):
        """
        Find existing company by fuzzy match or create new one.
        Returns (company, created) tuple.
        """
        from difflib import SequenceMatcher
        normalized = company_name.lower().strip()

        # Exact match first
        try:
            return cls.objects.get(normalized_name=normalized), False
        except cls.DoesNotExist:
            pass

        # Fuzzy match against existing companies
        for company in cls.objects.all():
            ratio = SequenceMatcher(None, normalized, company.normalized_name).ratio()
            if ratio >= threshold:
                return company, False

        # Create new
        return cls.objects.create(name=company_name), True


class ScrapedJobListing(models.Model):
    """
    Raw job listing data scraped from external ATS systems.
    These are market-observed roles, not directly posted by employers.
    """
    SOURCE_ATS_CHOICES = [
        ('greenhouse', 'Greenhouse'),
        ('lever', 'Lever'),
        ('workday', 'Workday'),
        ('icims', 'iCIMS'),
        ('taleo', 'Taleo'),
        ('bamboohr', 'BambooHR'),
        ('ashby', 'Ashby'),
        ('jobvite', 'Jobvite'),
        ('smartrecruiters', 'SmartRecruiters'),
        # genzjobs sources
        ('remotive', 'Remotive'),
        ('usajobs', 'USAJobs'),
        ('jsearch', 'JSearch'),
        ('arbeitnow', 'Arbeitnow'),
        ('jobicy', 'Jobicy'),
        ('whoishiring', 'Who Is Hiring'),
        ('direct_ats', 'Direct ATS'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('stale', 'Stale'),
        ('closed', 'Closed'),
        ('published', 'Published to Board'),
    ]

    JOB_CATEGORY_CHOICES = [
        ('engineering', 'Engineering/Tech'),
        ('healthcare', 'Healthcare'),
        ('retail', 'Retail'),
        ('finance', 'Finance'),
        ('sales', 'Sales'),
        ('marketing', 'Marketing'),
        ('operations', 'Operations'),
        ('hr', 'Human Resources'),
        ('legal', 'Legal'),
        ('executive', 'Executive'),
        ('other', 'Other'),
    ]

    # genzjobs integration
    genzjobs_id = models.CharField(
        max_length=50, unique=True, null=True, blank=True, db_index=True,
        help_text='CUID from genzjobs job_listings table'
    )

    # Source identification
    source_ats = models.CharField(max_length=50, choices=SOURCE_ATS_CHOICES)
    source_url = models.URLField(max_length=500, db_index=True)
    external_requisition_id = models.CharField(max_length=100, blank=True, db_index=True)

    # Company info
    company_name = models.CharField(max_length=255, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scraped_listings'
    )
    company_careers_url = models.URLField(max_length=500, blank=True)

    # Job details
    title = models.CharField(max_length=300)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True)

    # Structured fields
    job_type = models.CharField(max_length=50, blank=True)
    experience_level = models.CharField(max_length=50, blank=True)
    remote_status = models.CharField(max_length=50, blank=True)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='USD')
    department = models.CharField(max_length=100, blank=True)
    job_category = models.CharField(max_length=50, choices=JOB_CATEGORY_CHOICES, default='other')

    # Scoring-relevant fields (populated from genzjobs)
    has_requirements = models.BooleanField(default=False)
    has_benefits = models.BooleanField(default=False)
    has_company_logo = models.BooleanField(default=False)
    has_company_website = models.BooleanField(default=False)
    classification_confidence = models.FloatField(null=True, blank=True, help_text='ML classification confidence 0-1')
    skills_count = models.PositiveIntegerField(default=0)
    publisher = models.CharField(max_length=100, blank=True, help_text='Original publisher/source from genzjobs')

    # Tracking and signals
    date_first_seen = models.DateTimeField(auto_now_add=True)
    date_last_seen = models.DateTimeField(default=None, null=True, blank=True)
    date_posted_external = models.DateTimeField(null=True, blank=True)
    date_removed = models.DateTimeField(null=True, blank=True)

    # Content fingerprinting for repost detection
    description_hash = models.CharField(max_length=64, db_index=True)
    title_hash = models.CharField(max_length=64, db_index=True)
    repost_count = models.PositiveIntegerField(default=0)
    previous_listing = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reposts'
    )

    # AI-generated summary (populated on-demand via Claude Haiku)
    description_summary = models.TextField(blank=True, help_text='AI-generated concise summary of the job description')

    # Raw data storage
    raw_data = models.JSONField(default=dict, blank=True)

    # Link health tracking
    link_last_checked = models.DateTimeField(null=True, blank=True, help_text='When the source URL was last verified')
    link_status_code = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Last HTTP status code from source URL')

    # Status and publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    published_to_board = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    # Link to verified job if employer claims
    claimed_job = models.OneToOneField(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scraped_source'
    )

    class Meta:
        ordering = ['-date_last_seen']
        indexes = [
            models.Index(fields=['company_name', 'status']),
            models.Index(fields=['source_ats', 'status']),
            models.Index(fields=['date_last_seen', 'status']),
            models.Index(fields=['published_to_board', 'status']),
        ]
        verbose_name = 'Scraped Job Listing'
        verbose_name_plural = 'Scraped Job Listings'

    def __str__(self):
        return f"{self.title} at {self.company_name} ({self.source_ats})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('observed_listing_detail', args=[self.pk])

    def save(self, *args, **kwargs):
        import hashlib
        import re

        # Set date_last_seen on first save if not set
        if not self.date_last_seen:
            from django.utils import timezone
            self.date_last_seen = timezone.now()

        # Strip HTML before hashing for consistent fingerprinting
        plain_desc = re.sub(r'<[^>]+>', '', self.description) if self.description else ''
        normalized_desc = ' '.join(plain_desc.lower().split())
        self.description_hash = hashlib.sha256(normalized_desc.encode()).hexdigest()

        normalized_title = ' '.join(self.title.lower().split())
        title_company = f"{normalized_title}|{self.company_name.lower()}"
        self.title_hash = hashlib.sha256(title_company.encode()).hexdigest()

        super().save(*args, **kwargs)

    def days_since_first_seen(self):
        """Days since this listing was first observed"""
        from django.utils import timezone
        return (timezone.now() - self.date_first_seen).days

    def days_since_last_seen(self):
        """Days since this listing was last confirmed active"""
        from django.utils import timezone
        return (timezone.now() - self.date_last_seen).days

    def is_stale(self, days=7):
        """Check if listing hasn't been seen recently"""
        return self.days_since_last_seen() >= days


class HiringActivityScore(models.Model):
    """
    Computed hiring activity score for a scraped listing.
    Indicates likelihood that the job is actively being filled.
    """
    SCORE_BAND_CHOICES = [
        ('very_active', 'Very Active (80-100)'),
        ('likely_active', 'Likely Active (65-79)'),
        ('uncertain', 'Uncertain (50-64)'),
        ('low_signal', 'Low Signal (0-49)'),
    ]

    listing = models.OneToOneField(
        ScrapedJobListing,
        on_delete=models.CASCADE,
        related_name='activity_score'
    )

    # Overall score
    total_score = models.PositiveSmallIntegerField(
        default=50,
        help_text='Score from 0-100'
    )
    score_band = models.CharField(max_length=20, choices=SCORE_BAND_CHOICES, default='uncertain')

    # Detailed breakdown stored as JSON
    score_breakdown = models.JSONField(
        default=dict,
        help_text='Individual signal scores and contributions'
    )

    # Algorithm version for tracking changes
    score_version = models.PositiveSmallIntegerField(default=1)

    # Timestamps
    calculated_at = models.DateTimeField(auto_now=True)

    # Publishing status (denormalized for query performance)
    published_to_board = models.BooleanField(default=False)

    class Meta:
        ordering = ['-total_score']
        verbose_name = 'Hiring Activity Score'
        verbose_name_plural = 'Hiring Activity Scores'

    def __str__(self):
        return f"{self.listing.title}: {self.total_score} ({self.score_band})"

    def save(self, *args, **kwargs):
        from jobs.scoring.config import get_config
        config = get_config()

        # Calculate score band from config (not hardcoded thresholds)
        bands = config.get('score_bands', {})
        self.score_band = 'low_signal'  # default
        for band_name, (min_val, max_val) in bands.items():
            if min_val <= self.total_score <= max_val:
                self.score_band = band_name
                break

        # Use config's publish_threshold
        self.published_to_board = self.total_score >= config['publish_threshold']

        super().save(*args, **kwargs)

        # Sync to parent listing
        if self.listing.published_to_board != self.published_to_board:
            from django.utils import timezone
            self.listing.published_to_board = self.published_to_board
            if self.published_to_board and not self.listing.published_at:
                self.listing.published_at = timezone.now()
            self.listing.save(update_fields=['published_to_board', 'published_at'])

    def get_pip_display(self):
        """Return pip indicator string (e.g., ●●●●○)"""
        filled = min(5, max(0, self.total_score // 20))
        return '●' * filled + '○' * (5 - filled)


class CompanyHiringProfile(models.Model):
    """
    Aggregated hiring patterns at the company level.
    Updated periodically from scraped listing data.
    """
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='hiring_profile'
    )

    # Activity metrics
    total_active_listings = models.PositiveIntegerField(default=0)
    total_historical_listings = models.PositiveIntegerField(default=0)
    total_distinct_departments = models.PositiveIntegerField(default=0)

    # Lifecycle metrics
    avg_listing_lifespan_days = models.FloatField(null=True, blank=True)
    median_listing_lifespan_days = models.FloatField(null=True, blank=True)
    listing_close_rate_30d = models.FloatField(
        null=True,
        blank=True,
        help_text='Percentage of listings closed in last 30 days'
    )

    # Net job movement
    net_job_movement_30d = models.IntegerField(default=0)
    net_job_movement_90d = models.IntegerField(default=0)

    # Repost patterns
    repost_frequency = models.FloatField(
        default=0.0,
        help_text='Average reposts per listing'
    )

    # Content quality signals
    boilerplate_ratio = models.FloatField(
        default=0.0,
        help_text='Ratio of shared content across listings (0-1)'
    )
    avg_description_length = models.PositiveIntegerField(default=0)
    has_salary_info_ratio = models.FloatField(default=0.0)

    # Reputation/external signals
    reputation_score = models.FloatField(
        default=50.0,
        help_text='Composite reputation score (0-100)'
    )
    has_recent_layoffs = models.BooleanField(default=False)
    glassdoor_rating = models.FloatField(null=True, blank=True)
    linkedin_followers = models.PositiveIntegerField(null=True, blank=True)

    # Evergreen detection
    evergreen_listing_count = models.PositiveIntegerField(
        default=0,
        help_text='Listings open > 90 days with no changes'
    )

    # Timestamps
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Hiring Profile'
        verbose_name_plural = 'Company Hiring Profiles'

    def __str__(self):
        return f"{self.company.name} Hiring Profile"


class ListingFeedback(models.Model):
    """
    User feedback on scraped listings for quality improvement.
    Feeds back into scoring algorithm over time.
    """
    FEEDBACK_TYPE_CHOICES = [
        ('applied_got_response', 'Applied - Got Response'),
        ('applied_no_response', 'Applied - No Response'),
        ('listing_outdated', 'Listing Appears Outdated'),
        ('listing_spam', 'Listing is Spam/Fake'),
        ('company_not_hiring', 'Company Confirmed Not Hiring'),
        ('successfully_hired', 'Got Hired Through This'),
        ('other', 'Other'),
    ]

    listing = models.ForeignKey(
        ScrapedJobListing,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listing_feedback'
    )
    feedback_type = models.CharField(max_length=30, choices=FEEDBACK_TYPE_CHOICES)
    comment = models.TextField(blank=True)
    days_to_response = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Days until response if applicable'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Listing Feedback'
        verbose_name_plural = 'Listing Feedback'

    def __str__(self):
        return f"{self.listing.title} - {self.get_feedback_type_display()}"


# =============================================================================
# GENZJOBS UNMANAGED MODEL (read from shared Neon PostgreSQL)
# =============================================================================

class GenzjobsListing(models.Model):
    """
    Unmanaged model mapping to genzjobs `job_listings` table.
    Schema is managed by Prisma in the genzjobs project.
    Only isRjrpVerified and rjrpEmployerId are written by RJRP.
    """
    id = models.CharField(max_length=50, primary_key=True, db_column='id')

    # Core fields
    title = models.TextField(db_column='title')
    company = models.TextField(db_column='company')
    location = models.TextField(db_column='location', blank=True, null=True)
    description = models.TextField(db_column='description', blank=True, null=True)
    apply_url = models.TextField(db_column='applyUrl', blank=True, null=True)
    source = models.TextField(db_column='source')
    source_id = models.TextField(db_column='sourceId', blank=True, null=True)
    source_url = models.TextField(db_column='sourceUrl', blank=True, null=True)

    # Salary
    salary_min = models.IntegerField(db_column='salaryMin', blank=True, null=True)
    salary_max = models.IntegerField(db_column='salaryMax', blank=True, null=True)
    salary_currency = models.TextField(db_column='salaryCurrency', blank=True, null=True)

    # Classification
    job_type = models.TextField(db_column='jobType', blank=True, null=True)
    experience_level = models.TextField(db_column='experienceLevel', blank=True, null=True)
    remote = models.BooleanField(db_column='remote', default=False)
    category = models.TextField(db_column='category', blank=True, null=True)
    classification_confidence = models.FloatField(db_column='classificationConfidence', blank=True, null=True)

    # Rich content
    requirements = models.TextField(db_column='requirements', blank=True, null=True)
    benefits = models.TextField(db_column='benefits', blank=True, null=True)
    company_logo = models.TextField(db_column='companyLogo', blank=True, null=True)
    company_website = models.TextField(db_column='companyWebsite', blank=True, null=True)

    # Tags and skills (PostgreSQL text[] arrays, not JSON)
    skills = models.TextField(db_column='skills', blank=True, null=True)
    audience_tags = models.TextField(db_column='audienceTags', blank=True, null=True)

    # Status
    is_active = models.BooleanField(db_column='isActive', default=True)
    posted_at = models.DateTimeField(db_column='postedAt', blank=True, null=True)
    last_seen_at = models.DateTimeField(db_column='lastSeenAt', blank=True, null=True)
    updated_at = models.DateTimeField(db_column='updatedAt', blank=True, null=True)
    created_at = models.DateTimeField(db_column='createdAt', blank=True, null=True)

    # Publisher metadata
    publisher = models.TextField(db_column='publisher', blank=True, null=True)

    # RJRP integration fields (writable)
    is_rjrp_verified = models.BooleanField(db_column='isRjrpVerified', default=False)
    rjrp_employer_id = models.TextField(db_column='rjrpEmployerId', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'job_listings'
        verbose_name = 'genzjobs Listing'
        verbose_name_plural = 'genzjobs Listings'

    def __str__(self):
        return f"{self.title} at {self.company} ({self.source})"
