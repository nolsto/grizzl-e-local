from datetime import time, timezone, tzinfo
from decimal import Decimal
from typing import Annotated

import pytest

from grizzl_e_local.constants import Endpoint
from grizzl_e_local.document.base import BaseDocument
from grizzl_e_local.document.validation import ValidationError


class _TimeDoc(BaseDocument):
    tarifAStart: time
    tarifAStop: time


class _BoolDoc(BaseDocument):
    ground: bool
    enabled: bool


class _DecimalDoc(BaseDocument):
    rate: Decimal
    amount: Decimal


class _TzDoc(BaseDocument):
    timeZone: tzinfo


class _MixedDoc(BaseDocument):
    name: str
    tarifAStart: time
    ground: bool
    tarifValue: Decimal
    timeZone: tzinfo

    validators = []



class TestNormalization:
    def test_time_field_normalized(self):
        doc = _TimeDoc(tarifAStart=960, tarifAStop=1200)
        assert doc.tarifAStart == time(16, 0)
        assert doc.tarifAStop == time(20, 0)

    def test_time_field_passes_through_when_already_correct(self):
        doc = _TimeDoc(tarifAStart=time(8, 30), tarifAStop=1200)
        assert doc.tarifAStart == time(8, 30)

    def test_bool_field_normalized(self):
        doc = _BoolDoc(ground=1, enabled=0)
        assert doc.ground is True
        assert doc.enabled is False

    def test_decimal_fields_normalized(self):
        doc = _DecimalDoc(rate=36, amount=3)
        assert doc.rate == Decimal("0.36")
        assert doc.amount == Decimal("0.03")

    def test_tzinfo_field_normalized(self):
        doc = _TzDoc(timeZone=-5)
        assert isinstance(doc.timeZone, timezone)
        assert doc.timeZone.utcoffset(None).total_seconds() == -5 * 3600



class TestValidation:
    def test_invalid_int_for_time_raises(self):
        with pytest.raises(ValueError, match="tarifAStart"):
            _TimeDoc(tarifAStart="not_a_number", tarifAStop=0)

    def test_invalid_type_for_bool_raises(self):
        with pytest.raises(ValueError, match="ground"):
            _BoolDoc(ground="not_an_int", enabled=1)

    def test_invalid_int_for_decimal_raises(self):
        with pytest.raises(ValueError, match="rate"):
            _DecimalDoc(rate="bad", amount=0)

    def test_classmethod_validate(self):
        _TimeDoc.validate({"tarifAStart": 960})

        with pytest.raises(ValueError, match="tarifAStop"):
            _TimeDoc.validate({"tarifAStop": "bad"})



class TestSerialization:
    def test_serialize_converts_back_to_device_format(self):
        doc = _MixedDoc(
            name="test",
            tarifAStart=time(16, 0),
            ground=1,
            tarifValue=36,
            timeZone=-5,
        )
        serialized = doc.serialize()
        assert serialized["tarifAStart"] == 960
        assert serialized["ground"] == 1
        assert isinstance(serialized["tarifValue"], int)

    def test_serialize_omits_unknown_fields(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=0, tarifValue=0, timeZone=0)
        serialized = doc.serialize()
        assert "unknownField" not in serialized



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
    def test_custom_validator_fails(self):
        class Validator:
            fields = {"value"}

            def __call__(self, doc):
                if getattr(doc, "value", 0) > 100:
                    raise ValidationError("too high")

        class Doc(BaseDocument):
            value: int
            validators = [Validator()]

        doc = Doc(value=200)
        with pytest.raises(ValidationError, match="too high"):
            doc.run_validators()

    def test_all_validators_pass_with_good_data(self):
        class Validator:
            fields = {"value"}

            def __call__(self, doc):
                if getattr(doc, "value", 0) > 100:
                    raise ValidationError("too high")

        class Doc(BaseDocument):
            value: int
            validators = [Validator()]

        doc = Doc(value=50)
        doc.run_validators()


class TestDiff:
    def test_diff_returns_changed_fields(self):
        doc1 = _MixedDoc(name="a", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        doc2 = _MixedDoc(name="b", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        assert doc1.diff(doc2) == {"name"}

    def test_diff_empty_when_identical(self):
        doc1 = _MixedDoc(name="a", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        doc2 = _MixedDoc(name="a", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        assert doc1.diff(doc2) == set()



class TestMutation:
    def test_setitem_normalizes(self):
        doc = _TimeDoc(tarifAStart=0, tarifAStop=0)
        doc.tarifAStart = 1080
        assert doc.tarifAStart == time(18, 0)

    def test_setitem_validates_before_normalizing(self):
        doc = _TimeDoc(tarifAStart=0, tarifAStop=0)
        with pytest.raises(ValueError, match="tarifAStart"):
            doc.tarifAStart = "bad"

    def test_dot_access_delegates_to_dict(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        assert doc.name == "test"
        with pytest.raises(AttributeError):
            _ = doc.nonexistent_field

    def test_unknown_field_raises_keyerror(self):
        doc = _MixedDoc(name="test", tarifAStart=960, ground=1, tarifValue=36, timeZone=0)
        with pytest.raises(KeyError, match="unknown field"):
            doc.unknownField = "fail"


class TestLazyEvaluation:
    def test_callable_stores_resolver(self):
        class Doc(BaseDocument):
            value: int

        def make_value():
            return 42

        doc = Doc()
        doc.value = make_value
        assert callable(doc.data["value"])
        assert doc.serialize() == {"value": 42}

    def test_serialization_calls_callable(self):
        class Doc(BaseDocument):
            value: int

        def make_value():
            return 42

        doc = Doc()
        doc.value = make_value
        assert doc.serialize() == {"value": 42}

    def test_serialization_resolves_multiple_times(self):
        class Doc(BaseDocument):
            value: int

        counter = [0]
        def make_value():
            counter[0] += 1
            return counter[0]

        doc = Doc()
        doc.value = make_value
        assert doc.serialize() == {"value": 1}
        assert doc.serialize() == {"value": 2}

    def test_lazy_callable_raises_normalize_error(self):
        class Doc(BaseDocument):
            value: int

        def bad_value():
            return "not_an_int"

        doc = Doc()
        doc.value = bad_value
        with pytest.raises(ValueError, match="value"):
            doc.serialize()

    def test_diff_compares_raw_callables(self):
        class Doc(BaseDocument):
            value: int

        doc1 = Doc()
        doc2 = Doc()
        doc1.value = lambda: 1
        doc2.value = lambda: 2
        # Different callable objects are structurally different
        assert doc1.diff(doc2) == {"value"}
