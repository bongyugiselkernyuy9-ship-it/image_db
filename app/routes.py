import os
import shutil
import uuid
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_from_directory, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from PIL import Image
import io

from app.models import db, User, Employee, FileMetadata, FileView, AuditLog
from app.forms import LoginForm, RegisterForm, EmployeeForm, FileUploadForm, SearchForm

bp = Blueprint('main', __name__)

# Allowed extensions and their corresponding MIME types
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
MIME_MAPPING = {
    'jpg': ['image/jpeg', 'image/pjpeg'],
    'jpeg': ['image/jpeg', 'image/pjpeg'],
    'png': ['image/png'],
    'pdf': ['application/pdf'],
    'doc': ['application/msword'],
    'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    'xls': ['application/vnd.ms-excel'],
    'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
}

# Helper to write audit logs
def log_action(action, details=None):
    username = current_user.username if current_user.is_authenticated else 'Anonymous'
    user_id = current_user.id if current_user.is_authenticated else None
    
    log = AuditLog(
        action=action,
        user_id=user_id,
        username=username,
        details=details
    )
    db.session.add(log)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging action {action}: {str(e)}")

# Decorator to restrict routes to admin role
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            log_action('UNAUTHORIZED_ACCESS_ATTEMPT', f"Access denied to route: {request.path}")
            flash('Access denied. Administrator privileges are required.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Helper for filename extraction
def get_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


# ============================================================
# HELPER FUNCTIONS: View-Before-Delete & Soft Delete
# ============================================================

def can_delete(user, file):
    """Check whether a user is allowed to delete a specific file.
    
    Returns True ONLY if ALL three conditions are met:
      1. The user is the original uploader of the file.
      2. The user has previously viewed the file (record in file_views).
      3. The file is not already soft-deleted.
    
    This function performs SERVER-SIDE security checks and should be
    called on every delete attempt. Never trust the client-side UI.
    """
    # Condition 1: Ownership – user must be the uploader
    if user.id != file.uploader_id:
        return False
    
    # Condition 2: View prerequisite – user must have viewed the file
    view_record = FileView.query.filter_by(
        file_id=file.id,
        user_id=user.id
    ).first()
    if view_record is None:
        return False
    
    # Condition 3: File must not already be soft-deleted
    if file.deleted:
        return False
    
    return True


def record_file_view(user, file):
    """Record that a user has viewed a specific file.
    
    If a view record already exists for this user+file pair, no duplicate
    is created (enforced by the unique constraint in the database).
    
    Also logs the view action to the audit log for non-repudiation.
    
    Returns the FileView record (existing or newly created).
    """
    # Check if the user has already viewed this file
    existing_view = FileView.query.filter_by(
        file_id=file.id,
        user_id=user.id
    ).first()
    
    if existing_view:
        return existing_view
    
    # Create a new view record
    new_view = FileView(
        file_id=file.id,
        user_id=user.id
    )
    db.session.add(new_view)
    try:
        db.session.commit()
        # Audit log: record the view action (non-repudiation)
        log_action('FILE_VIEWED', 
                   f"Viewed file: {file.original_name} (ID: {file.id}). "
                   f"Viewed before deletion allowed.")
    except Exception as e:
        db.session.rollback()
        print(f"Error recording file view: {str(e)}")
    
    return new_view


# --- AUTH ROUTES ---

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            log_action('LOGIN_SUCCESS', f"User {user.username} logged in.")
            flash(f"Welcome back, {user.username}!", "success")
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            log_action('LOGIN_FAILURE', f"Failed login attempt for username: {form.username.data}")
            flash("Invalid username or password.", "danger")
            
    return render_template('login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    log_action('LOGOUT', f"User {current_user.username} logged out.")
    logout_user()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('main.login'))


@bp.route('/register-user', methods=['GET', 'POST'])
@login_required
@admin_required
def register_employee():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            log_action('REGISTER_USER', f"Created account {user.username} with role: {user.role}")
            flash(f"User account '{user.username}' created successfully.", "success")
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash("Error creating user account. Please try again.", "danger")
            print(f"Error registering user: {str(e)}")
        
    return render_template('register_employee.html', form=form)


# --- GENERAL ROUTES ---

@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    # Only count non-deleted files in dashboard stats
    employee_count = Employee.query.count()
    file_count = FileMetadata.query.filter_by(deleted=False).count()
    
    # Calculate storage (only active, non-deleted files)
    files = FileMetadata.query.filter_by(deleted=False).all()
    total_storage = sum(f.size for f in files) if files else 0
    
    log_count = AuditLog.query.count()
    
    # Recent files: exclude soft-deleted files
    recent_files = FileMetadata.query.filter_by(deleted=False).order_by(
        FileMetadata.upload_date.desc()
    ).limit(5).all()
    
    # Fetch recent logs (Admin only)
    recent_logs = []
    if current_user.is_admin:
        recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()
        
    return render_template(
        'dashboard.html',
        employee_count=employee_count,
        file_count=file_count,
        total_storage=total_storage,
        log_count=log_count,
        recent_files=recent_files,
        recent_logs=recent_logs
    )


# --- EMPLOYEE ROUTES ---

@bp.route('/employees')
@login_required
def employees():
    log_action('VIEW_EMPLOYEE_LIST', "Viewed all employee records.")
    all_employees = Employee.query.order_by(Employee.full_name).all()
    return render_template('employees.html', employees=all_employees)


@bp.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    form = EmployeeForm()
    if form.validate_on_submit():
        photo_filename = None
        
        # Handle employee profile photo if uploaded
        if form.photo.data:
            photo_file = form.photo.data
            ext = get_extension(photo_file.filename)
            
            # Simple integrity verification for images
            try:
                img_data = photo_file.read()
                photo_file.seek(0)
                img = Image.open(io.BytesIO(img_data))
                img.verify()
            except Exception:
                flash("Invalid profile image format.", "danger")
                return render_template('employee_form.html', form=form, title="Add Employee")
                
            photo_filename = f"photo_{uuid.uuid4().hex}.{ext}"
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
            photo_file.save(photo_path)
            
        employee = Employee(
            full_name=form.full_name.data,
            employee_id=form.employee_id.data,
            department=form.department.data,
            position=form.position.data,
            email=form.email.data,
            phone=form.phone.data,
            hire_date=form.hire_date.data,
            photo=photo_filename,
            created_by_id=current_user.id
        )
        db.session.add(employee)
        try:
            db.session.commit()
            log_action('CREATE_EMPLOYEE_RECORD', f"Created employee record {employee.full_name} ({employee.employee_id})")
            flash(f"Employee record for {employee.full_name} added.", "success")
            return redirect(url_for('main.employees'))
        except Exception as e:
            db.session.rollback()
            flash("Error creating employee record. Please try again.", "danger")
            print(f"Error adding employee: {str(e)}")
        
    return render_template('employee_form.html', form=form, title="Add Employee")


@bp.route('/employees/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(id):
    employee = Employee.query.get_or_404(id)
    form = EmployeeForm(original_employee_id=employee.employee_id, obj=employee)
    
    if form.validate_on_submit():
        if form.photo.data:
            # Delete old photo if it exists
            if employee.photo:
                old_photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], employee.photo)
                if os.path.exists(old_photo_path):
                    os.remove(old_photo_path)
                    
            photo_file = form.photo.data
            ext = get_extension(photo_file.filename)
            
            try:
                img_data = photo_file.read()
                photo_file.seek(0)
                img = Image.open(io.BytesIO(img_data))
                img.verify()
            except Exception:
                flash("Invalid profile image format.", "danger")
                return render_template('employee_form.html', form=form, title="Edit Employee", employee=employee)
                
            photo_filename = f"photo_{uuid.uuid4().hex}.{ext}"
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
            photo_file.save(photo_path)
            employee.photo = photo_filename
            
        employee.full_name = form.full_name.data
        employee.employee_id = form.employee_id.data
        employee.department = form.department.data
        employee.position = form.position.data
        employee.email = form.email.data
        employee.phone = form.phone.data
        employee.hire_date = form.hire_date.data
        
        try:
            db.session.commit()
            log_action('EDIT_EMPLOYEE_RECORD', f"Modified employee record {employee.full_name} ({employee.employee_id})")
            flash(f"Employee record for {employee.full_name} updated successfully.", "success")
            return redirect(url_for('main.employees'))
        except Exception as e:
            db.session.rollback()
            flash("Error updating employee record. Please try again.", "danger")
            print(f"Error editing employee: {str(e)}")
        
    return render_template('employee_form.html', form=form, title="Edit Employee", employee=employee)


