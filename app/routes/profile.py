"""User profile — change password, family member display names, and 2FA."""
import base64
import io
import pyotp
import qrcode
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

_TOTP_SETUP_KEY = "_totp_setup_secret"


@profile_bp.route("/")
@login_required
def profile():
    return render_template("profile/profile.html")


@profile_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not check_password_hash(current_user.password_hash, current_pw):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile.profile"))

    if len(new_pw) < 8:
        flash("New password must be at least 8 characters.", "danger")
        return redirect(url_for("profile.profile"))

    if new_pw != confirm_pw:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("profile.profile"))

    current_user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    flash("Password updated successfully.", "success")
    return redirect(url_for("profile.profile"))


@profile_bp.route("/family-members", methods=["POST"])
@login_required
def update_family_members():
    person1 = request.form.get("person1_name", "").strip()
    person2 = request.form.get("person2_name", "").strip()
    current_user.person1_name = person1 if person1 else None
    current_user.person2_name = person2 if person2 else None
    db.session.commit()
    flash("Family member names updated.", "success")
    return redirect(url_for("profile.profile"))


@profile_bp.route("/totp/setup")
@login_required
def totp_setup():
    """Show the 2FA setup page with a QR code to scan."""
    secret = pyotp.random_base32()
    session[_TOTP_SETUP_KEY] = secret
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.username, issuer_name="Tax Estimator"
    )
    qr_data_uri = _build_qr_data_uri(provisioning_uri)
    return render_template(
        "profile/totp_setup.html",
        qr_data_uri=qr_data_uri,
        totp_secret=secret,
    )


@profile_bp.route("/totp/enable", methods=["POST"])
@login_required
def totp_enable():
    """Verify the code from the authenticator app and enable 2FA."""
    secret = session.get(_TOTP_SETUP_KEY)
    if not secret:
        flash("Setup session expired. Please start over.", "danger")
        return redirect(url_for("profile.totp_setup"))
    code = request.form.get("totp_code", "").strip()
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        flash("Invalid verification code. Please scan the QR code again and try once more.", "danger")
        return redirect(url_for("profile.totp_setup"))
    current_user.totp_secret = secret
    current_user.totp_enabled = True
    db.session.commit()
    session.pop(_TOTP_SETUP_KEY, None)
    flash("Two-factor authentication has been enabled.", "success")
    return redirect(url_for("profile.profile"))


@profile_bp.route("/totp/disable", methods=["POST"])
@login_required
def totp_disable():
    """Disable 2FA after verifying the current password."""
    password = request.form.get("password", "")
    if not check_password_hash(current_user.password_hash, password):
        flash("Incorrect password. Two-factor authentication was not disabled.", "danger")
        return redirect(url_for("profile.profile"))
    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.session.commit()
    flash("Two-factor authentication has been disabled.", "success")
    return redirect(url_for("profile.profile"))


def _build_qr_data_uri(provisioning_uri: str) -> str:
    """Return a base64-encoded PNG data URI for the given provisioning URI."""
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
