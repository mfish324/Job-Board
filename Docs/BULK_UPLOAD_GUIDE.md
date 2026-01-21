# Bulk Job Upload Guide

This guide explains how to upload multiple job postings at once using a CSV file.

## Who Can Use Bulk Upload?

- **Employers** - via the Employer Dashboard
- **Recruiters** - via the Recruiter Dashboard
- **Admins** - via the Django Admin panel

---

## For Employers & Recruiters

### Step 1: Access Bulk Upload

1. Log in to your account
2. Go to your **Employer Dashboard** (or Recruiter Dashboard)
3. Click the **"Bulk Upload"** button in the top toolbar

### Step 2: Download the Template (Recommended)

Click **"Download CSV Template"** to get a pre-formatted spreadsheet with:
- Correct column headers
- Example job entries
- Proper formatting

### Step 3: Prepare Your CSV File

Open the template in Excel, Google Sheets, or any spreadsheet program.

#### Required Columns

| Column | Description | Example |
|--------|-------------|---------|
| `title` | Job title | Software Engineer |
| `description` | Full job description | "We are looking for..." |
| `location` | City, State or "Remote" | Chicago, IL |

#### Optional Columns

| Column | Description | Example |
|--------|-------------|---------|
| `company` | Company name (defaults to your profile) | Acme Corp |
| `salary` | Salary range | $80,000 - $120,000 |
| `is_active` | true/false (defaults to true) | true |

### Step 4: Format Your Data

**Important Tips:**

1. **Keep the header row** - Don't delete or rename the column headers
2. **Use quotes for descriptions** - If your description contains commas, wrap it in quotes:
   ```
   "This role requires Python, Django, and SQL skills."
   ```
3. **One job per row** - Each row becomes one job posting
4. **UTF-8 encoding** - Save as CSV UTF-8 format (especially important for special characters)

### Step 5: Upload Your File

1. Click **"Choose File"** and select your CSV
2. Click **"Upload Jobs"**
3. Review the success/error messages

### Understanding Results

- **Success message**: "Successfully imported X job(s)!"
- **Warning message**: Shows which rows failed and why
- **Error message**: File couldn't be processed (check format)

---

## Example CSV Content

```csv
title,company,description,location,salary,is_active
Software Engineer,Acme Corp,"Develop web applications using Python and Django. Requirements: 3+ years experience with Python, familiarity with REST APIs, and strong problem-solving skills.",Chicago IL,$80000-$120000,true
Marketing Manager,Acme Corp,"Lead marketing campaigns and brand strategy. Must have 5+ years marketing experience, excellent communication skills, and a track record of successful campaigns.",Remote,$70000-$90000,true
Data Analyst,Acme Corp,"Analyze business data and create actionable reports. SQL and Excel required. Experience with Python or R is a plus.",New York NY,$65000-$85000,true
```

---

## Common Issues & Solutions

### "Missing required field(s)"
**Cause**: A row is missing title, description, or location
**Fix**: Ensure every row has values in all required columns

### "Company name required"
**Cause**: No company in CSV and none set in your profile
**Fix**: Either add a company column or update your profile's company name

### File won't upload
**Cause**: Wrong file format
**Fix**: Save as `.csv` not `.xlsx` or `.xls`

### Special characters appear wrong
**Cause**: Wrong encoding
**Fix**: Save as "CSV UTF-8" in Excel, or select UTF-8 encoding in your spreadsheet app

### Descriptions are cut off
**Cause**: Excel may truncate long text
**Fix**: Use Google Sheets for long descriptions, or edit the CSV in a text editor

---

## For Administrators

Admins can bulk upload via the Django Admin panel:

1. Go to `/admin/`
2. Click **Jobs** under the Jobs section
3. Click **"Import Jobs from CSV"** button (top right)
4. Upload your CSV file
5. Jobs will be attributed to your admin account

---

## Best Practices

1. **Start small** - Test with 2-3 jobs first before uploading hundreds
2. **Review before upload** - Double-check your CSV in a spreadsheet program
3. **Use the template** - It ensures correct column names and format
4. **Keep backups** - Save your CSV before uploading
5. **Check results** - Review imported jobs on your dashboard

---

## Need Help?

If you encounter issues:
1. Check the error messages for specific row numbers
2. Review this guide's Common Issues section
3. Contact support at support@realjobsrealpeople.net