@bp.route('/employees/<int:id>')
@login_required
def employee_detail(id):
    employee = Employee.query.get_or_404(id)
    log_action('VIEW_EMPLOYEE_DETAILS', f"Viewed records for employee: {employee.full_name}")
    
    # Filter out soft-deleted files from the employee's linked files
    active_files = FileMetadata.query.filter_by(
        employee_id=employee.id,
        deleted=False
    ).all()
    
    return render_template('employee_detail.html', employee=employee, active_files=active_files)


# --- FILE AND IMAGE MANAGEMENT ---

@bp.route('/files')
@login_required
def files():
    upload_form = FileUploadForm()
    # Populate the employee choices dynamically
    employees = Employee.query.all()
    upload_form.employee_id.choices = [(e.id, f"{e.full_name} ({e.employee_id})") for e in employees]
    
    # Only show non-deleted files in the main library
    all_files = FileMetadata.query.filter_by(deleted=False).order_by(
        FileMetadata.upload_date.desc()
    ).all()
    
    # Build a set of file IDs the current user has viewed
    # This is used by the template to decide whether to show the Delete button
    user_viewed_ids = set()
    user_views = FileView.query.filter_by(user_id=current_user.id).all()
    for v in user_views:
        user_viewed_ids.add(v.file_id)
    
    return render_template(
        'files.html', 
        upload_form=upload_form, 
        files=all_files, 
        employees_exist=len(employees) > 0,
        viewed_file_ids=user_viewed_ids
    )


