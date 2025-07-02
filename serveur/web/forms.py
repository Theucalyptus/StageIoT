from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, Optional

# formulaire de login utilisateur
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=255)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# formulaire d'enregistrement d'un utilisateur
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=255)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=60)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# formulaire d'enregistrement d'un appareil
class DeviceAssociationForm(FlaskForm):
    deviceid = StringField('Device ID', validators=[DataRequired(), Length(min=1, max=32)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=60)])
    submit = SubmitField('Associate')

# formulaire d'enregistrement d'un appareil
class DeviceRegistrationForm(FlaskForm):
    deviceid = StringField('Device ID', validators=[DataRequired(), Length(min=1, max=32)])
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=60)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    lora_dev_eui = StringField('LoRa Device ID (dev eui)', validators=[Optional(), Length(min=16, max=16)])
    submit2 = SubmitField('Register')

# formulaire d'edition d'un appareil
class DeviceEditForm(FlaskForm):
    name = StringField('Name *', validators=[DataRequired(), Length(min=2, max=20)])
    description = TextAreaField('Description', validators=[Length(min=0, max=500)])
    lora = StringField('LoRa EUI', validators=[Optional(), Length(min=16, max=16)])
    password = PasswordField('Curent Password *', validators=[DataRequired(), Length(min=6, max=60)])
    new_password = PasswordField('new Password', validators=[Length(min=6, max=60)], default="")
    confirm_password = PasswordField('Confirm new Password', validators=[EqualTo('new Password')], default="")
    submit = SubmitField('Edit Device')