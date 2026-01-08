from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django import forms
import csv
import io
from .models import (Job, UserProfile, JobApplication, PhoneVerification, EmailVerification, SavedJob,
                     HiringStage, ApplicationStageHistory, ApplicationNote, ApplicationRating,
                     ApplicationTag, ApplicationTagAssignment, EmailTemplate, Notification,
                     EmailLog, Message, EmployerTeam, TeamMember, TeamInvitation, ActivityLog)


class CsvImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV File')


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
    change_list_template = 'admin/jobs/job/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='jobs_job_import_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == 'POST':
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']

                # Check file extension
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'Please upload a CSV file.')
                    return redirect('..')

                try:
                    # Read and decode the file
                    decoded_file = csv_file.read().decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded_file))

                    created_count = 0
                    error_count = 0
                    errors = []

                    for row_num, row in enumerate(reader, start=2):
                        try:
                            # Required fields
                            title = row.get('title', '').strip()
                            company = row.get('company', '').strip()
                            description = row.get('description', '').strip()
                            location = row.get('location', '').strip()

                            if not all([title, company, description, location]):
                                errors.append(f"Row {row_num}: Missing required field(s)")
                                error_count += 1
                                continue

                            # Optional fields
                            salary = row.get('salary', '').strip()
                            is_active = row.get('is_active', 'true').lower() in ('true', '1', 'yes')

                            Job.objects.create(
                                title=title,
                                company=company,
                                description=description,
                                location=location,
                                salary=salary,
                                is_active=is_active,
                                posted_by=request.user
                            )
                            created_count += 1

                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                            error_count += 1

                    if created_count > 0:
                        messages.success(request, f'Successfully imported {created_count} job(s).')
                    if error_count > 0:
                        messages.warning(request, f'Failed to import {error_count} row(s): {"; ".join(errors[:5])}')

                except Exception as e:
                    messages.error(request, f'Error processing CSV: {str(e)}')

                return redirect('..')
        else:
            form = CsvImportForm()

        context = {
            'form': form,
            'title': 'Import Jobs from CSV',
            'opts': self.model._meta,
        }
        return render(request, 'admin/jobs/job/csv_import.html', context)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'phone', 'company_name', 'experience_years', 'is_recruiter_approved')
    list_filter = ('user_type', 'is_recruiter_approved')
    search_fields = ('user__username', 'user__email', 'company_name', 'skills', 'agency_name')
    list_editable = ('is_recruiter_approved',)
    actions = ['approve_recruiters', 'reject_recruiters']
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'user_type', 'phone')
        }),
        ('Job Seeker Details', {
            'fields': ('resume', 'skills', 'experience_years', 'linkedin_url', 'desired_title',
                      'location', 'bio', 'profile_searchable', 'allow_recruiter_contact'),
            'classes': ('collapse',)
        }),
        ('Employer Details', {
            'fields': ('company_name', 'company_logo', 'company_website', 'company_linkedin', 'company_description'),
            'classes': ('collapse',)
        }),
        ('Recruiter Details', {
            'fields': ('is_independent_recruiter', 'agency_name', 'agency_website',
                      'recruiter_linkedin_url', 'is_recruiter_approved', 'recruiter_approved_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.action(description='Approve selected recruiters')
    def approve_recruiters(self, request, queryset):
        from django.utils import timezone
        recruiters = queryset.filter(user_type='recruiter', is_recruiter_approved=False)
        count = recruiters.update(is_recruiter_approved=True, recruiter_approved_at=timezone.now())
        self.message_user(request, f'{count} recruiter(s) approved successfully.')

    @admin.action(description='Reject/Revoke selected recruiters')
    def reject_recruiters(self, request, queryset):
        recruiters = queryset.filter(user_type='recruiter')
        count = recruiters.update(is_recruiter_approved=False, recruiter_approved_at=None)
        self.message_user(request, f'{count} recruiter(s) approval revoked.')


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

@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_verified', 'created_at', 'verified_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'verified_at', 'verification_code')
    date_hierarchy = 'created_at'


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'created_at', 'verified_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'verified_at', 'verification_token')
    date_hierarchy = 'created_at'


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ('user', 'job', 'saved_date')
    list_filter = ('saved_date',)
    search_fields = ('user__username', 'job__title', 'job__company')
    date_hierarchy = 'saved_date'
    readonly_fields = ('saved_date',)


# ============================================
# ATS ADMIN CONFIGURATIONS
# ============================================

@admin.register(HiringStage)
class HiringStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'employer', 'order', 'color', 'is_default', 'application_count')
    list_filter = ('is_default', 'employer')
    search_fields = ('name', 'employer__username')
    ordering = ('employer', 'order')

    def application_count(self, obj):
        return obj.applications.count()
    application_count.short_description = 'Applications'


@admin.register(ApplicationStageHistory)
class ApplicationStageHistoryAdmin(admin.ModelAdmin):
    list_display = ('application', 'stage', 'changed_by', 'changed_at')
    list_filter = ('changed_at', 'stage')
    search_fields = ('application__applicant__username', 'application__job__title')
    date_hierarchy = 'changed_at'
    readonly_fields = ('changed_at',)


@admin.register(ApplicationNote)
class ApplicationNoteAdmin(admin.ModelAdmin):
    list_display = ('application', 'author', 'is_private', 'created_at', 'content_preview')
    list_filter = ('is_private', 'created_at')
    search_fields = ('application__applicant__username', 'author__username', 'content')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ApplicationRating)