@bp.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    upload_form = FileUploadForm()
    employees = Employee.query.all()
    upload_form.employee_id.choices = [(e.id, f"{e.full_name} ({e.employee_id})") for e in employees]
    
    if upload_form.validate_on_submit():
        file = upload_form.file.data
        original_filename = file.filename
        
        # 1. Path traversal & filename safety check
        safe_name = secure_filename(original_filename)
        if not safe_name or safe_name in {'.', '..'}:
            flash("Invalid filename.", "danger")
            return redirect(url_for('main.files'))
            
        ext = get_extension(safe_name)
        
        # 2. Extension Allowed Check
        if ext not in ALLOWED_EXTENSIONS:
            flash(f"Extension .{ext} is not allowed.", "danger")
            return redirect(url_for('main.files'))
            
        # 3. MIME type double validation (Anti-spoofing check)
        mime_type = file.content_type
        expected_mimes = MIME_MAPPING.get(ext, [])
        if mime_type not in expected_mimes:
            log_action('UPLOAD_SECURITY_ALERT', f"MIME type spoofing suspected for file {original_filename}. Got: {mime_type}")
            flash(f"Security Alert: File type mismatch (MIME: {mime_type} vs Ext: .{ext}). Upload rejected.", "danger")
            return redirect(url_for('main.files'))
            
        # 4. Image integrity check using Pillow
        if ext in {'jpg', 'jpeg', 'png'}:
            try:
                img_data = file.read()
                file.seek(0)  # Reset stream pointer
                img = Image.open(io.BytesIO(img_data))
                img.verify()
            except Exception:
                log_action('UPLOAD_IMAGE_CORRUPTED', f"Attempted upload of invalid image: {original_filename}")
                flash("Uploaded image is corrupted or invalid.", "danger")
                return redirect(url_for('main.files'))
        
        # 5. Read file size
        file.seek(0, os.SEEK_END)
        size_in_bytes = file.tell()
        file.seek(0)
        
        # Final server-side 2GB check
        if size_in_bytes > current_app.config['MAX_CONTENT_LENGTH']:
            flash("File size exceeds 2 GB limit.", "danger")
            return redirect(url_for('main.files'))
            
        # Generate a unique disk filename to prevent overrides
        unique_filename = f"{uuid.uuid4().hex}_{safe_name}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(save_path)
        
        # Insert metadata
        file_meta = FileMetadata(
            filename=unique_filename,
            original_name=original_filename,
            file_type=mime_type,
            size=size_in_bytes,
            tags=upload_form.tags.data,
            uploader_id=current_user.id,
            employee_id=upload_form.employee_id.data
        )
        db.session.add(file_meta)
        try:
            db.session.commit()
            log_action('UPLOAD_FILE', f"Uploaded file: {original_filename} (Linked to Employee ID: {upload_form.employee_id.data})")
            flash(f"File '{original_filename}' uploaded successfully.", "success")
        except Exception as e:
            db.session.rollback()
            # Try to remove the file from disk if database insert failed
            try:
                os.remove(save_path)
            except:
                pass
            flash("Error saving file metadata. Please try again.", "danger")
            print(f"Error uploading file: {str(e)}")
    else:
        # Flash form errors if any
        for field, errors in upload_form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", "danger")
                
    return redirect(url_for('main.files'))


