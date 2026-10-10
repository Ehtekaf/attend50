import math
from functools import wraps
from flask import redirect, render_template, session


def apology(message, code=400):
    """Render message as an apology to user."""
    return render_template("apology.html", top=code, bottom=message), code


def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def calculate_stats(attended, held, target_percentage=75.0):
    """
    Calculates percentage and attendance margins.
    Returns a dictionary of metrics for the UI.
    """
    target_ratio = target_percentage / 100.0

    if held == 0:
        return {
            "held": 0,
            "attended": 0,
            "absent": 0,
            "percentage": 100.0,
            "formatted_percentage": "100.0%",
            "status": "safe",
            "margin_type": "safe",
            "margin_count": 0,
            "message": "No classes conducted yet."
        }

    percentage = round((attended / held) * 100, 2)
    absent = held - attended

    if percentage >= target_percentage:
        # Number of classes that can be safely missed
        if target_ratio == 0:
            bunk_count = 0
        else:
            bunk_count = math.floor((attended / target_ratio) - held)
            bunk_count = max(0, bunk_count)

        return {
            "held": held,
            "attended": attended,
            "absent": absent,
            "percentage": percentage,
            "formatted_percentage": f"{percentage:.1f}%",
            "status": "safe",
            "margin_type": "bunk",
            "margin_count": bunk_count,
            "message": f"You can safely skip {bunk_count} class{'es' if bunk_count != 1 else ''}."
        }
    else:
        # Number of consecutive classes needed to recover
        if target_ratio >= 1.0:
            # If target is 100% and you missed a class, you can never mathematically reach 100%
            recover_count = -1
            msg = "100% target can no longer be reached."
        else:
            numerator = (target_ratio * held) - attended
            denominator = 1.0 - target_ratio
            recover_count = math.ceil(numerator / denominator)
            recover_count = max(1, recover_count)
            msg = f"Must attend next {recover_count} consecutive class{'es' if recover_count != 1 else ''}."

        return {
            "held": held,
            "attended": attended,
            "absent": absent,
            "percentage": percentage,
            "formatted_percentage": f"{percentage:.1f}%",
            "status": "danger",
            "margin_type": "recover",
            "margin_count": recover_count,
            "message": msg
        }
