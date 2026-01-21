# Testing Site Upgrades Without Affecting Production

This guide explains how to safely test changes before deploying them to your live site.

---

## Option 1: Local Testing (Recommended First Step)

### Setup

1. **Open a terminal in your project folder**

2. **Create/activate a virtual environment** (if not already done):
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Mac/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up local environment**:
   Create a `.env` file in the project root (if not exists):
   ```
   DEBUG=True
   SECRET_KEY=local-development-key-change-in-production
   DATABASE_URL=sqlite:///db.sqlite3
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser** (if needed):
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server**:
   ```bash
   python manage.py runserver
   ```

8. **Test at**: http://127.0.0.1:8000

### What to Test Locally
- New features and UI changes
- Form submissions
- Page navigation
- Error handling
- Admin panel changes

### Limitations
- No Twilio SMS (use test mode or mock)
- No Cloudinary uploads (uses local storage)
- No email sending (configure console backend for testing)

---

## Option 2: Render Staging Environment (Recommended for Full Testing)

### Step 1: Create a Staging App on Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect the same GitHub repo
4. **Important settings**:
   - **Name**: `rjrp-staging` (or similar)
   - **Branch**: `main` (or create a `staging` branch)
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start Command**: `gunicorn jobboard.wsgi:application`

### Step 2: Create a Staging Database

1. In Render, click **"New +"** → **"PostgreSQL"**
2. **Name**: `rjrp-staging-db`
3. Choose the **Free** tier for testing
4. Copy the **Internal Database URL**

### Step 3: Configure Staging Environment Variables

In your staging web service, add these environment variables:

| Variable | Value |
|----------|-------|
| `DEBUG` | `False` |
| `SECRET_KEY` | Generate a new one: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DATABASE_URL` | Your staging database URL |
| `ALLOWED_HOSTS` | `rjrp-staging.onrender.com` |
| `DJANGO_SETTINGS_MODULE` | `jobboard.settings` |

**Optional (for full testing)**:
| Variable | Value |
|----------|-------|
| `TWILIO_ACCOUNT_SID` | Same as production (or test credentials) |
| `TWILIO_AUTH_TOKEN` | Same as production (or test credentials) |
| `TWILIO_PHONE_NUMBER` | Same as production |
| `CLOUDINARY_CLOUD_NAME` | Same as production (or separate test account) |
| `CLOUDINARY_API_KEY` | Same as production |
| `CLOUDINARY_API_SECRET` | Same as production |
| `EMAIL_HOST` | Same as production |
| `EMAIL_HOST_USER` | Same as production |
| `EMAIL_HOST_PASSWORD` | Same as production |

### Step 4: Test on Staging

1. Wait for Render to deploy (check the Logs tab)
2. Visit your staging URL: `https://rjrp-staging.onrender.com`
3. Test all new features thoroughly
4. Create test accounts (don't use real user data)

---

## Option 3: Using a Git Branch Strategy

### Setup Feature Branches

1. **Create a feature branch** for your changes:
   ```bash
   git checkout -b feature/rich-text-editor
   ```

2. **Make your changes** on this branch

3. **Test locally** (Option 1)

4. **Push to GitHub**:
   ```bash
   git push -u origin feature/rich-text-editor
   ```

5. **Test on staging** (if configured to deploy from this branch)

6. **When ready for production**, merge to main:
   ```bash
   git checkout main
   git pull origin main
   git merge feature/rich-text-editor
   git push origin main
   ```

---

## Testing Checklist

Before deploying to production, verify:

### Functionality
- [ ] All new features work correctly
- [ ] Existing features still work (regression testing)
- [ ] Forms submit without errors
- [ ] File uploads work (if applicable)
- [ ] Email notifications send (if applicable)
- [ ] SMS verification works (if applicable)

### User Experience
- [ ] Pages load without errors
- [ ] Mobile view looks correct
- [ ] All links work
- [ ] Error messages display properly

### Security
- [ ] No sensitive data exposed
- [ ] Forms have CSRF protection
- [ ] User permissions work correctly

### Performance
- [ ] Pages load in reasonable time
- [ ] No console errors in browser

---

## Rolling Back if Something Goes Wrong

### On Render

1. Go to your service in Render dashboard
2. Click **"Deploys"** tab
3. Find the last working deploy
4. Click the **"..."** menu → **"Rollback to this deploy"**

### Using Git

1. Find the last working commit:
   ```bash
   git log --oneline
   ```

2. Revert to that commit:
   ```bash
   git revert HEAD
   git push origin main
   ```

   Or reset (more drastic):
   ```bash
   git reset --hard <commit-hash>
   git push --force origin main  # CAREFUL: This rewrites history
   ```

---

## Deploying to Production

Once testing is complete:

### If Using Local Changes Only

```bash
# Commit your changes
git add .
git commit -m "Description of changes"

# Push to GitHub (this triggers Render auto-deploy)
git push origin main
```

### Monitor the Deploy

1. Go to Render dashboard
2. Watch the **Logs** for any errors
3. Once deployed, test critical paths on production
4. Keep the rollback option ready for 24-48 hours

---

## Quick Reference: Current Changes Pending

The following changes are ready but NOT committed:

1. **Bulk upload user guide** (`docs/BULK_UPLOAD_GUIDE.md`)
2. **Rich text editor for job descriptions** (`jobs/templates/jobs/post_job.html`)
3. **HTML rendering in job detail** (`jobs/templates/jobs/job_detail.html`)
4. **Strip HTML in job previews** (`jobs/templates/jobs/job_list.html`, `home.html`)
5. **This staging guide** (`docs/STAGING_TESTING_GUIDE.md`)

To test these locally:
```bash
python manage.py runserver
```

Then visit http://127.0.0.1:8000/employer/post-job/ to test the rich text editor.
