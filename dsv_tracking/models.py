from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShipmentNotFound(Exception):
    def __init__(self, reference_number: str):
        super().__init__(f"No shipment found for reference {reference_number!r}")
        self.reference_number = reference_number


class ShipmentSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    stt: str
    transport_mode: str = Field(alias="transportMode")
    percentage_progress: int = Field(alias="percentageProgress")
    last_event_code: str = Field(alias="lastEventCode")
    from_location: str = Field(alias="fromLocation")
    to_location: str = Field(alias="toLocation")
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")


class TrackingEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    date: str
    comment: str | None = None
    location_name: str | None = None
    location_country_code: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_location(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        location = data.pop("location", None) or {}
        data.setdefault("location_name", location.get("name"))
        data.setdefault("location_country_code", location.get("countryCode"))
        return data


class ShipmentDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stt_number: str
    transport_mode: str
    product: str | None = None
    active_step: str | None = None
    steps: list[str] = Field(default_factory=list)
    events: list[TrackingEvent] = Field(default_factory=list)
    pieces: int | None = None
    weight_value: float | None = None
    weight_unit: str | None = None
    collect_from: str | None = None
    deliver_to: str | None = None
    delivery_date_estimated: str | None = None
    delivery_date_agreed: str | None = None
    waybill_numbers: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _flatten(cls, data):
        if not isinstance(data, dict):
            return data

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

        return {
            "stt_number": data.get("sttNumber"),
            "transport_mode": data.get("transportMode"),
            "product": data.get("product"),
            "active_step": progress_bar.get("activeStep"),
            "steps": progress_bar.get("steps", []),
            "events": data.get("events", []),
            "pieces": goods.get("pieces"),
            "weight_value": weight.get("value"),
            "weight_unit": weight.get("unit"),
            "collect_from": city_line(collect_from),
            "deliver_to": city_line(deliver_to),
            "delivery_date_estimated": delivery_date.get("estimated"),
            "delivery_date_agreed": delivery_date.get("agreed"),
            "waybill_numbers": references.get("waybillAndConsignementNumbers", []),
        }


class TripPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    last_event_code: str = Field(alias="lastEventCode")
    last_event_date: str = Field(alias="lastEventDate")
    latitude: float
    longitude: float


class Trip(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_delivered: bool = Field(default=False, alias="isDelivered")
    points: list[TripPoint] = Field(default_factory=list, alias="trip")
