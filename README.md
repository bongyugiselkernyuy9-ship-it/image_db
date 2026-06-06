# Antigravity Document & Employee Management System

A secure, functional, and modern Flask web application designed for centralizing employee records and managing corporate documents/images.

## Core Features

- **Role-Based Authentication**:
  - `Admin`: Full permissions to manage employee profiles, register new system users, upload/download/view files, review immutable system audit logs, and delete files.
  - `Employee`: Access to upload, search, view, and download documents. Restrained from modifying employee records, registering users, or deleting documents.
- **Document & Image Center**:
  - Drag-and-drop file dropzone with tags and employee linkage.
  - Formats: JPG, PNG, PDF, DOC, DOCX, XLS, XLSX.
  - Safe file size limit: up to 2 GB.
  - In-browser image preview (with PIL verification to prevent file spoofing/corruption).
- **Compliance Logging**:
  - High-integrity audit log capturing every download, view, delete, modifications to employees, and system authentications.
- **Advanced Search Index**:
  - Query files by filename, linked employee name, tags, file type groups, and upload date ranges.
- **Aesthetic Premium UI**:
  - Modern dark layout with Outfit/Inter typography, neon glow states, responsive design, and smooth hover micro-animations.

---

## Security Implementation

1. **Path Traversal Protection**: All uploaded documents are renamed with a secure UUID hash prefix on disk. The system resolves requests explicitly from the designated upload folder and performs database record existence verification before serving resources.
2. **Anti-XSS Escaping**: Automatically sanitizes and escapes all user inputs in rendering templates (e.g. usernames, tags, file names) using Jinja2 autoescaping.
3. **MIME Spoofing Validation**: Validates the file extension and compares the client's MIME header against an expected list of allowed MIME types to prevent script execution vectors.
4. **Image Integrity Verification**: Checks image streams using the `Pillow` library to confirm image structures are not corrupted or malicious wrappers.
5. **CSRF Protection**: All POST operations are protected by `Flask-WTF` CSRF token verification.
6. **Session Security**: Session cookies configured with `HttpOnly=True` and path isolation rules.

---

## Setup Instructions

Ensure you have **Python 3.9+** installed (verified up to Python 3.14).

### 1. Create Virtual Environment

Open your terminal (PowerShell on Windows) in the project root directory and run:

```powershell
# Create venv
py -m venv venv

# Activate venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

Install all the required python modules using pip:

```powershell
pip install -r requirements.txt
```

### 3. Generate Initial Administrator Account

Before running the web app, you must seed the database with an administrator account. Use our secure generator script:

```powershell
python create_admin.py
```
*You will be prompted to enter a username, select a password (minimum 6 characters), and confirm.*

### 4. Set Environment Variables (Optional)

By default, the application runs on a development secret key. For a staging/production run, configure the `SECRET_KEY` environment variable:

```powershell
# In PowerShell:
$env:SECRET_KEY="your-random-long-secret-key-string"
```

### 5. Launch the Application

Start the Flask development server:

```powershell
python run.py
```

The application will initialize the database (under `instance/app.db`) and start running locally at:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Project Structure

```
image_db/
├── app/
│   ├── __init__.py          # App initialization & configurations
│   ├── models.py            # SQLAlchemy schemas (User, Employee, FileMetadata, AuditLog)
│   ├── forms.py             # Flask-WTF validation forms
│   ├── routes.py            # Route decorators, validation logic, & views
│   ├── templates/           # Jinja templates (Bootstrap 5 & Custom Style)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── employees.html
│   │   ├── employee_form.html
│   │   ├── employee_detail.html
│   │   ├── files.html
│   │   ├── file_detail.html
│   │   ├── search.html
│   │   └── audit_logs.html
│   └── static/              # Assets
│       ├── css/
│       │   └── style.css    # Custom CSS variables, dark layout & animations
│       └── js/
│           └── main.js      # JS for Alerts, drag & drop previews
├── instance/                # Local SQLite DB location
├── uploads/                 # Local directory for saving physical documents
├── requirements.txt         # Dependent Python modules
├── create_admin.py          # Seeding script for admin
├── run.py                   # Server wrapper launcher
├── test_app.py              # Automated test suite
└── README.md                # Documentation
```

---

## Running the Unit Tests

To run the automated security and validation test suite:

```powershell
python test_app.py
```
