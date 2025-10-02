# Phone & Email Verification Setup Guide

## Progress: 40% Complete ✅

### What We've Done So Far:

✅ **Step 1:** Added Twilio to requirements.txt
✅ **Step 2:** Configured settings.py with Twilio and email settings
✅ **Step 3:** Created verification database models

### What's Left to Do:

⏳ **Step 4:** Create database migrations
⏳ **Step 5:** Register models in admin
⏳ **Step 6:** Create verification utility functions
⏳ **Step 7:** Update signup forms
⏳ **Step 8:** Create verification views
⏳ **Step 9:** Add URL routes
⏳ **Step 10:** Create verification templates
⏳ **Step 11:** Update .env file
⏳ **Step 12:** Install Twilio package
⏳ **Step 13:** Test the system

---

## Next Steps (What You Need to Do)

### A. Get Twilio Account (Free Trial)

1. **Sign up at Twilio:**
   https://www.twilio.com/try-twilio

2. **Get your credentials:**
   - Account SID
   - Auth Token
   - Phone Number (they give you one free)

3. **Add to your .env file:**
   ```
   TWILIO_ACCOUNT_SID=your_account_sid_here
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_PHONE_NUMBER=+1234567890
   ```

**Cost:** FREE for trial (includes $15.50 credit = ~1,900 SMS messages)

### B. Set Up Email (Gmail Example)

1. **Create/use Gmail account** for sending verification emails

2. **Enable App Password:**
   - Go to Google Account → Security
   - Turn on 2-Step Verification
   - Generate App Password

3. **Add to .env file:**
   ```
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your_app_password_here
   DEFAULT_FROM_EMAIL=noreply@realjobsrealpeople.net
   ```

**Cost:** FREE

---

## How It Will Work

### For Job Seekers (New Signup Flow):

```
1. User fills out signup form
   ↓
2. User enters phone number
   ↓
3. System sends 6-digit code via SMS
   ↓
4. User enters code to verify phone
   ↓
5. System sends email verification link
   ↓
6. User clicks link to verify email
   ↓
7. Account is fully activated ✅
```

### For Employers:

Same flow as job seekers - ensures all users are verified.

---

## Database Models Created

### PhoneVerification Model
```python
- user (link to User)
- phone_number
- verification_code (6 digits)
- is_verified (True/False)
- created_at
- verified_at
- is_code_expired() method (10 min expiry)
```

### EmailVerification Model
```python
- user (link to User)
- verification_token (unique 64-char string)
- is_verified (True/False)
- created_at
- verified_at
- is_token_expired() method (24 hour expiry)
```

---

## Security Features

✅ **Code Expiry:** Phone codes expire after 10 minutes
✅ **Token Expiry:** Email tokens expire after 24 hours
✅ **One-Time Use:** Codes/tokens can only be used once
✅ **Rate Limiting:** Prevents spam (to be added)
✅ **Unique Tokens:** Random 64-character email tokens

---

## Configuration Options (in settings.py)

You can turn verification on/off:

```python
PHONE_VERIFICATION_REQUIRED = True   # Set to False to disable phone verification
EMAIL_VERIFICATION_REQUIRED = True   # Set to False to disable email verification
VERIFICATION_CODE_EXPIRY_MINUTES = 10  # How long phone codes last
```

---

## What Happens If User Doesn't Verify?

### Option 1: Soft Enforcement (Recommended for Launch)
- User can signup but sees banner: "Please verify your phone/email"
- Can browse jobs but cannot apply until verified
- Gentle reminders to complete verification

### Option 2: Hard Enforcement
- User cannot login until both phone + email verified
- Account is locked after signup until verification
- More secure but higher dropoff

**We'll implement Option 1 (soft) first, then you can switch to Option 2 if needed.**

---

## Costs Breakdown

### Twilio (Phone Verification)
- **Setup:** FREE
- **Per SMS:** $0.0079 (less than 1 cent)
- **1,000 users:** ~$8
- **Free trial:** $15.50 credit = 1,900 SMS

### Email (Gmail/SMTP)
- **Setup:** FREE
- **Per Email:** FREE
- **Limit:** 500 emails/day (Gmail free tier)
- **For more:** Use AWS SES ($0.10 per 1,000 emails)

### Total Cost for 1,000 Users:
- **Twilio:** $8
- **Email:** $0
- **TOTAL:** $8

Compare to: $445 in Stripe fees for $5 deposits!

---

## Testing Plan

### Test Accounts to Create:

1. **Test Job Seeker:**
   - Use your real phone for first test
   - Use your email
   - Go through full flow

2. **Test Employer:**
   - Different phone number
   - Different email
   - Verify employer can post jobs after verification

3. **Test Invalid Codes:**
   - Wrong phone code
   - Expired phone code
   - Wrong email link
   - Expired email link

---

## Future Enhancements

Once basic verification works, you can add:

### Phase 2 Features:
- **Resend code** button (with rate limiting)
- **Rate limiting:** Max 3 code requests per hour
- **International phone numbers** (country code selector)
- **SMS templates:** Branded messages
- **Email templates:** Branded HTML emails
- **Admin dashboard:** See verification status
- **Verification badges:** Show "Verified" badge on profiles

### Phase 3 Features:
- **Two-factor authentication (2FA)** for login
- **Phone number as username** option
- **Social auth:** Login with Google/LinkedIn
- **ID verification:** For premium users

---

## Files Modified So Far

✅ `requirements.txt` - Added Twilio
✅ `jobboard/settings.py` - Added configuration
✅ `jobs/models.py` - Added PhoneVerification & EmailVerification models

### Files We'll Create/Modify Next:

⏳ `jobs/admin.py` - Register verification models
⏳ `jobs/utils.py` - Verification helper functions (NEW FILE)
⏳ `jobs/forms.py` - Add phone field to signup
⏳ `jobs/views.py` - Add verification views
⏳ `jobs/urls.py` - Add verification URLs
⏳ `jobs/templates/jobs/verify_phone.html` (NEW FILE)
⏳ `jobs/templates/jobs/verify_email.html` (NEW FILE)
⏳ `.env.example` - Add Twilio variables

---

## Ready to Continue?

The next steps will be:

1. **Run migrations** to create database tables
2. **Install Twilio** package
3. **Create utility functions** for sending codes
4. **Update signup flow** to include verification
5. **Create verification pages**
6. **Test everything**

Then you'll be ready to launch with verified users! 🚀

---

## Questions?

- **"What if Twilio is down?"** - Fallback to email-only verification
- **"What about international users?"** - Twilio works globally (slightly higher cost)
- **"Can I skip phone verification?"** - Yes, set `PHONE_VERIFICATION_REQUIRED = False`
- **"What if user changes phone?"** - Add "Update Phone" feature later
- **"How do I test without using real phone?"** - Twilio has test numbers for development

