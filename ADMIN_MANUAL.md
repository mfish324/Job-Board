# Real Jobs, Real People - Admin Manual

This guide explains how to manage the site through the Django Admin dashboard.

## Accessing Admin

1. Go to `https://realjobsrealpeople.net/admin/`
2. Log in with your superuser credentials

---

## Managing Jobs

### View All Jobs
- Click **Jobs** in the sidebar
- You'll see: Title, Company, Location, Posted By, Active Status, Posted Date

### Quick Actions (from list view)
- **Toggle Active**: Click the checkbox in the "Is Active" column to activate/deactivate jobs
- **Filter**: Use the right sidebar to filter by active status, date, or location
- **Search**: Use the search bar to find jobs by title, company, description, or location

### Edit a Job
1. Click on the job title
2. Modify any fields (title, company, description, location, salary)
3. Click **Save**

### Delete a Job
**Option 1 - Single job:**
1. Click on the job title to open it
2. Click **Delete** at the bottom
3. Confirm deletion

**Option 2 - Multiple jobs:**
1. Check the boxes next to jobs you want to delete
2. Select "Delete selected jobs" from the Action dropdown
3. Click **Go**
4. Confirm deletion

### Deactivate vs Delete
- **Deactivate**: Uncheck "Is active" - job is hidden but preserved
- **Delete**: Permanently removes the job and all its applications

---

## Managing Users

### View All Users
- Click **User profiles** in the sidebar
- You'll see: Username, User Type, Phone, Company Name, Experience Years, Recruiter Approved

### Filter Users
Use the right sidebar to filter by:
- **User type**: Job Seeker, Employer, or Recruiter
- **Recruiter approved**: Yes/No (for recruiter accounts)

### Edit a User Profile
1. Click on the username
2. Expand the relevant section:
   - **User Info**: Basic info, user type, phone
   - **Job Seeker Details**: Resume, skills, experience, LinkedIn, profile visibility
   - **Employer Details**: Company name, logo, website, description
   - **Recruiter Details**: Agency info, LinkedIn, approval status
3. Click **Save**

---

## Approving Recruiters

Recruiters require admin approval before they can search candidates.

### View Pending Recruiters
1. Go to **User profiles**
2. Filter by **User type** = "recruiter"
3. Filter by **Is recruiter approved** = "No"

### Approve a Recruiter

**Option 1 - Quick approve (from list):**
- Click the checkbox in the "Is Recruiter Approved" column

**Option 2 - Bulk approve:**
1. Check the boxes next to recruiters to approve
2. Select **"Approve selected recruiters"** from the Action dropdown
3. Click **Go**

**Option 3 - From detail view:**
1. Click on the recruiter's username
2. Expand "Recruiter Details"
3. Check "Is recruiter approved"
4. Click **Save**

### What to Verify Before Approving
- LinkedIn URL is valid and matches a real professional profile
- Agency name (if not independent) is a legitimate company
- Phone and email are verified (check Phone verifications and Email verifications)

### Revoke Recruiter Access
1. Select the recruiter(s)
2. Choose **"Reject/Revoke selected recruiters"** from Actions
3. Click **Go**

---

## Managing Job Applications

### View Applications
- Click **Job applications** in the sidebar
- You'll see: Applicant, Job, Status, Applied Date

### Update Application Status
- Click the status dropdown in the list view to change status
- Or click on an application to view/edit details

### Filter Applications
- By status: Pending, Reviewed, Interviewed, Offered, Hired, Rejected
- By date: Use the date hierarchy at the top

---

## Verification Management

### Phone Verifications
- Click **Phone verifications** in the sidebar
- View who has verified their phone number
- See verification timestamps

### Email Verifications
- Click **Email verifications** in the sidebar
- View who has verified their email
- See verification timestamps

---

## Other Admin Sections

### Saved Jobs
View which users have saved which jobs.

### Hiring Stages (ATS)
Manage custom hiring pipeline stages for employers.

### Email Templates
View/edit email templates employers have created.

### Notifications
View all system notifications sent to users.

### Email Logs
Track all emails sent from the platform.

### Team Management
- **Employer teams**: View employer team structures
- **Team members**: See who belongs to which teams
- **Team invitations**: Track pending invitations

### Activity Logs
View all team activity (useful for auditing).

### Chat Logs
View chatbot conversations for monitoring/improvement.

---

## Common Tasks

### Manually Verify a User
If a user has trouble with verification:
1. Go to **Phone verifications** or **Email verifications**
2. Find their record
3. Check "Is verified"
4. Save

### Change User Type
1. Go to **User profiles**
2. Click on the user
3. Change "User type" dropdown
4. Save

Note: Changing user types may cause issues if the user has existing data (e.g., job postings as employer). Use with caution.

### View User's Applications
1. Go to **Job applications**
2. Search for the username in the search bar

### View Job's Applications
1. Go to **Job applications**
2. Search for the job title in the search bar

---

## Tips

1. **Use filters**: The right sidebar filters are powerful for finding specific records
2. **Bulk actions**: Select multiple items and use the Action dropdown for efficiency
3. **Search**: The search bar searches multiple fields at once
4. **Date hierarchy**: Click on years/months/days at the top to navigate by date
5. **List editable**: Some fields can be edited directly from the list view (checkboxes, dropdowns)

---

## Security Notes

- Never share admin credentials
- Log out when done (especially on shared computers)
- Review recruiter approvals carefully - they gain access to job seeker data
- Regularly review the activity logs for suspicious behavior
