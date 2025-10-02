from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Job, UserProfile, JobApplication


class JobModelTest(TestCase):
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
        self.assertEqual(self.job.title, 'Software Engineer')
        self.assertTrue(self.job.is_active)
        self.assertEqual(str(self.job), 'Software Engineer at Test Corp')


class UserProfileModelTest(TestCase):
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
        self.assertEqual(self.seeker_profile.user_type, 'job_seeker')
        self.assertEqual(self.employer_profile.user_type, 'employer')
        self.assertEqual(self.seeker_profile.experience_years, 3)


class ViewsTest(TestCase):
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

    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JobBoard')

    def test_job_list_page(self):
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Job')

    def test_job_detail_page(self):
        response = self.client.get(reverse('job_detail', args=[self.job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job.title)

    def test_login_required_for_apply(self):
        response = self.client.get(reverse('apply_job', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_job_search(self):
        response = self.client.get(reverse('job_list'), {'search': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Job')


class JobApplicationTest(TestCase):
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

    def test_duplicate_application_prevention(self):
        JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='First application'
        )

        # Try to create duplicate
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            JobApplication.objects.create(
                job=self.job,
                applicant=self.job_seeker,
                cover_letter='Second application'
            )

    def test_application_status_default(self):
        application = JobApplication.objects.create(
            job=self.job,
            applicant=self.job_seeker,
            cover_letter='Test'
        )
        self.assertEqual(application.status, 'pending')
