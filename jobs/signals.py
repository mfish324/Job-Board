from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .models import UserProfile


@receiver(user_signed_up)
def create_profile_for_allauth_signup(request, user, **kwargs):
    """
    The job seeker/employer/recruiter signup forms create UserProfile
    themselves (see forms.py). Allauth-driven signups (Google OAuth, via
    SOCIALACCOUNT_AUTO_SIGNUP) bypass those forms entirely, so without this
    the user ends up with no UserProfile and 500s on any page that assumes
    one exists (e.g. edit_profile).
    """
    UserProfile.objects.get_or_create(user=user, defaults={'user_type': 'job_seeker'})
