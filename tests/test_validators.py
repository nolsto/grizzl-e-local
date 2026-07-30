import pytest

from grizzl_e_local.document.base import BaseDocument
from grizzl_e_local.document.validation import ValidationError
from grizzl_e_local.document.versions import CurrentRestraintValidator, HttpAuthValidator
from grizzl_e_local.document.validation import PasswordLengthValidator


class TestCurrentRestraintValidatorDirect:
    def _make_doc(self, current_set: int = 32, cur_design: int = 40):
        class Doc(BaseDocument):
            currentSet: int
            curDesign: int

        doc = Doc()
        doc["currentSet"] = current_set
        doc["curDesign"] = cur_design
        return doc

    def test_valid_within_design(self):
        doc = self._make_doc(32, 40)
        CurrentRestraintValidator()(doc)

    def test_exceeds_design_raises(self):
        doc = self._make_doc(50, 40)
        with pytest.raises(ValidationError, match="Device not designed to exceed"):
            CurrentRestraintValidator()(doc)

    def test_equal_to_design_is_ok(self):
        doc = self._make_doc(40, 40)
        CurrentRestraintValidator()(doc)


class TestHttpAuthValidatorDirect:
    def _make_doc(self):
        class Doc(BaseDocument):
            httpUsername: str
            httpPassword: str
        return Doc()

    def test_password_without_username_raises(self):
        doc = self._make_doc()
        doc["httpPassword"] = "secret123"
        with pytest.raises(ValidationError, match="httpUsername required"):
            HttpAuthValidator()(doc)

    def test_username_with_empty_password_ok(self):
        doc = self._make_doc()
        doc["httpUsername"] = "admin"
        HttpAuthValidator()(doc)  # no error — password is empty

    def test_both_set_ok(self):
        doc = self._make_doc()
        doc["httpUsername"] = "admin"
        doc["httpPassword"] = "secret123"
        HttpAuthValidator()(doc)  # no error — both present


class TestPasswordLengthValidatorDirect:
    def _make_doc(self):
        class Doc(BaseDocument):
            password: str
        return Doc()

    def test_short_password_raises(self):
        doc = self._make_doc()
        doc["password"] = "short"
        with pytest.raises(ValidationError, match="must be at least 8 characters"):
            PasswordLengthValidator("password")(doc)

    def test_empty_password_ok(self):
        doc = self._make_doc()
        doc["password"] = ""
        PasswordLengthValidator("password")(doc)  # no error — empty is allowed

    def test_long_enough_password_ok(self):
        doc = self._make_doc()
        doc["password"] = "longenough"
        PasswordLengthValidator("password")(doc)  # no error
