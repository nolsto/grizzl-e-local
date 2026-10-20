from typing import Annotated

import pytest

from grizzl_e_local.constants import Endpoint
from grizzl_e_local.document.base import BaseDocument
from grizzl_e_local.document.validation import ValidationError


class _MinutesDoc(BaseDocument):
    tarifAStart: int  # minutes from midnight, interpreted by the device layer
    tarifAStop: int


class _FlagsDoc(BaseDocument):
    ground: int
    enabled: int


class _MixedDoc(BaseDocument):
    name: str
    tarifAStart: int
    ground: int
    totalEnergy: float

    validators = []


class TestRawStorage:
    def test_values_stored_as_received(self):
        doc = _MinutesDoc(tarifAStart=960, tarifAStop=1200)
        assert doc.tarifAStart == 960
        assert doc.tarifAStop == 1200

    def test_flags_store_zero_one_ints(self):
        doc = _FlagsDoc(ground=1, enabled=0)
        assert doc.ground == 1
        assert doc.enabled == 0

    def test_strings_stored_as_is(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=1, totalEnergy=3.5)
        assert doc.name == "test"


class TestValidation:
    def test_string_for_int_field_raises(self):
        with pytest.raises(ValueError, match="tarifAStart"):
            _MinutesDoc(tarifAStart="not_a_number", tarifAStop=0)

    def test_int_for_str_field_raises(self):
        with pytest.raises(ValueError, match="name"):
            _MixedDoc(name=1, tarifAStart=0, ground=0, totalEnergy=0.0)

    def test_classmethod_validate(self):
        _MinutesDoc.validate({"tarifAStart": 960})

        with pytest.raises(ValueError, match="tarifAStop"):
            _MinutesDoc.validate({"tarifAStop": "bad"})

    def test_validate_ignores_unknown_fields(self):
        # Firmware may add fields after a device update; ingest must not crash.
        _MinutesDoc.validate({"unknownField": 1})


class TestFloatTolerance:
    def test_int_value_accepted_for_float_field(self):
        # JSON numbers without a fractional part parse as int even on float fields.
        doc = BaseDocument.__subclasses__() and None or None
        class EnergyDoc(BaseDocument):
            totalEnergy: float

        doc = EnergyDoc(totalEnergy=5)
        assert doc.totalEnergy == 5


class TestEndpointDetection:
    def _make_doc(self):
        class Doc(BaseDocument):
            name: str
            secret: str = ""

        return Doc

    def test_default_endpoint_is_set(self):
        assert self._make_doc().get_endpoint("name") is Endpoint.SET

    def test_config_ap_endpoint(self):
        class Doc(BaseDocument):
            secret: Annotated[str, Endpoint.CONFIG_AP]

        assert Doc.get_endpoint("secret").name == "CONFIG_AP"


class TestValidators:
    def _validator(self):
        class Validator:
            fields = {"value"}

            def __call__(self, doc):
                if getattr(doc, "value", 0) > 100:
                    raise ValidationError("too high")

        return Validator()

    def test_custom_validator_fails(self):
        class Doc(BaseDocument):
            value: int
            validators = [self._validator()]

        doc = Doc(value=200)
        with pytest.raises(ValidationError, match="too high"):
            doc.run_validators()
        assert not doc.is_valid()

    def test_all_validators_pass_with_good_data(self):
        class Doc(BaseDocument):
            value: int
            validators = [self._validator()]

        doc = Doc(value=50)
        doc.run_validators()
        assert doc.is_valid()


class TestDiff:
    def test_diff_returns_changed_fields(self):
        doc1 = _MixedDoc(name="a", tarifAStart=960, ground=1, totalEnergy=3.5)
        doc2 = _MixedDoc(name="b", tarifAStart=960, ground=1, totalEnergy=3.5)
        assert doc1.diff(doc2) == {"name"}

    def test_diff_empty_when_identical(self):
        doc1 = _MixedDoc(name="a", tarifAStart=960, ground=1, totalEnergy=3.5)
        doc2 = _MixedDoc(name="a", tarifAStart=960, ground=1, totalEnergy=3.5)
        assert doc1.diff(doc2) == set()


class TestMutation:
    def test_setitem_stores_raw_value(self):
        doc = _MinutesDoc(tarifAStart=0, tarifAStop=0)
        doc.tarifAStart = 1080
        assert doc.tarifAStart == 1080

    def test_setitem_rejects_wrong_type(self):
        doc = _MinutesDoc(tarifAStart=0, tarifAStop=0)
        with pytest.raises(ValueError, match="tarifAStart"):
            doc.tarifAStart = "bad"

    def test_dot_access_delegates_to_dict(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=1, totalEnergy=3.5)
        assert doc.name == "test"
        with pytest.raises(AttributeError):
            _ = doc.nonexistent_field

    def test_unknown_field_raises_keyerror(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=1, totalEnergy=3.5)
        with pytest.raises(KeyError, match="unknown field"):
            doc.unknownField = "fail"
