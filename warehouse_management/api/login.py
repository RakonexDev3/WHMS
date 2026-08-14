import frappe

@frappe.whitelist(allow_guest=True)
def mobile_login(username, password):

    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(username, password)

        user = frappe.get_doc("User", username)

        if not user.api_key:
            user.api_key = frappe.generate_hash(length=15)

        api_secret = frappe.generate_hash(length=15)
        user.api_secret = api_secret

        user.save(ignore_permissions=True)

        # gather user's roles and filter only custom roles
        try:
            user_roles = frappe.get_roles(username)
        except Exception:
            user_roles = []

        custom_roles = (
            frappe.get_all(
                "Role",
                filters={"name": ["in", user_roles], "is_custom": 1},
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
                "status": "active" if user.enabled == 1 else "inactive",
                "roles": custom_roles,
            },
            "user_creds": {"api_key": user.api_key, "api_secret": api_secret},
        }

    except Exception:
        frappe.throw("Invalid credentials")
