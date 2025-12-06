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
