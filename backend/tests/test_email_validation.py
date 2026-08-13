from app.utils.email_utils import validate_student_email


def test_valid_emails():
    valid = [
        "john.doe@vsit.edu.in",
        "rahul.sharma@vsit.edu.in",
        "priya.patel@vsit.edu.in",
    ]
    for e in valid:
        assert validate_student_email(e)


def test_invalid_emails():
    invalid = [
        "john@vsit.edu.in",
        "john.doe@gmail.com",
        "john.doe@vsit.com",
        "john.doe@vsit.edu",
        "john.doe@vsit.edu.in.in",
        "john.doe.extra@vsit.edu.in",
        "john doe@vsit.edu.in",
    ]
    for e in invalid:
        assert not validate_student_email(e)