@bp.route('/files/<int:id>')
@login_required
def file_detail(id):
    file = FileMetadata.query.get_or_404(id)
    
    # SECURITY: Block access to soft-deleted files
    if file.deleted:
        flash("This file has been deleted and is no longer accessible.", "warning")
        return redirect(url_for('main.files'))
    
    # Record the view in file_views table (creates entry if not exists)
    record_file_view(current_user, file)
    
    # Determine if the current user can delete this file
    delete_allowed = can_delete(current_user, file)
    
    log_action('VIEW_FILE_METADATA', f"Viewed metadata details for file: {file.original_name}")
    return render_template('file_detail.html', file=file, can_delete=delete_allowed)


@bp.route('/files/<int:id>/download')
@login_required
def download_file(id):
    file = FileMetadata.query.get_or_404(id)
    
    # SECURITY: Block download of soft-deleted files
    if file.deleted:
        flash("This file has been deleted and is no longer accessible.", "warning")
        return redirect(url_for('main.files'))
    
    # Record the view when downloading (viewing the file content)
    record_file_view(current_user, file)
    
    # Secure download wrapper to prevent path traversal
    # Resolves from UPLOAD_FOLDER explicitly, checking filename exist in db
    safe_filename = file.filename
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_filename)
    if not os.path.exists(file_path):
        log_action('DOWNLOAD_FILE_ERROR', f"Requested file {safe_filename} was missing from disk.")
        flash("The physical file is missing from disk storage.", "danger")
        return redirect(url_for('main.files'))
        
    log_action('DOWNLOAD_FILE', f"Downloaded file: {file.original_name}")
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        safe_filename,
        as_attachment=True,
        download_name=file.original_name
    )


@bp.route('/files/<int:id>/delete', methods=['POST'])
@login_required
def delete_file(id):
    """Soft-delete a file: move to trash folder and mark as deleted in DB.
    
    Security checks (all server-side):
      1. User must be the original uploader of the file.
      2. User must have previously viewed the file.
      3. File must not already be soft-deleted.
    """
    file = FileMetadata.query.get_or_404(id)
    
    # SERVER-SIDE SECURITY: Verify all deletion prerequisites
    if not can_delete(current_user, file):
        log_action('DELETE_DENIED', 
                   f"Delete denied for file: {file.original_name} (ID: {file.id}). "
                   f"User: {current_user.username}. Reason: prerequisites not met.")
        flash("You are not authorized to delete this file. "
              "You must be the uploader and have viewed the file first.", "danger")
        return redirect(url_for('main.file_detail', id=file.id))
    
    # Get the view record ID for audit trail (non-repudiation)
    view_record = FileView.query.filter_by(
        file_id=file.id,
        user_id=current_user.id
    ).first()
    
    # Move the physical file from uploads/ to trash/
    source_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    trash_path = os.path.join(current_app.config['TRASH_FOLDER'], file.filename)
    
    if os.path.exists(source_path):
        shutil.move(source_path, trash_path)
    
    # Update database: mark as soft-deleted
    file.deleted = True
    file.deleted_at = datetime.utcnow()
    file.deleted_by = current_user.id
    try:
        db.session.commit()
        # Audit log: record the deletion with link to the view record
        log_action('FILE_DELETED', 
                   f"Soft deleted file: {file.original_name} (ID: {file.id}). "
                   f"Soft deleted after viewing (view_id = {view_record.id}). ")
        flash(f"File '{file.original_name}' has been moved to trash.", "success")
    except Exception as e:
        db.session.rollback()
        # Restore the physical file if database update failed
        try:
            shutil.move(trash_path, source_path)
        except:
            pass
        flash("Error deleting file. Please try again.", "danger")
        print(f"Error deleting file: {str(e)}")
        return redirect(url_for('main.file_detail', id=file.id))
    
    return redirect(url_for('main.files'))


