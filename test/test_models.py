"""Offline unit tests for dsv_tracking.models parsing.

Fixture payloads mirror the real examples documented in
docs/dsv-tracking-api.md (captured from the live site). No network calls.
"""

from __future__ import annotations

import pydantic
import pytest

from dsv_tracking.models import ShipmentDetail, ShipmentSummary, Trip

SHIPMENTS_QUERY_RESPONSE = {
    "result": [
        {
            "id": "LandStt:SESOE620172194:CTTS:LAND",
            "stt": "SESOE620172194",
            "transportMode": "LAND",
            "percentageProgress": 100,
            "lastEventCode": "DLV",
            "fromLocation": "Norsborg",
            "toLocation": "Växjö",
            "startDate": "2026-05-15T00:00:00Z",
            "endDate": "2026-05-18T00:00:00Z",
            "consignment": None,
            "additionalReferenceValues": None,
            "isXpress": False,
            "swedenViewAvailable": True,
        }
    ],
    "warnings": [],
}

SHIPMENT_DETAIL_RESPONSE = {
    "sttNumber": "SESOE620172194",
    "references": {
        "shipper": ["57439 /"],
        "consignee": [],
        "waybillAndConsignementNumbers": ["3476236157"],
        "additionalReferences": [],
        "originalStt": None,
    },
    "goods": {
        "pieces": 1,
        "volume": {"value": 0.004, "unit": "CBM"},
        "weight": {"value": 0.8, "unit": "KGS"},
        "dimensions": [],
        "loadingMeters": {"value": 0.0, "unit": "MTR"},
    },
    "events": [
        {
            "code": "COL",
            "date": "2026-05-15T14:00:00+02:00",
            "location": {"name": "Norsborg", "code": "SOE", "countryCode": "SE"},
            "comment": "Collected",
        },
        {
            "code": "DLV",
            "date": "2026-05-18T10:57:31+02:00",
            "location": {"name": "Växjö", "code": "VXO", "countryCode": "SE"},
            "comment": "Delivered",
        },
    ],
    "product": "DSVparcel",
    "transportMode": "LAND",
    "deliveryDate": {"estimated": "2026-05-18T00:00:00Z", "agreed": None},
    "progressBar": {
        "steps": ["BOOKED", "TRANSPORTATION", "DISPATCHING_CENTER", "IN_DELIVERY", "DELIVERED"],
        "activeStep": "DELIVERED",
    },
    "location": {
        "collectFrom": {"countryCode": "SE", "country": "Sweden", "city": "Norsborg", "postCode": "14563"},
        "deliverTo": {"countryCode": "SE", "country": "Sweden", "city": "Växjö", "postCode": "35250"},
    },
}

TRIP_RESPONSE = {
    "start": {"name": None, "latitude": 59.22888181, "longitude": 17.840829818},
    "end": {"name": None, "latitude": 56.914394339, "longitude": 14.73500537},
    "trip": [
        {"lastEventCode": "COL", "lastEventDate": "2026-05-15T14:00:00+02:00", "latitude": 59.22888181, "longitude": 17.840829818},
        {"lastEventCode": "DLV", "lastEventDate": "2026-05-18T10:57:31+02:00", "latitude": 56.914394339, "longitude": 14.73500537},
    ],
    "isDelivered": True,
}


def test_shipment_summary_from_json():
    summary = ShipmentSummary.model_validate(SHIPMENTS_QUERY_RESPONSE["result"][0])
    assert summary.id == "LandStt:SESOE620172194:CTTS:LAND"
    assert summary.stt == "SESOE620172194"
    assert summary.transport_mode == "LAND"
    assert summary.percentage_progress == 100
    assert summary.last_event_code == "DLV"
    assert summary.from_location == "Norsborg"
    assert summary.to_location == "Växjö"


def test_shipment_detail_from_json():
    detail = ShipmentDetail.model_validate(SHIPMENT_DETAIL_RESPONSE)
    assert detail.stt_number == "SESOE620172194"
    assert detail.transport_mode == "LAND"
    assert detail.product == "DSVparcel"
    assert detail.active_step == "DELIVERED"
    assert detail.steps == ["BOOKED", "TRANSPORTATION", "DISPATCHING_CENTER", "IN_DELIVERY", "DELIVERED"]
    assert detail.pieces == 1
    assert detail.weight_value == 0.8
    assert detail.weight_unit == "KGS"
    assert detail.collect_from == "Norsborg, 14563, Sweden"
    assert detail.deliver_to == "Växjö, 35250, Sweden"
    assert detail.delivery_date_estimated == "2026-05-18T00:00:00Z"
    assert detail.waybill_numbers == ["3476236157"]

    assert len(detail.events) == 2
    first_event = detail.events[0]
    assert first_event.code == "COL"
    assert first_event.comment == "Collected"
    assert first_event.location_name == "Norsborg"
    assert first_event.location_country_code == "SE"


def test_trip_from_json():
    trip = Trip.model_validate(TRIP_RESPONSE)
    assert trip.is_delivered is True
    assert len(trip.points) == 2
    assert trip.points[0].last_event_code == "COL"
    assert trip.points[0].latitude == 59.22888181
    assert trip.points[1].last_event_code == "DLV"


def test_shipment_summary_missing_field_raises_validation_error():
    incomplete = dict(SHIPMENTS_QUERY_RESPONSE["result"][0])
    del incomplete["transportMode"]

    with pytest.raises(pydantic.ValidationError) as exc_info:
        ShipmentSummary.model_validate(incomplete)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("transportMode",) and error["type"] == "missing" for error in errors)
