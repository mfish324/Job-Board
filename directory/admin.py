from django.contrib import admin
from .models import (
    FeaturedEmployer, JobTitleMapping, DirectoryEmployerCategory,
    EmployerTitleOverride, DirectoryClick,
)


class DirectoryEmployerCategoryInline(admin.TabularInline):
    model = DirectoryEmployerCategory
    extra = 1
    fields = ('canonical_category', 'employer_search_term', 'estimated_count', 'is_active')


class EmployerTitleOverrideInline(admin.TabularInline):
    model = EmployerTitleOverride
    extra = 1
    fields = ('canonical_title', 'preferred_search_term', 'notes')


@admin.register(FeaturedEmployer)
class FeaturedEmployerAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'estimated_open_roles', 'is_active',
                    'last_count_update', 'display_priority')
    list_filter = ('industry', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'display_priority')
    inlines = [DirectoryEmployerCategoryInline, EmployerTitleOverrideInline]
    fieldsets = (
        ('Company Info', {
            'fields': ('name', 'slug', 'logo', 'description', 'headquarters',
                       'employee_count', 'industry')
        }),
        ('Career Portal', {
            'fields': ('career_url', 'url_pattern', 'supports_location')
        }),
        ('Display & Counts', {
            'fields': ('is_active', 'display_priority', 'estimated_open_roles',
                       'last_count_update')
        }),
        ('Verified Link', {
            'fields': ('verified_employer',),
            'classes': ('collapse',)
        }),
    )


class EmployerTitleOverrideInlineForMapping(admin.TabularInline):
    model = EmployerTitleOverride
    extra = 0
    fields = ('employer', 'preferred_search_term', 'notes')


@admin.register(JobTitleMapping)
class JobTitleMappingAdmin(admin.ModelAdmin):
    list_display = ('canonical_title', 'alias_count_display', 'override_count_display')
    search_fields = ('canonical_title',)
    prepopulated_fields = {'slug': ('canonical_title',)}
    inlines = [EmployerTitleOverrideInlineForMapping]

    @admin.display(description='Aliases')
    def alias_count_display(self, obj):
        return obj.alias_count

    @admin.display(description='Overrides')
    def override_count_display(self, obj):
        return obj.employer_overrides.count()


@admin.register(DirectoryEmployerCategory)
class DirectoryEmployerCategoryAdmin(admin.ModelAdmin):
    list_display = ('employer', 'canonical_category', 'employer_search_term',
                    'estimated_count', 'is_active')
    list_filter = ('employer', 'is_active')
    search_fields = ('employer__name', 'canonical_category')


@admin.register(DirectoryClick)
class DirectoryClickAdmin(admin.ModelAdmin):
    list_display = ('employer', 'search_query', 'source', 'user', 'timestamp')
    list_filter = ('source', 'timestamp', 'employer')
    search_fields = ('employer__name', 'search_query')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    raw_id_fields = ('user', 'employer', 'category')
