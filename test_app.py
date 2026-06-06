import unittest
import os
import io
from datetime import datetime
from flask import url_for
from app import create_app
from app.models import db, User, Employee, FileMetadata, AuditLog

class AntigravityAppTestCase(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite database for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier form testing
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Create test admin
        self.admin = User(username='test_admin', role='admin')
        self.admin.set_password('123456')
        # Create test employee user
        self.employee_user = User(username='test_employee', role='employee')
        self.employee_user.set_password('654321')
        
        db.session.add(self.admin)
        db.session.add(self.employee_user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # --- TESTING AUTHENTICATION & RBAC ---

    def test_user_password_hashing(self):
        self.assertTrue(self.admin.check_password('123456'))
        self.assertFalse(self.admin.check_password('wrongpass'))
        self.assertEqual(self.admin.role, 'admin')
        self.assertEqual(self.employee_user.role, 'employee')

    def test_login_logout(self):
        # Test non-numeric password is blocked by form validation
        response = self.login('test_admin', 'badpass')
        self.assertIn(b'Password must contain only numbers.', response.data)

        # Test invalid numeric login first (when session is anonymous)
        response = self.login('test_admin', '999999')
        self.assertIn(b'Invalid username or password.', response.data)

        # Test valid login
        response = self.login('test_admin', '123456')
        self.assertIn(b'test_admin', response.data)
        
        # Test audit log for login
        log = AuditLog.query.filter_by(action='LOGIN_SUCCESS').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.username, 'test_admin')
        
        # Test audit log for failed login
        fail_log = AuditLog.query.filter_by(action='LOGIN_FAILURE').first()
        self.assertIsNotNone(fail_log)

    def test_role_based_access_controls(self):
        # Access control limit: employees cannot register new users or manage employee records
        
        # 1. Anonymous user blocked
        response = self.client.get('/register-user')
        self.assertEqual(response.status_code, 302)  # Redirects to login page
        
        # 2. Employee login
        self.login('test_employee', '654321')
        
        # Try to register user -> Forbidden
        response = self.client.get('/register-user')
        self.assertEqual(response.status_code, 403)
        
        # Try to add employee -> Forbidden
        response = self.client.get('/employees/add')
        self.assertEqual(response.status_code, 403)
        
        self.logout()
        
        # 3. Admin login
        self.login('test_admin', '123456')
        
        # Try to register user -> Success (renders page)
        response = self.client.get('/register-user')
        self.assertEqual(response.status_code, 200)
        
        # Try to add employee -> Success
        response = self.client.get('/employees/add')
        self.assertEqual(response.status_code, 200)

    # --- TESTING EMPLOYEE RECORDS ---

    def test_employee_creation_and_view(self):
        self.login('test_admin', '123456')
        
        # Add employee
        response = self.client.post('/employees/add', data=dict(
            full_name='Test Subject',
            employee_id='EMP-TEST-001',
            department='QA',
            position='Verifier',
            email='test@co.com',
            phone='12345678',
            hire_date='2026-05-22'
        ), follow_redirects=True)
        
        self.assertIn(b'Test Subject', response.data)
        
        # Verify DB entry
        emp = Employee.query.filter_by(employee_id='EMP-TEST-001').first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.full_name, 'Test Subject')
        self.assertEqual(emp.created_by_id, self.admin.id)
        
        # Verify Audit Log
        log = AuditLog.query.filter_by(action='CREATE_EMPLOYEE_RECORD').first()
        self.assertIsNotNone(log)
        self.assertIn('EMP-TEST-001', log.details)

    # --- TESTING FILE MANAGEMENT & SECURITY ---

    def test_file_upload_security_validations(self):
        self.login('test_admin', '123456')
        
        # First, need an employee to link to
        emp = Employee(
            full_name='Subject A',
            employee_id='EMP-A',
            department='Ops',
            position='Staff',
            email='a@co.com',
            phone='123',
            hire_date=datetime.now().date(),
            created_by_id=self.admin.id
        )
        db.session.add(emp)
        db.session.commit()
        
        # 1. Verify rejected extension (e.g. .exe)
        response = self.client.post('/files/upload', data=dict(
            file=(io.BytesIO(b"executable content"), "malicious.exe"),
            employee_id=emp.id,
            tags="malicious"
        ), follow_redirects=True)
        self.assertIn(b'Extension .exe is not allowed.', response.data)
        
        # 2. Verify rejected spoofed MIME type (e.g. PDF file but sending image/png)
        # Here we attempt to upload a text file with a mismatch MIME
        response = self.client.post('/files/upload', data=dict(
            file=(io.BytesIO(b"%PDF-1.4..."), "report.pdf"),
            employee_id=emp.id,
            tags="report"
        ), content_type='multipart/form-data', follow_redirects=True)
        
        # Werkzeug sets default Content-Type based on extension if not specified.
        # But if the client explicitly sends an invalid content-type:
        data = {
            'file': (io.BytesIO(b"%PDF-1.4..."), "report.pdf", "image/png"), # Spoofed
            'employee_id': emp.id,
            'tags': 'report'
        }
        response = self.client.post('/files/upload', data=data, follow_redirects=True)
        self.assertIn(b'Security Alert: File type mismatch', response.data)
        
        # 3. Verify successful file upload
        data = {
            'file': (io.BytesIO(b"%PDF-1.4..."), "report.pdf", "application/pdf"),
            'employee_id': emp.id,
            'tags': 'secure, test'
        }
        response = self.client.post('/files/upload', data=data, follow_redirects=True)
        self.assertIn(b"File &#39;report.pdf&#39; uploaded successfully.", response.data)
        
        # Check DB entry
        file_meta = FileMetadata.query.filter_by(original_name='report.pdf').first()
        self.assertIsNotNone(file_meta)
        self.assertEqual(file_meta.employee_id, emp.id)
        
        # Check path traversal block on raw upload requests
        response = self.client.get(f"/uploads/../test_app.py")
        self.assertIn(response.status_code, {400, 403, 404})

if __name__ == '__main__':
    unittest.main()
