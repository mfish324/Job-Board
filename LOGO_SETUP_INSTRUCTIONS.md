# Logo Integration Instructions

Your Django job board application is now configured to use your company logo!

## Quick Setup (3 Steps)

### Step 1: Place Your Logo File

Copy your logo image file to this directory:
```
jobs/static/jobs/images/logo.png
```

**Supported formats:**
- PNG (recommended for transparency)
- JPG/JPEG
- SVG
- WebP

**Recommended specifications:**
- **Height:** 45-60px for best display
- **Width:** Up to 200px (will auto-resize if larger)
- **Format:** PNG with transparent background works best
- **File size:** Keep under 100KB for fast loading

### Step 2: Rename Your File (if needed)

If your logo file has a different name or format, either:

**Option A - Rename your file to `logo.png`**
```bash
# Example: If your file is named "company-logo.jpg"
mv jobs/static/jobs/images/company-logo.jpg jobs/static/jobs/images/logo.png
```

**Option B - Update the template**

Edit `jobs/templates/jobs/base.html` on line 170 and change:
```html
<img src="{% static 'jobs/images/logo.png' %}" ...>
```
to match your filename:
```html
<img src="{% static 'jobs/images/your-logo-name.svg' %}" ...>
```

### Step 3: Collect Static Files (if deploying)

If you're deploying to production, run:
```bash
python manage.py collectstatic
```

For development, Django will serve the static files automatically.

---

## Current Configuration

✅ **Static files directory created:** `jobs/static/jobs/images/`
✅ **Settings.py updated** with static file configuration
✅ **Base template updated** to display logo in navigation bar
✅ **Responsive design:** Logo adapts to mobile/desktop screens

### Logo Display Locations

Your logo will appear in:
1. **Navigation bar** (top of every page)
   - Desktop: Logo + company name
   - Mobile: Logo only (saves space)
2. **Footer** (currently shows icon, can be updated to use logo)

---

## Customization Options

### Adjust Logo Size

Edit `jobs/templates/jobs/base.html` around line 44-49:

```css
.navbar-brand img.logo {
    height: 45px;        /* Change this number */
    width: auto;
    max-width: 200px;    /* Or change max width */
    object-fit: contain;
}
```

### Add Logo to Footer

Edit `jobs/templates/jobs/base.html` around line 257:

Change from:
```html
<i class="bi bi-briefcase-fill me-2"></i>Real Jobs, Real People
```

To:
```html
<img src="{% static 'jobs/images/logo.png' %}" alt="Logo" style="height: 30px; margin-right: 10px;">Real Jobs, Real People
```

### Different Logos for Light/Dark Sections

You can have different logo versions:
- `logo.png` - For dark navbar
- `logo-dark.png` - For light sections (footer, etc.)

---

## Troubleshooting

### Logo Not Showing?

1. **Check file path:**
   ```bash
   ls jobs/static/jobs/images/logo.png
   ```

2. **Clear browser cache:**
   - Press `Ctrl + Shift + R` (Windows/Linux)
   - Press `Cmd + Shift + R` (Mac)

3. **Restart development server:**
   ```bash
   python manage.py runserver
   ```

4. **Check for typos** in the filename or template path

5. **Verify static files setting** in `jobboard/settings.py`:
   ```python
   STATIC_URL = 'static/'
   STATICFILES_DIRS = [
       BASE_DIR / 'jobs' / 'static',
   ]
   ```

### Logo Too Big/Small?

Adjust the `height` value in the CSS (see Customization Options above)

### Logo Quality Issues?

- Use a high-resolution image (2x the display size)
- For a 45px display height, use a 90px actual height
- PNG format preserves quality better than JPG

---

## File Structure

```
RJRP/
├── jobs/
│   ├── static/
│   │   └── jobs/
│   │       └── images/
│   │           └── logo.png          ← Put your logo here!
│   ├── templates/
│   │   └── jobs/
│   │       └── base.html             ← Logo is referenced here
│   └── ...
├── jobboard/
│   └── settings.py                   ← Static files configured here
└── ...
```

---

## Need Help?

- Logo not showing: Check file path and browser cache
- Logo looks blurry: Use higher resolution image
- Logo too large: Adjust height in CSS
- Different format: Update template with correct filename extension
