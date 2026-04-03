"""User profile — change password and family member display names."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


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
