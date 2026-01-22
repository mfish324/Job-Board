from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.safestring import mark_safe
from .models import UserProfile, Job, JobApplication


class JobSeekerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number (Optional)',
        help_text='A verified phone number is required for full verification. Employers may not respond to applicants who are not fully verified.',
        widget=forms.TextInput(attrs={'placeholder': '+1234567890'})
    )
    sms_consent = forms.BooleanField(
        required=False,
        label=mark_safe('By providing my phone number, I agree to receive SMS notifications about <strong>job application updates and account alerts</strong> from Real Jobs Real People. Message frequency varies. Message & data rates may apply. Reply STOP to opt out at any time. <a href="/privacy-policy/" target="_blank">Privacy Policy</a>.'),
    )
    privacy_consent = forms.BooleanField(
        required=True,
        label='I agree to the Privacy Policy and Terms of Service',
        help_text='We will never sell your data or spam you.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'sms_consent', 'password1', 'password2', 'privacy_consent')

    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number', '').strip()
        sms_consent = cleaned_data.get('sms_consent')

        # If phone number is provided, SMS consent is required
        if phone_number and not sms_consent:
            self.add_error('sms_consent', 'You must agree to receive SMS messages if you provide a phone number. Without SMS consent, we cannot verify your phone number.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                user_type='job_seeker',
                sms_consent=self.cleaned_data.get('sms_consent', False)
            )
        return user

class EmployerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company_name = forms.CharField(max_length=200)
    company_website = forms.URLField(required=False)
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number (Optional)',
        help_text='A verified phone number is recommended for full account verification.',
        widget=forms.TextInput(attrs={'placeholder': '+1234567890'})
    )
    sms_consent = forms.BooleanField(
        required=False,
        label=mark_safe('By providing my phone number, I agree to receive SMS notifications about <strong>job posting updates and account alerts</strong> from Real Jobs Real People. Message frequency varies. Message & data rates may apply. Reply STOP to opt out at any time. <a href="/privacy-policy/" target="_blank">Privacy Policy</a>.'),
    )
    privacy_consent = forms.BooleanField(
        required=True,
        label='I agree to the Privacy Policy and Terms of Service'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'sms_consent', 'password1', 'password2', 'privacy_consent')

    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number', '').strip()
        sms_consent = cleaned_data.get('sms_consent')

        # If phone number is provided, SMS consent is required
        if phone_number and not sms_consent:
            self.add_error('sms_consent', 'You must agree to receive SMS messages if you provide a phone number. Without SMS consent, we cannot verify your phone number.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                user_type='employer',
                company_name=self.cleaned_data['company_name'],
                company_website=self.cleaned_data.get('company_website', ''),
                sms_consent=self.cleaned_data.get('sms_consent', False)
            )
        return user


