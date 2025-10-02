# Logo Not Updating - Troubleshooting Guide

## Your Current Setup

✅ Logo files found in correct location:
- `jobs/static/jobs/images/logo.png` (21KB)
- `jobs/static/jobs/images/logo_name.png` (58KB)

The template is currently configured to use: `logo.png`

---

## Quick Fixes (Try These in Order)

### Fix 1: Hard Refresh Your Browser
The browser is likely caching the old logo.

**Windows/Linux:**
- Press `Ctrl + Shift + R`
- Or `Ctrl + F5`

**Mac:**
- Press `Cmd + Shift + R`
- Or hold `Shift` and click the reload button

### Fix 2: Clear Browser Cache Completely

**Chrome:**
1. Press `Ctrl + Shift + Delete` (or `Cmd + Shift + Delete` on Mac)
2. Select "Cached images and files"
3. Click "Clear data"
4. Reload the page

**Firefox:**
1. Press `Ctrl + Shift + Delete`
2. Select "Cache"
3. Click "Clear Now"
4. Reload the page

### Fix 3: Open in Incognito/Private Mode
- Chrome: `Ctrl + Shift + N` (or `Cmd + Shift + N` on Mac)
- Firefox: `Ctrl + Shift + P`
- Navigate to your site: `http://localhost:8000`

If the logo appears in incognito mode, it's definitely a cache issue!

### Fix 4: Restart the Development Server

In your terminal where Django is running:
1. Press `Ctrl + C` to stop the server
2. Activate your virtual environment:
   ```bash
   venv\Scripts\activate
   ```
3. Start the server again:
   ```bash
   python manage.py runserver
   ```
4. Refresh your browser with `Ctrl + Shift + R`

---

## If You Want to Use a Different Logo File

You have two logo files. If you want to use `logo_name.png` instead:

### Option 1: Rename Your File
```bash
cd jobs/static/jobs/images/
del logo.png
ren logo_name.png logo.png
```

### Option 2: Update the Template

Edit `jobs/templates/jobs/base.html` around line 236-238:

**Change from:**
```html
<img src="{% static 'jobs/images/logo.png' %}" alt="Real Jobs, Real People Logo" class="logo">
```

**To:**
```html
<img src="{% static 'jobs/images/logo_name.png' %}" alt="Real Jobs, Real People Logo" class="logo">
```

---

## Verify Logo is Loading

### Check in Browser DevTools:

1. Right-click on the page → "Inspect" (or press `F12`)
2. Go to the "Network" tab
3. Reload the page (`Ctrl + R`)
4. Look for `logo.png` in the list
5. Click on it to see:
   - Status: Should be `200 OK`
   - Preview: Should show your logo image

If you see a `404 Not Found`, the file path is wrong.

### Check the URL Being Requested:

In DevTools Network tab, the logo should load from:
```
http://localhost:8000/static/jobs/images/logo.png
```

You can also test this directly:
1. Copy that URL
2. Paste it into your browser address bar
3. You should see just the logo image

---

## Common Issues & Solutions

### Issue: Logo shows but it's the old one
**Solution:** Clear browser cache (Fix 1 or 2 above)

### Issue: Logo doesn't show at all (broken image icon)
**Possible causes:**
1. Development server not running
2. Wrong file path in template
3. File permissions issue

**Solution:**
- Verify server is running
- Check file exists: `ls jobs/static/jobs/images/`
- Verify template path matches filename

### Issue: Logo shows on some pages but not others
**Solution:**
- The logo is in `base.html`, so it should appear on all pages
- Hard refresh each page individually
- Clear cache completely

### Issue: "Static file not found" error
**Possible causes:**
1. Virtual environment not activated
2. Settings.py not configured correctly

**Solution:**
Check `jobboard/settings.py` has these lines (around line 123-126):
```python
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'jobs' / 'static',
]
```

---

## Step-by-Step Verification

Run these commands to verify everything:

```bash
# 1. Check logo file exists
ls jobs/static/jobs/images/logo.png

# 2. Check file size (should not be 0)
ls -lh jobs/static/jobs/images/logo.png

# 3. Check template references it
grep "logo.png" jobs/templates/jobs/base.html

# 4. Restart server (after activating venv)
venv\Scripts\activate
python manage.py runserver
```

---

## Still Not Working?

### Nuclear Option: Force Everything

1. **Stop the server** (`Ctrl + C`)

2. **Delete browser cache completely**

3. **Check your logo file:**
   ```bash
   # View file details
   ls -lh jobs/static/jobs/images/logo.png
   ```

4. **Add a cache-busting parameter** (temporary fix):

   Edit `jobs/templates/jobs/base.html` and change:
   ```html
   <img src="{% static 'jobs/images/logo.png' %}?v=2" ...>
   ```

   The `?v=2` forces the browser to reload it.

5. **Restart everything:**
   ```bash
   venv\Scripts\activate
   python manage.py runserver
   ```

6. **Open in incognito mode:**
   `Ctrl + Shift + N` and go to `http://localhost:8000`

---

## Success Checklist

- [ ] Logo file exists in `jobs/static/jobs/images/`
- [ ] Template has `{% load static %}` at the top
- [ ] Template references correct filename
- [ ] Development server is running
- [ ] Browser cache cleared with `Ctrl + Shift + R`
- [ ] Logo appears in incognito mode
- [ ] Logo loads when visiting `/static/jobs/images/logo.png` directly

Once all checked, your logo should appear! ✅

---

## Need More Help?

Check these files:
- Logo location: `jobs/static/jobs/images/logo.png`
- Template file: `jobs/templates/jobs/base.html` (line ~238)
- Settings file: `jobboard/settings.py` (line ~123)

The most common issue is browser cache - try the hard refresh first! 🔄
