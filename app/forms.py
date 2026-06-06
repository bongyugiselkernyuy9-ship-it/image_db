from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models import User, Employee

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')

    def validate_password(self, password):
        if not password.data.isdigit():
            raise ValidationError('Password must contain only numbers.')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Role', choices=[('employee', 'Employee'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Register User')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose another one.')

    def validate_password(self, password):
        if not password.data.isdigit():
            raise ValidationError('Password must contain only numbers.')


class EmployeeForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=128)])
    employee_id = StringField('Employee ID (Unique)', validators=[DataRequired(), Length(max=64)])
    department = StringField('Department', validators=[DataRequired(), Length(max=64)])
    position = StringField('Position', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    hire_date = DateField('Hire Date', format='%Y-%m-%d', validators=[DataRequired()])
    photo = FileField('Profile Photo (Optional)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only (jpg, png, jpeg).')
    ])
    submit = SubmitField('Save Employee')

    def __init__(self, original_employee_id=None, *args, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)
        self.original_employee_id = original_employee_id

    def validate_employee_id(self, employee_id):
        if employee_id.data != self.original_employee_id:
            emp = Employee.query.filter_by(employee_id=employee_id.data).first()
            if emp:
                raise ValidationError('Employee ID is already in use by another record.')


class FileUploadForm(FlaskForm):
    file = FileField('File', validators=[
        FileRequired('Please select a file to upload.')
    ])
    employee_id = SelectField('Link to Employee', coerce=int, validators=[DataRequired()])
    tags = StringField('Tags (Comma separated)', validators=[Optional(), Length(max=256)])
    submit = SubmitField('Upload')


class SearchForm(FlaskForm):
    query = StringField('Search Query (Filename or Employee Name)', validators=[Optional()])
    file_type = SelectField('File Type', choices=[
        ('', 'All File Types'),
        ('image', 'Images (JPG, PNG)'),
        ('pdf', 'PDF Documents'),
        ('doc', 'Word Documents (DOC, DOCX)'),
        ('xls', 'Excel Spreadsheets (XLS, XLSX)')
    ], validators=[Optional()])
    tags = StringField('Tags', validators=[Optional()])
    start_date = DateField('Upload Date From', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('Upload Date To', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Search')