# --- MY VIEWED FILES (View-Before-Delete List) ---

@bp.route('/my-viewed-files')
@login_required
def my_viewed_files():
    """Show files that the current user has both uploaded AND viewed AND are not deleted.
    
    On this list, the Delete button is always shown because the view
    prerequisite is inherently satisfied (the list only contains viewed files).
    """
    # Get IDs of files the user has viewed
    viewed_file_ids = [v.file_id for v in FileView.query.filter_by(
        user_id=current_user.id
    ).all()]
    
    # Query files that the user uploaded, has viewed, and are not deleted
    my_files = FileMetadata.query.filter(
        FileMetadata.id.in_(viewed_file_ids),
        FileMetadata.uploader_id == current_user.id,
        FileMetadata.deleted == False
    ).order_by(FileMetadata.upload_date.desc()).all()
    
    return render_template('my_viewed_files.html', files=my_files)


# --- ADMIN TRASH MANAGEMENT ---

@bp.route('/admin/trash')
@login_required
@admin_required
def admin_trash():
    """Admin-only page listing all soft-deleted files with Restore and Permanent Delete options."""
    deleted_files = FileMetadata.query.filter_by(deleted=True).order_by(
        FileMetadata.deleted_at.desc()
    ).all()
    
    log_action('VIEW_TRASH', "Admin accessed the trash management page.")
    return render_template('trash.html', files=deleted_files)


