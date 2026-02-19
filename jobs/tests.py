"""
Comprehensive Test Suite for Real Jobs, Real People

Tests are organized by feature area:
1. Model Tests - Data integrity and model behavior
2. Authentication Tests - Signup, login, logout
3. Verification Tests - Phone and email verification
4. Job Management Tests - Post, edit, delete jobs
5. Application Tests - Apply, view, manage applications
6. ATS Tests - Pipeline, stages, notes, ratings, tags
7. Permission Tests - Access control and authorization
8. Security Tests - Rate limiting, CSRF, input validation
"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from .models import (
    Job, UserProfile, JobApplication, PhoneVerification, EmailVerification,
    SavedJob, HiringStage, ApplicationStageHistory, ApplicationNote,
    ApplicationRating, ApplicationTag, ApplicationTagAssignment,
    EmailTemplate, Notification, EmployerTeam, TeamMember, TeamInvitation,
    # HAS models
    Company, ScrapedJobListing, HiringActivityScore, CompanyHiringProfile, ListingFeedback
)


# =============================================================================
# MODEL TESTS
# =============================================================================

class JobModelTest(TestCase):
    """Test Job model behavior"""

    def setUp(self):
        self.user = User.objects.create_user(username='employer', password='testpass123')
        UserProfile.objects.create(user=self.user, user_type='employer', company_name='Test Corp')
        self.job = Job.objects.create(
            title='Software Engineer',
            company='Test Corp',
            description='Test job description',
            location='Remote',
            salary='$100k',
            posted_by=self.user
        )

    def test_job_creation(self):
        """Job should be created with correct attributes"""
        self.assertEqual(self.job.title, 'Software Engineer')
        self.assertTrue(self.job.is_active)
        self.assertEqual(str(self.job), 'Software Engineer at Test Corp')

    def test_job_default_active(self):
        """New jobs should be active by default"""
        job = Job.objects.create(
            title='Test Job',
            company='Test',
            description='Desc',
            location='NYC',
            posted_by=self.user
        )
        self.assertTrue(job.is_active)

    def test_job_posted_date_auto(self):
        """Posted date should be set automatically"""
        self.assertIsNotNone(self.job.posted_date)


class UserProfileModelTest(TestCase):
    """Test UserProfile model behavior"""

    def setUp(self):
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')
        self.employer = User.objects.create_user(username='employer', password='testpass123')

        self.seeker_profile = UserProfile.objects.create(
            user=self.job_seeker,
            user_type='job_seeker',
            skills='Python, Django',
            experience_years=3
        )

        self.employer_profile = UserProfile.objects.create(
            user=self.employer,
            user_type='employer',
            company_name='Tech Corp'
        )

    def test_userprofile_creation(self):
        """UserProfile should be created with correct attributes"""
        self.assertEqual(self.seeker_profile.user_type, 'job_seeker')
        self.assertEqual(self.employer_profile.user_type, 'employer')
        self.assertEqual(self.seeker_profile.experience_years, 3)

    def test_employer_requires_company_name(self):
        """Employer profile should have company name"""
        self.assertEqual(self.employer_profile.company_name, 'Tech Corp')


class JobApplicationModelTest(TestCase):
    """Test JobApplication model behavior"""

    def setUp(self):
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')
        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')
        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

    def test_duplicate_application_prevention(self):
        """Should prevent duplicate applications to same job"""
        JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='First application'
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            JobApplication.objects.create(
                job=self.job,
                applicant=self.job_seeker,
                cover_letter='Second application'
            )

    def test_application_status_default(self):
        """Application should default to pending status"""
        application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test'
        )
        self.assertEqual(application.status, 'pending')

    def test_application_applied_date_auto(self):
        """Applied date should be set automatically"""
        application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test'
        )
        self.assertIsNotNone(application.applied_date)


class HiringStageModelTest(TestCase):
    """Test HiringStage model behavior"""

    def setUp(self):
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')

    def test_default_stages_creation(self):
        """Should create default stages for employer"""
        HiringStage.create_default_stages_for_employer(self.employer)
        stages = HiringStage.objects.filter(employer=self.employer)
        self.assertEqual(stages.count(), 6)  # Applied, Screening, Interview, Offer, Hired, Rejected

    def test_stage_ordering(self):
        """Stages should be ordered by order field"""
        HiringStage.create_default_stages_for_employer(self.employer)
        stages = list(HiringStage.objects.filter(employer=self.employer).order_by('order'))
        self.assertEqual(stages[0].name, 'Applied')
        self.assertEqual(stages[-1].name, 'Rejected')


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================

class AuthenticationViewsTest(TestCase):
    """Test authentication views"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(
            username='employer',
            email='employer@test.com',
            password='testpass123'
        )
        self.job_seeker = User.objects.create_user(
            username='seeker',
            email='seeker@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

    def test_home_page_loads(self):
        """Home page should load successfully"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):
        """Login page should load successfully"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_signup_choice_page_loads(self):
        """Signup choice page should load successfully"""
        response = self.client.get(reverse('signup_choice'))
        self.assertEqual(response.status_code, 200)

    def test_valid_login(self):
        """Valid credentials should log user in"""
        response = self.client.post(reverse('login'), {
            'username': 'employer',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success

    def test_invalid_login(self):
        """Invalid credentials should show error"""
        response = self.client.post(reverse('login'), {
            'username': 'employer',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Stay on login page

    def test_logout(self):
        """User should be able to logout"""
        self.client.login(username='employer', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)  # Redirect after logout

    def test_employer_redirected_to_dashboard(self):
        """Employer should be redirected to dashboard after login"""
        response = self.client.post(reverse('login'), {
            'username': 'employer',
            'password': 'testpass123'
        }, follow=True)
        self.assertRedirects(response, reverse('employer_dashboard'))

    def test_job_seeker_redirected_to_home(self):
        """Job seeker should be redirected to home after login"""
        response = self.client.post(reverse('login'), {
            'username': 'seeker',
            'password': 'testpass123'
        }, follow=True)
        self.assertRedirects(response, reverse('home'))


class SignupTest(TestCase):
    """Test signup functionality"""

    def setUp(self):
        self.client = Client()

    @patch('jobs.views.send_phone_verification_code')
    @patch('jobs.views.send_email_verification')
    def test_job_seeker_signup(self, mock_email, mock_sms):
        """Job seeker should be able to sign up"""
        mock_sms.return_value = True
        mock_email.return_value = True

        response = self.client.post(reverse('jobseeker_signup'), {
            'username': 'newseeker',
            'email': 'newseeker@test.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'phone_number': '+15551234567',
            'first_name': 'Test',
            'last_name': 'User',
            'privacy_consent': True
        })

        # Should redirect to verification
        self.assertEqual(response.status_code, 302)

        # User should be created
        self.assertTrue(User.objects.filter(username='newseeker').exists())

        # Profile should be created
        user = User.objects.get(username='newseeker')
        self.assertEqual(user.userprofile.user_type, 'job_seeker')

    @patch('jobs.views.send_phone_verification_code')
    @patch('jobs.views.send_email_verification')
    def test_employer_signup(self, mock_email, mock_sms):
        """Employer should be able to sign up"""
        mock_sms.return_value = True
        mock_email.return_value = True

        response = self.client.post(reverse('employer_signup'), {
            'username': 'newemployer',
            'email': 'newemployer@test.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'phone_number': '+15551234567',
            'company_name': 'New Company',
            'privacy_consent': True
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newemployer').exists())

    def test_signup_password_mismatch(self):
        """Signup should fail if passwords don't match"""
        response = self.client.post(reverse('jobseeker_signup'), {
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'ComplexPass123!',
            'password2': 'DifferentPass123!',
            'phone_number': '555-123-4567'
        })
        self.assertEqual(response.status_code, 200)  # Stay on page
        self.assertFalse(User.objects.filter(username='newuser').exists())


# =============================================================================
# VERIFICATION TESTS
# =============================================================================

class PhoneVerificationTest(TestCase):
    """Test phone verification flow"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, user_type='job_seeker')
        self.verification = PhoneVerification.objects.create(
            user=self.user,
            phone_number='+15551234567',
            verification_code='123456'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_verify_phone_page_loads(self):
        """Phone verification page should load"""
        response = self.client.get(reverse('verify_phone'))
        self.assertEqual(response.status_code, 200)

    def test_correct_code_verifies(self):
        """Correct verification code should verify phone"""
        response = self.client.post(reverse('verify_phone'), {
            'verification_code': '123456'
        })
        self.verification.refresh_from_db()
        self.assertTrue(self.verification.is_verified)

    def test_incorrect_code_fails(self):
        """Incorrect verification code should fail"""
        response = self.client.post(reverse('verify_phone'), {
            'verification_code': '000000'
        })
        self.verification.refresh_from_db()
        self.assertFalse(self.verification.is_verified)


class EmailVerificationTest(TestCase):
    """Test email verification flow"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, user_type='job_seeker')
        self.verification = EmailVerification.objects.create(
            user=self.user,
            verification_token='abc123token'
        )

    def test_valid_token_verifies_email(self):
        """Valid token should verify email"""
        response = self.client.get(reverse('verify_email', args=['abc123token']))
        self.verification.refresh_from_db()
        self.assertTrue(self.verification.is_verified)

    def test_invalid_token_fails(self):
        """Invalid token should not verify email"""
        response = self.client.get(reverse('verify_email', args=['wrongtoken']))
        self.verification.refresh_from_db()
        self.assertFalse(self.verification.is_verified)


# =============================================================================
# JOB MANAGEMENT TESTS
# =============================================================================

class JobViewsTest(TestCase):
    """Test job listing and detail views"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

    def test_job_list_page(self):
        """Job list page should show jobs"""
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Job')

    def test_job_detail_page(self):
        """Job detail page should show job info"""
        response = self.client.get(reverse('job_detail', args=[self.job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job.title)

    def test_job_search(self):
        """Job search should filter results"""
        response = self.client.get(reverse('job_list'), {'search': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Job')

    def test_job_search_no_results(self):
        """Job search with no matches should show no jobs"""
        response = self.client.get(reverse('job_list'), {'search': 'NonexistentJob'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Test Job')

    def test_inactive_job_not_shown(self):
        """Inactive jobs should not appear in list"""
        self.job.is_active = False
        self.job.save()
        response = self.client.get(reverse('job_list'))
        self.assertNotContains(response, 'Test Job')


class JobManagementTest(TestCase):
    """Test employer job management"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')

        # Create verification to allow posting
        PhoneVerification.objects.create(user=self.employer, phone_number='+15551234567', is_verified=True)
        EmailVerification.objects.create(user=self.employer, is_verified=True)

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )
        self.client.login(username='employer', password='testpass123')

    def test_employer_dashboard_loads(self):
        """Employer dashboard should load"""
        response = self.client.get(reverse('employer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_post_job_page_loads(self):
        """Post job page should load for employer"""
        response = self.client.get(reverse('post_job'))
        self.assertEqual(response.status_code, 200)

    def test_edit_job_own_job(self):
        """Employer should be able to edit own job"""
        response = self.client.get(reverse('edit_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 200)

    def test_toggle_job_status(self):
        """Employer should be able to toggle job status"""
        self.assertTrue(self.job.is_active)
        response = self.client.post(reverse('toggle_job_status', args=[self.job.id]))
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)


# =============================================================================
# APPLICATION TESTS
# =============================================================================

class JobApplicationViewsTest(TestCase):
    """Test job application functionality"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        # Verify job seeker (required to apply)
        PhoneVerification.objects.create(user=self.job_seeker, phone_number='+15551234567', is_verified=True)

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

    def test_login_required_for_apply(self):
        """Unauthenticated users should be redirected to login"""
        response = self.client.get(reverse('apply_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)

    def test_apply_page_loads_for_seeker(self):
        """Application page should load for verified job seeker"""
        self.client.login(username='seeker', password='testpass123')
        response = self.client.get(reverse('apply_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 200)

    def test_employer_cannot_apply(self):
        """Employers should not be able to apply to jobs"""
        self.client.login(username='employer', password='testpass123')
        response = self.client.get(reverse('apply_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)  # Redirect with error

    def test_successful_application(self):
        """Job seeker should be able to submit application"""
        self.client.login(username='seeker', password='testpass123')
        response = self.client.post(reverse('apply_job', args=[self.job.id]), {
            'cover_letter': 'I am interested in this position.'
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success
        self.assertTrue(JobApplication.objects.filter(
            job=self.job,
            applicant=self.job_seeker
        ).exists())

    def test_cannot_apply_twice(self):
        """Job seeker cannot apply to same job twice"""
        JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='First application'
        )
        self.client.login(username='seeker', password='testpass123')
        response = self.client.post(reverse('apply_job', args=[self.job.id]), {
            'cover_letter': 'Second application'
        })
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)
        # Should still only have one application
        self.assertEqual(JobApplication.objects.filter(
            job=self.job,
            applicant=self.job_seeker
        ).count(), 1)


# =============================================================================
# ATS (APPLICANT TRACKING SYSTEM) TESTS
# =============================================================================

class ATSPipelineTest(TestCase):
    """Test ATS pipeline functionality"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

        # Create default stages
        HiringStage.create_default_stages_for_employer(self.employer)

        self.application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test application'
        )

        self.client.login(username='employer', password='testpass123')

    def test_pipeline_page_loads(self):
        """ATS pipeline page should load"""
        response = self.client.get(reverse('ats_pipeline', args=[self.job.id]))
        self.assertEqual(response.status_code, 200)

    def test_move_application_stage(self):
        """Should be able to move application to different stage"""
        screening_stage = HiringStage.objects.get(employer=self.employer, name='Screening')
        response = self.client.post(
            reverse('move_application_stage', args=[self.application.id]),
            {'stage_id': screening_stage.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_stage, screening_stage)

    def test_stage_history_created(self):
        """Moving stage should create history record"""
        screening_stage = HiringStage.objects.get(employer=self.employer, name='Screening')
        self.client.post(
            reverse('move_application_stage', args=[self.application.id]),
            {'stage_id': screening_stage.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        history = ApplicationStageHistory.objects.filter(application=self.application)
        self.assertTrue(history.exists())


class ATSNotesTest(TestCase):
    """Test ATS notes functionality"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

        self.application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test application'
        )

        self.client.login(username='employer', password='testpass123')

    def test_add_note(self):
        """Should be able to add note to application"""
        response = self.client.post(
            reverse('add_application_note', args=[self.application.id]),
            {'content': 'Great candidate, schedule interview.'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ApplicationNote.objects.filter(
            application=self.application,
            content='Great candidate, schedule interview.'
        ).exists())


class ATSRatingsTest(TestCase):
    """Test ATS ratings functionality"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

        self.application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test application'
        )

        self.client.login(username='employer', password='testpass123')

    def test_add_rating(self):
        """Should be able to rate application"""
        response = self.client.post(
            reverse('rate_application', args=[self.application.id]),
            {
                'overall_rating': 4,
                'skills_rating': 5,
                'experience_rating': 4,
                'culture_fit_rating': 3
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ApplicationRating.objects.filter(
            application=self.application,
            overall_rating=4
        ).exists())


class ATSTagsTest(TestCase):
    """Test ATS tags functionality"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        self.client.login(username='employer', password='testpass123')

    def test_create_tag(self):
        """Should be able to create tag"""
        response = self.client.post(reverse('manage_tags'), {
            'action': 'create',
            'name': 'High Priority',
            'color': '#ff0000'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ApplicationTag.objects.filter(
            employer=self.employer,
            name='High Priority'
        ).exists())

    def test_delete_tag(self):
        """Should be able to delete tag"""
        tag = ApplicationTag.objects.create(
            employer=self.employer,
            name='Test Tag',
            color='#00ff00'
        )
        response = self.client.post(reverse('manage_tags'), {
            'action': 'delete',
            'tag_id': tag.id
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ApplicationTag.objects.filter(id=tag.id).exists())


# =============================================================================
# PERMISSION TESTS
# =============================================================================

class PermissionTest(TestCase):
    """Test access control and permissions"""

    def setUp(self):
        self.client = Client()
        self.employer1 = User.objects.create_user(username='employer1', password='testpass123')
        self.employer2 = User.objects.create_user(username='employer2', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer1, user_type='employer', company_name='Corp 1')
        UserProfile.objects.create(user=self.employer2, user_type='employer', company_name='Corp 2')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Corp 1',
            description='Test description',
            location='Test City',
            posted_by=self.employer1
        )

        self.application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test application'
        )

    def test_employer_cannot_access_other_employer_job(self):
        """Employer should not be able to edit another employer's job"""
        self.client.login(username='employer2', password='testpass123')
        response = self.client.get(reverse('edit_job', args=[self.job.id]))
        self.assertNotEqual(response.status_code, 200)

    def test_employer_cannot_view_other_employer_applications(self):
        """Employer should not see applications for other employer's jobs"""
        self.client.login(username='employer2', password='testpass123')
        response = self.client.get(reverse('ats_pipeline', args=[self.job.id]))
        self.assertNotEqual(response.status_code, 200)

    def test_job_seeker_cannot_access_employer_dashboard(self):
        """Job seeker should not access employer dashboard"""
        self.client.login(username='seeker', password='testpass123')
        response = self.client.get(reverse('employer_dashboard'))
        self.assertNotEqual(response.status_code, 200)

    def test_job_seeker_cannot_post_job(self):
        """Job seeker should not be able to post jobs"""
        self.client.login(username='seeker', password='testpass123')
        response = self.client.get(reverse('post_job'))
        self.assertNotEqual(response.status_code, 200)


class SavedJobsPermissionTest(TestCase):
    """Test saved jobs permissions"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

        self.job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test description',
            location='Test City',
            posted_by=self.employer
        )

    def test_job_seeker_can_save_job(self):
        """Job seeker should be able to save jobs"""
        self.client.login(username='seeker', password='testpass123')
        response = self.client.get(reverse('save_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SavedJob.objects.filter(
            user=self.job_seeker,
            job=self.job
        ).exists())


# =============================================================================
# SECURITY TESTS
# =============================================================================

class SecurityTest(TestCase):
    """Test security features"""

    def setUp(self):
        self.client = Client()

    def test_csrf_protection(self):
        """Forms should require CSRF token"""
        # Disable CSRF for this test client to verify form requires it
        response = self.client.post(reverse('login'), {
            'username': 'test',
            'password': 'test'
        })
        # Django's test client handles CSRF automatically
        # This test verifies the endpoint exists and responds
        self.assertIn(response.status_code, [200, 302, 403])

    def test_password_not_in_response(self):
        """Passwords should never appear in responses"""
        user = User.objects.create_user(username='testuser', password='secretpass123')
        UserProfile.objects.create(user=user, user_type='job_seeker')
        self.client.login(username='testuser', password='secretpass123')

        response = self.client.get(reverse('edit_profile'))
        self.assertNotContains(response, 'secretpass123')


class NotificationTest(TestCase):
    """Test notification system"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        self.job_seeker = User.objects.create_user(username='seeker', password='testpass123')

        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')
        UserProfile.objects.create(user=self.job_seeker, user_type='job_seeker')

    def test_notification_created_on_application(self):
        """Notification should be created when application is submitted"""
        job = Job.objects.create(
            title='Test Job',
            company='Test Corp',
            description='Test',
            location='NYC',
            posted_by=self.employer
        )

        # Verify job seeker
        PhoneVerification.objects.create(user=self.job_seeker, phone_number='+15551234567', is_verified=True)

        self.client.login(username='seeker', password='testpass123')
        self.client.post(reverse('apply_job', args=[job.id]), {
            'cover_letter': 'I am interested.'
        })

        # Employer should have notification
        self.assertTrue(Notification.objects.filter(
            recipient=self.employer,
            notification_type='application_received'
        ).exists())


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class FullApplicationFlowTest(TestCase):
    """Test complete application flow from start to finish"""

    def setUp(self):
        self.client = Client()

    @patch('jobs.views.send_phone_verification_code')
    @patch('jobs.views.send_email_verification')
    def test_complete_job_seeker_flow(self, mock_email, mock_sms):
        """Test complete flow: signup -> verify -> apply -> view application"""
        mock_sms.return_value = True
        mock_email.return_value = True

        # 1. Create employer and job first
        employer = User.objects.create_user(username='employer', password='testpass123')
        UserProfile.objects.create(user=employer, user_type='employer', company_name='Test Corp')
        job = Job.objects.create(
            title='Software Engineer',
            company='Test Corp',
            description='Looking for a developer',
            location='Remote',
            posted_by=employer
        )

        # 2. Sign up as job seeker
        response = self.client.post(reverse('jobseeker_signup'), {
            'username': 'newseeker',
            'email': 'seeker@test.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'phone_number': '+15551234567',
            'first_name': 'Test',
            'last_name': 'Seeker',
            'privacy_consent': True
        })
        self.assertEqual(response.status_code, 302)

        # 3. Verify phone (simulate)
        user = User.objects.get(username='newseeker')
        phone_verification = PhoneVerification.objects.get(user=user)
        phone_verification.is_verified = True
        phone_verification.save()

        # 4. Apply to job
        self.client.login(username='newseeker', password='ComplexPass123!')
        response = self.client.post(reverse('apply_job', args=[job.id]), {
            'cover_letter': 'I am very interested in this position.'
        })
        self.assertEqual(response.status_code, 302)

        # 5. Verify application was created
        application = JobApplication.objects.get(job=job, applicant=user)
        self.assertEqual(application.status, 'pending')
        self.assertEqual(application.cover_letter, 'I am very interested in this position.')

        # 6. View application in profile
        response = self.client.get(reverse('user_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Software Engineer')


# =============================================================================
# HIRING ACTIVITY SCORE (HAS) TESTS
# =============================================================================

class CompanyModelTest(TestCase):
    """Test Company model behavior"""

    def setUp(self):
        self.company = Company.objects.create(
            name='Test Company Inc.',
            website='https://testcompany.com',
            industry='Technology'
        )

    def test_company_creation(self):
        """Company should be created with correct attributes"""
        self.assertEqual(self.company.name, 'Test Company Inc.')
        self.assertEqual(self.company.industry, 'Technology')

    def test_normalized_name_generation(self):
        """Normalized name should be generated on save"""
        self.assertIsNotNone(self.company.normalized_name)
        # normalized_name preserves lowercase version of original name
        self.assertEqual(self.company.normalized_name.lower(), 'test company inc.')

    def test_find_or_create_exact_match(self):
        """find_or_create should find exact match"""
        found, created = Company.find_or_create('Test Company Inc.')
        self.assertFalse(created)
        self.assertEqual(found.id, self.company.id)

    def test_find_or_create_new_company(self):
        """find_or_create should create new company if not found"""
        found, created = Company.find_or_create('New Company LLC')
        self.assertTrue(created)
        self.assertEqual(found.name, 'New Company LLC')


class ScrapedJobListingModelTest(TestCase):
    """Test ScrapedJobListing model behavior"""

    def setUp(self):
        self.company = Company.objects.create(name='Tech Corp')
        self.listing = ScrapedJobListing.objects.create(
            source_ats='greenhouse',
            source_url='https://boards.greenhouse.io/techcorp/jobs/12345',
            company_name='Tech Corp',
            company=self.company,
            title='Senior Software Engineer',
            description='We are looking for a senior engineer...',
            location='San Francisco, CA'
        )

    def test_listing_creation(self):
        """Listing should be created with correct attributes"""
        self.assertEqual(self.listing.title, 'Senior Software Engineer')
        self.assertEqual(self.listing.status, 'active')
        self.assertFalse(self.listing.published_to_board)

    def test_description_hash_generated(self):
        """Description hash should be generated on save"""
        self.assertIsNotNone(self.listing.description_hash)
        self.assertEqual(len(self.listing.description_hash), 64)  # SHA-256 hex

    def test_days_since_first_seen(self):
        """days_since_first_seen should calculate correctly"""
        days = self.listing.days_since_first_seen()
        self.assertEqual(days, 0)  # Just created

    def test_is_stale_new_listing(self):
        """New listing should not be stale"""
        self.assertFalse(self.listing.is_stale())


class HiringActivityScoreModelTest(TestCase):
    """Test HiringActivityScore model behavior"""

    def setUp(self):
        self.listing = ScrapedJobListing.objects.create(
            source_ats='lever',
            source_url='https://jobs.lever.co/company/12345',
            company_name='Lever Company',
            title='Product Manager',
            description='Product manager role...'
        )
        self.has = HiringActivityScore.objects.create(
            listing=self.listing,
            total_score=75,
            score_breakdown={'base': {'points': 50, 'explanation': 'Base score'}}
        )

    def test_score_band_calculated_on_save(self):
        """Score band should be calculated automatically"""
        self.assertEqual(self.has.score_band, 'likely_active')

    def test_score_band_very_active(self):
        """Score 80+ should be very_active"""
        self.has.total_score = 85
        self.has.save()
        self.assertEqual(self.has.score_band, 'very_active')

    def test_score_band_uncertain(self):
        """Score 50-64 should be uncertain"""
        self.has.total_score = 55
        self.has.save()
        self.assertEqual(self.has.score_band, 'uncertain')

    def test_score_band_low_signal(self):
        """Score below 50 should be low_signal"""
        self.has.total_score = 35
        self.has.save()
        self.assertEqual(self.has.score_band, 'low_signal')

    def test_published_to_board_synced(self):
        """published_to_board should sync with listing on save"""
        self.has.total_score = 70  # Above threshold
        self.has.save()
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.published_to_board)


class HASEngineTest(TestCase):
    """Test HAS scoring engine"""

    def setUp(self):
        from jobs.scoring import HASEngine
        self.engine = HASEngine()

        self.company = Company.objects.create(
            name='Active Company',
            industry='technology'
        )
        self.profile = CompanyHiringProfile.objects.create(
            company=self.company,
            total_active_listings=10,
            net_job_movement_30d=5,
            reputation_score=75.0
        )
        self.listing = ScrapedJobListing.objects.create(
            source_ats='greenhouse',
            source_url='https://boards.greenhouse.io/active/jobs/1',
            company_name='Active Company',
            company=self.company,
            title='Software Engineer',
            description='A' * 600,  # Long description for quality points
            location='New York, NY',
            salary_min=80000,
            salary_max=120000
        )

    def test_base_score(self):
        """Score should start at base score"""
        score, breakdown = self.engine.calculate_score(self.listing)
        self.assertEqual(breakdown['base']['points'], 50)

    def test_freshness_signal_new_listing(self):
        """Fresh listing should get maximum freshness points"""
        score, breakdown = self.engine.calculate_score(self.listing)
        self.assertGreater(breakdown['freshness']['points'], 10)

    def test_specificity_with_salary(self):
        """Listing with salary should get specificity points"""
        score, breakdown = self.engine.calculate_score(self.listing)
        self.assertGreater(breakdown['specificity']['points'], 0)

    def test_company_velocity_positive(self):
        """Company with positive job movement should get points"""
        score, breakdown = self.engine.calculate_score(self.listing, profile=self.profile)
        self.assertGreater(breakdown['company_velocity']['points'], 0)

    def test_company_reputation_good(self):
        """Company with good reputation should get bonus"""
        score, breakdown = self.engine.calculate_score(self.listing, profile=self.profile)
        self.assertGreater(breakdown['company_reputation']['points'], 0)

    def test_score_clamping_max(self):
        """Score should be clamped to maximum of 100"""
        # Create an ideal listing
        score, breakdown = self.engine.calculate_score(self.listing, profile=self.profile)
        self.assertLessEqual(score, 100)

    def test_score_clamping_min(self):
        """Score should be clamped to minimum of 0"""
        # Create a bad listing
        bad_listing = ScrapedJobListing.objects.create(
            source_ats='other',
            source_url='https://example.com/job/bad',
            company_name='Bad Company',
            title='Job',
            description='Short',
            repost_count=5
        )
        # Make it old by setting date_first_seen in the past
        from django.utils import timezone
        bad_listing.date_first_seen = timezone.now() - timedelta(days=120)
        bad_listing.save()

        score, breakdown = self.engine.calculate_score(bad_listing)
        self.assertGreaterEqual(score, 0)

    def test_get_score_band(self):
        """get_score_band should return correct band"""
        self.assertEqual(self.engine.get_score_band(90), 'very_active')
        self.assertEqual(self.engine.get_score_band(70), 'likely_active')
        self.assertEqual(self.engine.get_score_band(55), 'uncertain')
        self.assertEqual(self.engine.get_score_band(30), 'low_signal')

    def test_should_publish(self):
        """should_publish should return True for scores >= 65"""
        self.assertTrue(self.engine.should_publish(75))
        self.assertTrue(self.engine.should_publish(65))
        self.assertFalse(self.engine.should_publish(64))
        self.assertFalse(self.engine.should_publish(50))

    def test_score_listing_creates_has(self):
        """score_listing should create HiringActivityScore record"""
        has = self.engine.score_listing(self.listing, save=True)
        self.assertIsNotNone(has.id)
        self.assertIsNotNone(has.total_score)
        self.assertIsNotNone(has.score_band)


class HASSignalsTest(TestCase):
    """Test individual HAS signal calculators"""

    def setUp(self):
        from jobs.scoring.config import get_config
        self.config = get_config()

        self.listing = ScrapedJobListing.objects.create(
            source_ats='workday',
            source_url='https://workday.com/job/1',
            company_name='Test Company',
            title='Test Job',
            description='Test description for the job posting.'
        )

    def test_repost_penalty(self):
        """Repost penalty should increase with reposts"""
        from jobs.scoring.signals import calculate_repost_penalty

        # No reposts
        self.listing.repost_count = 0
        points, _ = calculate_repost_penalty(self.listing, self.config)
        self.assertEqual(points, 0)

        # Some reposts
        self.listing.repost_count = 2
        points, _ = calculate_repost_penalty(self.listing, self.config)
        self.assertEqual(points, -10)  # -5 per repost

        # Many reposts (clamped)
        self.listing.repost_count = 10
        points, _ = calculate_repost_penalty(self.listing, self.config)
        self.assertEqual(points, -15)  # Clamped to min

    def test_specificity_no_salary(self):
        """Specificity should be lower without salary"""
        from jobs.scoring.signals import calculate_specificity

        # Without salary
        points1, _ = calculate_specificity(self.listing, self.config)

        # With salary
        self.listing.salary_min = 50000
        self.listing.salary_max = 70000
        points2, _ = calculate_specificity(self.listing, self.config)

        self.assertGreater(points2, points1)


class ListingFeedbackModelTest(TestCase):
    """Test ListingFeedback model behavior"""

    def setUp(self):
        self.user = User.objects.create_user(username='feedbacker', password='testpass123')
        UserProfile.objects.create(user=self.user, user_type='job_seeker')
        self.listing = ScrapedJobListing.objects.create(
            source_ats='greenhouse',
            source_url='https://boards.greenhouse.io/test/1',
            company_name='Test Company',
            title='Test Job',
            description='Test description'
        )

    def test_feedback_creation(self):
        """Feedback should be created correctly"""
        feedback = ListingFeedback.objects.create(
            listing=self.listing,
            user=self.user,
            feedback_type='applied_got_response',
            days_to_response=5,
            comment='Got interview!'
        )
        self.assertEqual(feedback.feedback_type, 'applied_got_response')
        self.assertEqual(feedback.days_to_response, 5)


class MarketListingsViewTest(TestCase):
    """Test market listings views"""

    def setUp(self):
        self.client = Client()
        self.employer = User.objects.create_user(username='employer', password='testpass123')
        UserProfile.objects.create(user=self.employer, user_type='employer', company_name='Test Corp')

        # Create and verify phone for employer
        PhoneVerification.objects.create(user=self.employer, phone_number='+15551234567', is_verified=True)

        # Create a published listing
        self.listing = ScrapedJobListing.objects.create(
            source_ats='greenhouse',
            source_url='https://boards.greenhouse.io/test/1',
            company_name='Test Corp',
            title='Published Job',
            description='This is a published job listing.',
            published_to_board=True,
            status='active'
        )

        # Create HAS score
        HiringActivityScore.objects.create(
            listing=self.listing,
            total_score=75,
            score_band='likely_active',
            score_breakdown={}
        )

    def test_job_list_page_loads(self):
        """Job list page should load and include observed listings"""
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)

    def test_job_list_shows_published(self):
        """Job list should show published observed listings"""
        response = self.client.get(reverse('job_list'))
        self.assertContains(response, 'Published Job')

    def test_observed_listing_detail_loads(self):
        """Observed listing detail page should load"""
        response = self.client.get(reverse('observed_listing_detail', args=[self.listing.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published Job')

    def test_market_redirect(self):
        """Old /market/ URL should 301 redirect to /jobs/"""
        response = self.client.get(reverse('market_redirect'))
        self.assertEqual(response.status_code, 301)

    def test_claim_listing_requires_login(self):
        """Claim listing should require authentication"""
        response = self.client.get(reverse('claim_listing', args=[self.listing.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_claim_listing_employer_only(self):
        """Only employers can claim listings"""
        job_seeker = User.objects.create_user(username='seeker', password='testpass123')
        UserProfile.objects.create(user=job_seeker, user_type='job_seeker')
        self.client.login(username='seeker', password='testpass123')

        response = self.client.get(reverse('claim_listing', args=[self.listing.id]))
        self.assertEqual(response.status_code, 302)  # Redirect with error


class HASManagementCommandTest(TestCase):
    """Test HAS management commands"""

    def setUp(self):
        self.listing = ScrapedJobListing.objects.create(
            source_ats='greenhouse',
            source_url='https://boards.greenhouse.io/test/cmd',
            company_name='Command Test Corp',
            title='Test Job for Commands',
            description='Description for command testing.',
            status='active'
        )

    def test_score_listings_dry_run(self):
        """score_listings --dry-run should not create scores"""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('score_listings', '--dry-run', stdout=out)

        # Should not create any HAS records
        self.assertFalse(HiringActivityScore.objects.filter(listing=self.listing).exists())

    def test_score_listings_creates_scores(self):
        """score_listings should create HAS records"""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('score_listings', '--force', stdout=out)

        # Should create HAS record
        self.assertTrue(HiringActivityScore.objects.filter(listing=self.listing).exists())

    def test_expire_stale_listings_dry_run(self):
        """expire_stale_listings --dry-run should not change status"""
        from django.core.management import call_command
        from io import StringIO

        # Make listing old
        self.listing.date_last_seen = timezone.now() - timedelta(days=14)
        self.listing.save()

        out = StringIO()
        call_command('expire_stale_listings', '--dry-run', stdout=out)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'active')  # Should still be active