class ApplicationRatingAdmin(admin.ModelAdmin):
    list_display = ('application', 'rater', 'overall_rating', 'skills_rating', 'experience_rating', 'culture_fit_rating', 'created_at')
    list_filter = ('overall_rating', 'created_at')
    search_fields = ('application__applicant__username', 'rater__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ApplicationTag)
class ApplicationTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'employer', 'color', 'usage_count')
    list_filter = ('employer',)
    search_fields = ('name', 'employer__username')

    def usage_count(self, obj):
        return obj.assignments.count()
    usage_count.short_description = 'Used On'


@admin.register(ApplicationTagAssignment)
class ApplicationTagAssignmentAdmin(admin.ModelAdmin):
    list_display = ('tag', 'application', 'assigned_by', 'assigned_at')
    list_filter = ('assigned_at', 'tag')
    search_fields = ('tag__name', 'application__applicant__username')
    date_hierarchy = 'assigned_at'
    readonly_fields = ('assigned_at',)


# ============================================
# PHASE 2: EMAIL & NOTIFICATION ADMIN
# ============================================

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'employer', 'template_type', 'is_active', 'updated_at')
    list_filter = ('template_type', 'is_active', 'employer')
    search_fields = ('name', 'subject', 'employer__username')
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Template Info', {
            'fields': ('employer', 'name', 'template_type', 'is_active')
        }),
        ('Content', {
            'fields': ('subject', 'body')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username')
    date_hierarchy = 'created_at'
    list_editable = ('is_read',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('recipient', 'application', 'job')


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'subject', 'sender', 'status', 'sent_at', 'created_at')
    list_filter = ('status', 'created_at', 'sender')
    search_fields = ('recipient_email', 'subject', 'sender__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'sent_at')
    raw_id_fields = ('sender', 'recipient_user', 'template', 'application')
    fieldsets = (
        ('Email Details', {
            'fields': ('sender', 'recipient_email', 'recipient_user', 'subject')
        }),
        ('Content', {
            'fields': ('body', 'template')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'sent_at')
        }),
        ('Related', {
            'fields': ('application',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'application', 'is_read', 'content_preview', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'content', 'application__job__title')
    date_hierarchy = 'created_at'
    list_editable = ('is_read',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('application', 'sender')

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


# ============================================
# PHASE 3: TEAM COLLABORATION ADMIN
# ============================================

@admin.register(EmployerTeam)
class EmployerTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'member_count', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    def member_count(self, obj):
        return obj.members.filter(is_active=True).count()
    member_count.short_description = 'Active Members'


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'joined_at')
    search_fields = ('user__username', 'user__email', 'team__name')
    date_hierarchy = 'joined_at'
    list_editable = ('role', 'is_active')
    raw_id_fields = ('user', 'team', 'invited_by')


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'team', 'role', 'status', 'invited_by', 'created_at', 'expires_at')
    list_filter = ('status', 'role', 'created_at')
    search_fields = ('email', 'team__name', 'invited_by__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('token', 'created_at')
    raw_id_fields = ('team', 'invited_by', 'accepted_by')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'user', 'team', 'description_preview', 'created_at')
    list_filter = ('action_type', 'created_at', 'team')
    search_fields = ('description', 'user__username', 'team__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'team', 'application', 'job')

    def description_preview(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_preview.short_description = 'Description'
