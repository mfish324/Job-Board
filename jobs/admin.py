from django.contrib import admin
from .models import Job, UserProfile, JobApplication


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'posted_by', 'is_active', 'posted_date')
    list_filter = ('is_active', 'posted_date', 'location')
    search_fields = ('title', 'company', 'description', 'location')
    date_hierarchy = 'posted_date'
    list_editable = ('is_active',)
    readonly_fields = ('posted_date',)
    fieldsets = (
        ('Job Information', {
            'fields': ('title', 'company', 'description', 'location', 'salary')
        }),
        ('Status & Meta', {
            'fields': ('is_active', 'posted_by', 'posted_date')
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'phone', 'company_name', 'experience_years')
    list_filter = ('user_type',)
    search_fields = ('user__username', 'user__email', 'company_name', 'skills')
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'user_type', 'phone')
        }),
        ('Job Seeker Details', {
            'fields': ('resume', 'skills', 'experience_years'),
            'classes': ('collapse',)
        }),
        ('Employer Details', {
            'fields': ('company_name', 'company_logo', 'company_website', 'company_description'),
            'classes': ('collapse',)
        }),
    )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'job', 'status', 'applied_date')
    list_filter = ('status', 'applied_date')
    search_fields = ('applicant__username', 'job__title', 'job__company')
    date_hierarchy = 'applied_date'
    list_editable = ('status',)
    readonly_fields = ('applied_date',)
    fieldsets = (
        ('Application Details', {
            'fields': ('job', 'applicant', 'applied_date', 'status')
        }),
        ('Application Content', {
            'fields': ('cover_letter', 'custom_resume')
        }),
    )