import frappe

@frappe.whitelist(allow_guest=True)
def mobile_login(username, password):
    login_manager = frappe.auth.LoginManager()

    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(username, password)

        user = frappe.get_doc("User", username)

        if not user.api_key:
            user.api_key = frappe.generate_hash(length=15)

        api_secret = frappe.generate_hash(length=15)
        user.api_secret = api_secret

        user.save(ignore_permissions=True)

        return {
            "api_key": user.api_key,
            "api_secret": api_secret,
            "user": username
        }

    except Exception:
        frappe.throw("Invalid credentials")
