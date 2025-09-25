from django.contrib import admin
from .models import Job, UserProfile, JobApplication

admin.site.register(Job)
admin.site.register(UserProfile)
admin.site.register(JobApplication)