from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, Job, JobApplication


class JobSeekerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label='Phone Number',
        help_text='Enter your phone number with country code (e.g., +1234567890)',
        widget=forms.TextInput(attrs={'placeholder': '+1234567890'})
    )
    privacy_consent = forms.BooleanField(
        required=True,
        label='I agree to the Privacy Policy and Terms of Service',
        help_text='We will never sell your data or spam you.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2', 'privacy_consent')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            UserProfile.objects.create(user=user, user_type='job_seeker')
        return user

class EmployerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company_name = forms.CharField(max_length=200)
    company_website = forms.URLField(required=False)
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label='Phone Number',
        help_text='Enter your phone number with country code (e.g., +1234567890)',
        widget=forms.TextInput(attrs={'placeholder': '+1234567890'})
    )
    privacy_consent = forms.BooleanField(
        required=True,
        label='I agree to the Privacy Policy and Terms of Service'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'password1', 'password2', 'privacy_consent')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                user_type='employer',
                company_name=self.cleaned_data['company_name'],
                company_website=self.cleaned_data.get('company_website', '')
            )
        return user


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
        fields = ['phone', 'resume', 'skills', 'experience_years', 'linkedin_url']
        widgets = {
            'skills': forms.Textarea(attrs={'rows': 4, 'placeholder': 'List your skills separated by commas'}),
            'phone': forms.TextInput(attrs={'placeholder': '+1 234 567 8900'}),
            'experience_years': forms.NumberInput(attrs={'min': 0, 'max': 50}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/yourname'}),
        }
        labels = {
            'linkedin_url': 'LinkedIn Profile URL (Bonus Verification)',
        }
        help_texts = {
            'linkedin_url': 'Add your LinkedIn profile to enhance your verification status and stand out to employers.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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