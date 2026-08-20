import frappe
from frappe.utils.password import set_encrypted_password


@frappe.whitelist(allow_guest=True)
def mobile_login(username, password):
    try:
        # Authenticate user
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(username, password)

        user = frappe.get_doc("User", username)

        # Generate API key if the user doesn't already have one
        if not user.api_key:
            user.api_key = frappe.generate_hash(length=15)
            user.save(ignore_permissions=True)

        # Generate a new API secret
        api_secret = frappe.generate_hash(length=15)

        # Store the API secret using Frappe's encrypted password mechanism
        set_encrypted_password(
            "User",
            username,
            api_secret,
            "api_secret"
        )

        frappe.db.commit()

        # Get user's roles
        try:
            user_roles = frappe.get_roles(username)
        except Exception:
            user_roles = []

        # Get only custom roles
        custom_roles = (
            frappe.get_all(
                "Role",
                filters={
                    "name": ["in", user_roles],
                    "is_custom": 1,
                },
                pluck="name",
            )
            if user_roles
            else []
        )

        return {
            "success": True,
            "message": "Login successful",
            "user_details": {
                "user_id": username,
                "user_name": user.full_name,
                "status": "active" if user.enabled else "inactive",
                "roles": custom_roles,
            },
            "user_creds": {
                "api_key": user.api_key,
                "api_secret": api_secret,
            },
        }

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Mobile Login Error"
        )
        frappe.throw("Invalid credentials")