@bp.route('/admin/trash/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_file(id):
    """Restore a soft-deleted file: move back to uploads/ and clear deleted flags.
    
    Only admins can restore files. Restoration does NOT require viewing.
    """
    file = FileMetadata.query.get_or_404(id)
    
    if not file.deleted:
        flash("This file is not in the trash.", "warning")
        return redirect(url_for('main.admin_trash'))
    
    # Move the physical file back from trash/ to uploads/
    trash_path = os.path.join(current_app.config['TRASH_FOLDER'], file.filename)
    restore_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    
    if os.path.exists(trash_path):
        shutil.move(trash_path, restore_path)
    else:
        flash("Warning: Physical file was not found in trash folder.", "warning")
    
    # Update database: clear soft-delete flags
    file.deleted = False
    file.deleted_at = None
    file.deleted_by = None
    try:
        db.session.commit()
        log_action('FILE_RESTORED', 
                   f"Restored file from trash: {file.original_name} (ID: {file.id}).")
        flash(f"File '{file.original_name}' has been restored successfully.", "success")
    except Exception as e:
        db.session.rollback()
        # Restore the physical file back to trash if database update failed
        try:
            shutil.move(restore_path, trash_path)
        except:
            pass
        flash("Error restoring file. Please try again.", "danger")
        print(f"Error restoring file: {str(e)}")
        return redirect(url_for('main.admin_trash'))
    
    return redirect(url_for('main.admin_trash'))


@bp.route('/admin/trash/<int:id>/permanent-delete', methods=['POST'])
@login_required
@admin_required
def permanent_delete_file(id):
    """Permanently delete a file: remove from disk and database.
    
    Only admins can permanently delete files. This action is irreversible.
    """
    file = FileMetadata.query.get_or_404(id)
    
    if not file.deleted:
        flash("Only soft-deleted files (in trash) can be permanently deleted.", "warning")
        return redirect(url_for('main.admin_trash'))
    
    # Store file info for audit log before deleting
    original_name = file.original_name
    file_id = file.id
    
    # Remove the physical file from trash/
    trash_path = os.path.join(current_app.config['TRASH_FOLDER'], file.filename)
    if os.path.exists(trash_path):
        os.remove(trash_path)
    
    # Delete all associated view records, then delete the file metadata from DB
    FileView.query.filter_by(file_id=file.id).delete()
    db.session.delete(file)
    try:
        db.session.commit()
        log_action('FILE_PERMANENTLY_DELETED', 
                   f"Permanently deleted file: {original_name} (ID: {file_id}). "
                   f"Removed from disk and database.")
        flash(f"File '{original_name}' has been permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error permanently deleting file. Please try again.", "danger")
        print(f"Error permanently deleting file: {str(e)}")
        return redirect(url_for('main.admin_trash'))
    
    return redirect(url_for('main.admin_trash'))


# --- PROTECTED STATIC LOADER (Prevent unauthenticated hotlinking) ---

@bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    # Path traversal block
    filename = secure_filename(filename)
    if not filename or filename in {'.', '..'}:
        abort(400, "Bad Request: Invalid file pointer")
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        abort(404)
        
    # Standard check: does this filename belong to employee photo or metadata table?
    is_employee_photo = Employee.query.filter_by(photo=filename).first() is not None
    file_record = FileMetadata.query.filter_by(filename=filename).first()
    is_document = file_record is not None
    
    if not (is_employee_photo or is_document):
        log_action('UNAUTHORIZED_FILE_ACCESS', f"User tried to access unlisted upload file: {filename}")
        abort(403, "Access Denied: Unlisted resource request")
    
    # SECURITY: Block access to soft-deleted files (prevent direct URL access)
    if is_document and file_record.deleted:
        log_action('DELETED_FILE_ACCESS_ATTEMPT', 
                   f"User tried to access soft-deleted file via direct URL: {filename}")
        abort(404)  # Return 404 to not reveal file existence
        
    log_action('VIEW_FILE_CONTENT', f"Loaded raw content for: {filename}")
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


# --- ADVANCED SEARCH ROUTE ---

@bp.route('/search')
@login_required
def search():
    # Instantiate search form with GET query params
    form = SearchForm(request.args)
    
    # Query building – always exclude soft-deleted files
    query = FileMetadata.query.join(Employee).filter(FileMetadata.deleted == False)
    
    # Apply filters dynamically
    search_query = request.args.get('query', '').strip()
    if search_query:
        # Match file original name OR employee name
        query = query.filter(
            (FileMetadata.original_name.like(f"%{search_query}%")) |
            (Employee.full_name.like(f"%{search_query}%"))
        )
        
    file_type = request.args.get('file_type', '').strip()
    if file_type:
        if file_type == 'image':
            query = query.filter(FileMetadata.file_type.like('image/%'))
        elif file_type == 'pdf':
            query = query.filter(FileMetadata.file_type == 'application/pdf')
        elif file_type == 'doc':
            query = query.filter(
                (FileMetadata.file_type == 'application/msword') |
                (FileMetadata.file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            )
        elif file_type == 'xls':
            query = query.filter(
                (FileMetadata.file_type == 'application/vnd.ms-excel') |
                (FileMetadata.file_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            )
            
    tags = request.args.get('tags', '').strip()
    if tags:
        # Handle comma-separated tags filter (checks for sub-matches)
        tag_list = [t.strip() for t in tags.split(',')]
        for tag in tag_list:
            if tag:
                query = query.filter(FileMetadata.tags.like(f"%{tag}%"))
                
    start_date_str = request.args.get('start_date', '').strip()
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(FileMetadata.upload_date >= start_date)
        except ValueError:
            pass
            
    end_date_str = request.args.get('end_date', '').strip()
    if end_date_str:
        try:
            # Set to end of the day
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(FileMetadata.upload_date <= end_date)
        except ValueError:
            pass
            
    results = query.order_by(FileMetadata.upload_date.desc()).all()
    log_action('SEARCH_DOCUMENTS', f"Searched index query='{search_query}', type='{file_type}', tags='{tags}'")
    
    return render_template('search.html', form=form, results=results)


# --- SECURITY & COMPLIANCE LOGS (Admin Only) ---

@bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    log_action('VIEW_AUDIT_LOGS', "Accessed security audit log portal.")
    all_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('audit_logs.html', logs=all_logs)
