from __future__ import annotations

from dataclasses import dataclass


class ShipmentNotFound(Exception):
    def __init__(self, reference_number: str):
        super().__init__(f"No shipment found for reference {reference_number!r}")
        self.reference_number = reference_number


@dataclass
class ShipmentSummary:
    id: str
    stt: str
    transport_mode: str
    percentage_progress: int
    last_event_code: str
    from_location: str
    to_location: str
    start_date: str | None
    end_date: str | None

    @classmethod
    def from_json(cls, data: dict) -> ShipmentSummary:
        return cls(
            id=data["id"],
            stt=data["stt"],
            transport_mode=data["transportMode"],
            percentage_progress=data["percentageProgress"],
            last_event_code=data["lastEventCode"],
            from_location=data["fromLocation"],
            to_location=data["toLocation"],
            start_date=data.get("startDate"),
            end_date=data.get("endDate"),
        )


@dataclass
class TrackingEvent:
    code: str
    date: str
    comment: str | None
    location_name: str | None
    location_country_code: str | None

    @classmethod
    def from_json(cls, data: dict) -> TrackingEvent:
        location = data.get("location") or {}
        return cls(
            code=data["code"],
            date=data["date"],
            comment=data.get("comment"),
            location_name=location.get("name"),
            location_country_code=location.get("countryCode"),
        )


@dataclass
class ShipmentDetail:
    stt_number: str
    transport_mode: str
    product: str | None
    active_step: str | None
    steps: list[str]
    events: list[TrackingEvent]
    pieces: int | None
    weight_value: float | None
    weight_unit: str | None
    collect_from: str | None
    deliver_to: str | None
    delivery_date_estimated: str | None
    delivery_date_agreed: str | None
    waybill_numbers: list[str]

    @classmethod
    def from_json(cls, data: dict) -> ShipmentDetail:
        goods = data.get("goods") or {}
        weight = goods.get("weight") or {}
        progress_bar = data.get("progressBar") or {}
        location = data.get("location") or {}
        collect_from = location.get("collectFrom") or {}
        deliver_to = location.get("deliverTo") or {}
        delivery_date = data.get("deliveryDate") or {}
        references = data.get("references") or {}

        def city_line(place: dict) -> str | None:
            if not place:
                return None
            parts = [place.get("city"), place.get("postCode"), place.get("country")]
            return ", ".join(p for p in parts if p)

        return cls(
            stt_number=data["sttNumber"],
            transport_mode=data["transportMode"],
            product=data.get("product"),
            active_step=progress_bar.get("activeStep"),
            steps=progress_bar.get("steps", []),
            events=[TrackingEvent.from_json(e) for e in data.get("events", [])],
            pieces=goods.get("pieces"),
            weight_value=weight.get("value"),
            weight_unit=weight.get("unit"),
            collect_from=city_line(collect_from),
            deliver_to=city_line(deliver_to),
            delivery_date_estimated=delivery_date.get("estimated"),
            delivery_date_agreed=delivery_date.get("agreed"),
            waybill_numbers=references.get("waybillAndConsignementNumbers", []),
        )


@dataclass
class TripPoint:
    last_event_code: str
    last_event_date: str
    latitude: float
    longitude: float

    @classmethod
    def from_json(cls, data: dict) -> TripPoint:
        return cls(
            last_event_code=data["lastEventCode"],
            last_event_date=data["lastEventDate"],
            latitude=data["latitude"],
            longitude=data["longitude"],
        )


@dataclass
class Trip:
    is_delivered: bool
    points: list[TripPoint]

    @classmethod
    def from_json(cls, data: dict) -> Trip:
        return cls(
            is_delivered=data.get("isDelivered", False),
            points=[TripPoint.from_json(p) for p in data.get("trip", [])],
        )