class RecruiterSignUpForm(UserCreationForm):
    """Sign up form for recruiters"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number (Optional)',
        help_text='A verified phone number is recommended for full account verification.',
        widget=forms.TextInput(attrs={'placeholder': '+1234567890'})
    )
    is_independent_recruiter = forms.BooleanField(
        required=False,
        label='I am an independent recruiter',
        help_text='Check this if you work independently without a recruiting agency'
    )
    agency_name = forms.CharField(
        max_length=200,
        required=False,
        label='Agency/Company Name',
        help_text='The name of your recruiting agency or employer (leave blank if independent)'
    )
    agency_website = forms.URLField(
        required=False,
        label='Agency/Company Website'
    )
    linkedin_url = forms.URLField(
        required=True,
        label='Your LinkedIn Profile URL',
        help_text='Required for recruiter verification',
        widget=forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/yourname'})
    )
    sms_consent = forms.BooleanField(
        required=False,
        label=mark_safe('By providing my phone number, I agree to receive SMS notifications about <strong>candidate updates and account alerts</strong> from Real Jobs Real People. Message frequency varies. Message & data rates may apply. Reply STOP to opt out at any time. <a href="/privacy-policy/" target="_blank">Privacy Policy</a>.'),
    )
    privacy_consent = forms.BooleanField(
        required=True,
        label='I agree to the Privacy Policy and Terms of Service'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number',
                  'is_independent_recruiter', 'agency_name', 'agency_website', 'linkedin_url',
                  'sms_consent', 'password1', 'password2', 'privacy_consent')

    def clean(self):
        cleaned_data = super().clean()
        is_independent = cleaned_data.get('is_independent_recruiter')
        agency_name = cleaned_data.get('agency_name')
        phone_number = cleaned_data.get('phone_number', '').strip()
        sms_consent = cleaned_data.get('sms_consent')

        # If not independent, agency name is required
        if not is_independent and not agency_name:
            self.add_error('agency_name', 'Agency name is required unless you are an independent recruiter.')

        # If phone number is provided, SMS consent is required
        if phone_number and not sms_consent:
            self.add_error('sms_consent', 'You must agree to receive SMS messages if you provide a phone number. Without SMS consent, we cannot verify your phone number.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                user_type='recruiter',
                is_independent_recruiter=self.cleaned_data.get('is_independent_recruiter', False),
                agency_name=self.cleaned_data.get('agency_name', ''),
                agency_website=self.cleaned_data.get('agency_website', ''),
                recruiter_linkedin_url=self.cleaned_data['linkedin_url'],
                is_recruiter_approved=False,  # Requires admin approval
                sms_consent=self.cleaned_data.get('sms_consent', False)
            )
        return user


class RecruiterProfileForm(forms.ModelForm):
    """Profile form for recruiters to edit their information"""
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ['is_independent_recruiter', 'agency_name', 'agency_website',
                  'recruiter_linkedin_url', 'phone']
        widgets = {
            'agency_website': forms.URLInput(attrs={'placeholder': 'https://yourcompany.com'}),
            'recruiter_linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/yourname'}),
            'phone': forms.TextInput(attrs={'placeholder': '+1 234 567 8900'}),
        }
        labels = {
            'is_independent_recruiter': 'I am an independent recruiter',
            'agency_name': 'Agency/Company Name',
            'agency_website': 'Agency/Company Website',
            'recruiter_linkedin_url': 'Your LinkedIn Profile URL',
            'phone': 'Phone Number',
        }
        help_texts = {
            'is_independent_recruiter': 'Check this if you work independently without a recruiting agency',
            'recruiter_linkedin_url': 'Required for recruiter verification',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def clean(self):
        cleaned_data = super().clean()
        is_independent = cleaned_data.get('is_independent_recruiter')
        agency_name = cleaned_data.get('agency_name')

        if not is_independent and not agency_name:
            self.add_error('agency_name', 'Agency name is required unless you are an independent recruiter.')

        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
            profile.save()
        return profile


class JobPostForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'company', 'location', 'salary', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 8}),
        }

class JobSeekerProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ['phone', 'resume', 'skills', 'experience_years', 'linkedin_url',
                  'desired_title', 'location', 'bio', 'profile_searchable', 'allow_recruiter_contact']
        widgets = {
            'skills': forms.Textarea(attrs={'rows': 4, 'placeholder': 'List your skills separated by commas'}),
            'phone': forms.TextInput(attrs={'placeholder': '+1 234 567 8900'}),
            'experience_years': forms.NumberInput(attrs={'min': 0, 'max': 50}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/yourname'}),
            'desired_title': forms.TextInput(attrs={'placeholder': 'e.g., Software Engineer, Marketing Manager'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g., Chicago, IL'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Brief summary about yourself and your career goals...'}),
        }
        labels = {
            'linkedin_url': 'LinkedIn Profile URL (Bonus Verification)',
            'desired_title': 'Desired Job Title',
            'location': 'Your Location',
            'bio': 'About Me',
            'profile_searchable': 'Allow employers to find my profile',
            'allow_recruiter_contact': 'Allow verified recruiters to contact me',
        }
        help_texts = {
            'linkedin_url': 'Add your LinkedIn profile to enhance your verification status and stand out to employers.',
            'profile_searchable': 'When enabled, employers can discover your profile when searching for candidates.',
            'allow_recruiter_contact': 'When enabled, verified recruiters can view your profile and reach out about job opportunities.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use mark_safe to allow bold text in labels
        self.fields['profile_searchable'].label = mark_safe('Allow <strong>employers</strong> to find my profile')
        self.fields['allow_recruiter_contact'].label = mark_safe('Allow verified <strong>recruiters</strong> to contact me')
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            # Update user fields
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
            profile.save()
        return profile

class EmployerProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ['company_name', 'company_logo', 'company_website', 'company_linkedin', 'company_description', 'phone']
        widgets = {
            'company_description': forms.Textarea(attrs={'rows': 4}),
            'company_linkedin': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/company/yourcompany'}),
        }
        labels = {
            'company_linkedin': 'Company LinkedIn Page',
        }
        help_texts = {
            'company_linkedin': 'Add your company LinkedIn page to build trust with job seekers.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
            profile.save()
        return profile

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['cover_letter', 'custom_resume']
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'rows': 6, 
                'placeholder': 'Tell the employer why you\'re a great fit for this position...'
            })
        }
        labels = {
            'custom_resume': 'Upload Resume (optional - uses your profile resume if not provided)'
        }