# Rahul HRMS

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2+-green.svg)](https://www.djangoproject.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%20%26%20Storage-emerald.svg)](https://supabase.com/)
[![License: LGPL v2.1](https://img.shields.io/badge/License-LGPL%20v2.1-blue.svg)](LICENSE)

> **Rahul HRMS is a production-ready, cloud-native Human Resource Management System customized and powered by Supabase PostgreSQL and Supabase Storage.**
> *Based on and customized from the open-source Horilla HRMS core architecture.*

---

## 🚀 Key Modules & Capabilities

- 👥 **Workforce & Employee Management**: Complete employee profiles, bank details, work histories, departmental structures, reporting hierarchies, and document registries.
- ⏰ **Attendance & Shift Scheduling**: Shift rotation, work type requests, biometric device integration, late come/early out tracking, and real-time attendance validation.
- 🏖️ **Leave & Encashment**: Multi-level leave policy configurations, balance ledgers, compensatory leave workflows, holiday calendars, and encashment settings.
- 🎯 **Recruitment & Applicant Tracking**: Interactive candidate pipelines, interview scheduling, automated surveys, and spaCy NLP resume parser.
- 💰 **Payroll & Compensation**: Salary slips, customizable allowances, tax deductions, reimbursements, and automated payslip generation.
- 📊 **Performance Management (PMS)**: 360-degree feedback, Key Results, Objectives & OKR tracking, and appraisal cycles.
- 📁 **Cloud Media & Document Storage**: Full Supabase Storage integration with private buckets and signed secure URLs for sensitive HR documents, certifications, and contracts.
- 📈 **Analytics & Reports**: Visual dashboards, exportable Excel/CSV datasets, and PDF summaries.
- 🔐 **Enterprise Security & Permissions**: Role-based access control (RBAC), company-scoped authorization, session protection, and audit logging.

---

## 🏗 System Architecture & Infrastructure

- **Backend Framework**: Django 5.2 (Python 3.12)
- **Primary Relational Database**: Supabase PostgreSQL (PostgreSQL 17 via direct connection or PgBouncer Session/Transaction pooler)
- **Cloud Object Storage**: Supabase Storage (`rahul-hrms` private bucket)
- **Asynchronous Tasks & Scheduling**: APScheduler / Redis
- **Security & Media**: WhiteNoise static file compression, signed token URLs for employee media

---

## ⚡ Quick Start & Local Setup

### 1. Prerequisites
- Python 3.11 or Python 3.12
- Git
- Access to Supabase Project (PostgreSQL database and Storage)

### 2. Clone the Repository
```bash
git clone https://github.com/krish0000987-netizen/hrms-rahul-shukal-.git
cd hrms-rahul-shukal-
```

### 3. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env` with your Supabase credentials and database connection details:
```ini
DEBUG=True
SECRET_KEY=your-secure-django-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,*
TIME_ZONE=Asia/Kolkata

# Supabase Credentials
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<your-supabase-publishable-key>
SUPABASE_SECRET_KEY=<your-supabase-secret-key>
SUPABASE_SERVICE_ROLE_KEY=<your-supabase-service-role-key>
SUPABASE_STORAGE_BUCKET=rahul-hrms
USE_SUPABASE_STORAGE=True

# Supabase PostgreSQL Database Connection
DATABASE_URL=postgresql://postgres.<project-ref>:<db-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

### 5. Run Database Migrations
Apply all schema migrations to your Supabase PostgreSQL database:
```bash
python manage.py migrate
```

### 6. Create Initial Admin User
Create your Rahul HRMS superuser administrator:
```bash
python manage.py createrahuluser
# or standard Django: python manage.py createsuperuser
```

### 7. Run the Development Server
```bash
python manage.py runserver 8000
```
Visit **[http://localhost:8000](http://localhost:8000)** in your browser and sign in.

---

## 🐳 Docker Deployment

To run Rahul HRMS in production using Docker:

```bash
# Build and run the containers
docker-compose up -d --build

# Run migrations inside the container
docker-compose exec web python manage.py migrate

# Access the service
open http://localhost:8000
```

---

## 🧪 Testing & Verification

Run Django system checks and automated test suites:
```bash
# Verify system integrity
python manage.py check

# Run test suite
python manage.py test base employee attendance leave payroll
```

---

## 📄 License & Attribution

This project is licensed under the **GNU Lesser General Public License v2.1 (LGPL-2.1)**.
Rahul HRMS builds upon the open-source Horilla HRMS framework and incorporates custom enterprise branding, Supabase PostgreSQL, and Supabase Storage integrations.
See the [LICENSE](LICENSE) file for complete details.
