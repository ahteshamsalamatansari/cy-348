#!/usr/bin/env python3
"""
Relay On Demand - Direct HTTP API Client

Calls the Relay REST API directly instead of using Playwright browser automation.
This is faster, more reliable, and simpler than browser-based automation.

API Base: https://ar3lay0pndm4ndi.relayondemand.com/relayapi/api/

Usage:
    from relay_api import RelayAPI
    api = RelayAPI()
    api.login("user@example.com", "password")
    api.place_order({...})
"""

import requests
import json
import os
from typing import Dict, Any, Optional, List


class RelayAPI:
    """Direct HTTP client for the Relay On Demand carrier API."""

    BASE_URL = "https://ar3lay0pndm4ndi.relayondemand.com/relayapi/api"

    def __init__(self):
        self.auth_token: Optional[str] = None
        self.carrier_name: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # Cache for reference data
        self._task_types: Optional[List[Dict]] = None
        self._trailer_types: Optional[List[Dict]] = None
        self._endorsement_types: Optional[List[Dict]] = None
        self._settings: Optional[Dict] = None

    @property
    def is_authenticated(self) -> bool:
        return self.auth_token is not None

    def _url(self, endpoint: str) -> str:
        return f"{self.BASE_URL}/{endpoint}"

    def _auth_headers(self) -> Dict[str, str]:
        if not self.auth_token:
            raise RuntimeError("Not authenticated. Call login() first.")
        return {"AuthToken": f"Bearer {self.auth_token}"}

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        resp = self.session.get(
            self._url(endpoint),
            headers=self._auth_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: Any = None) -> Dict:
        headers = self._auth_headers() if self.auth_token else {}
        resp = self.session.post(
            self._url(endpoint),
            headers=headers,
            json=data,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- Authentication ----

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> Dict:
        """
        Authenticate with the Relay API.
        Falls back to env vars CARRIER_USERNAME / CARRIER_PASSWORD.
        """
        email = email or os.getenv("CARRIER_USERNAME", "apitest@test.com")
        password = password or os.getenv("CARRIER_PASSWORD", "test123")

        resp = self.session.post(
            self._url("User/CarrierLogin"),
            json={"Email": email, "Password": password},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("Status"):
            self.auth_token = result["Data"]["AuthToken"]
            self.carrier_name = result["Data"].get("CarrierName", "")
            return {
                "success": True,
                "carrier_name": self.carrier_name,
                "auth_token": self.auth_token,
                "first_name": result["Data"].get("FirstName", ""),
                "is_demo": result["Data"].get("DemoAccount", False),
            }
        return {
            "success": False,
            "error": result.get("Message", "Login failed"),
        }

    def validate_token(self) -> bool:
        """Check if the current auth token is still valid."""
        if not self.auth_token:
            return False
        try:
            result = self._post("User/ValidateToken", {"AuthToken": self.auth_token})
            return result.get("Status", False)
        except Exception:
            return False

    # ---- Reference Data ----

    def get_task_types(self, force_refresh: bool = False) -> List[Dict]:
        """Get task types (pickup, dropoff, etc.) - needed for order placement."""
        if self._task_types and not force_refresh:
            return self._task_types
        result = self._get("Setting/GetTask")
        self._task_types = result.get("Data", result) if isinstance(result, dict) else result
        return self._task_types

    def get_trailer_types(self, force_refresh: bool = False) -> List[Dict]:
        """Get trailer types - needed for order placement."""
        if self._trailer_types and not force_refresh:
            return self._trailer_types
        result = self._get("PlaceOrder/TrailerTypes")
        self._trailer_types = result.get("Data", result) if isinstance(result, dict) else result
        return self._trailer_types

    def get_endorsement_types(self, force_refresh: bool = False) -> List[Dict]:
        """Get endorsement types (HAZMAT, Tanker, etc.)."""
        if self._endorsement_types and not force_refresh:
            return self._endorsement_types
        result = self._get("PlaceOrder/EndorsementTypes")
        self._endorsement_types = result.get("Data", result) if isinstance(result, dict) else result
        return self._endorsement_types

    def get_settings(self, force_refresh: bool = False) -> Dict:
        """Get app settings."""
        if self._settings and not force_refresh:
            return self._settings
        self._settings = self._get("Setting/GetSettings")
        return self._settings

    def get_states(self) -> List[Dict]:
        """Get US states list."""
        return self._get("Common/GetStates")

    def check_place_order_allowed(self) -> Dict:
        """Check if carrier is allowed to place orders."""
        try:
            return self._get("PlaceOrder/CheckPlaceOrderAllowed")
        except requests.exceptions.HTTPError:
            # Some versions of the API require POST
            return self._post("PlaceOrder/CheckPlaceOrderAllowed", {})

    # ---- Order Placement ----

    def get_estimated_distance(self, order_data: Dict) -> Dict:
        """
        Calculate estimated distance, cost, and time for an order.
        Returns: { Status, Data: { Cost, TimeInMinutes, DistanceInMiles } }
        """
        return self._post("PlaceOrder/TotalEstimatedDistance", order_data)

    def place_order(self, order_data: Dict) -> Dict:
        """
        Submit a new order via POST PlaceOrder/NewOrder.
        This is the primary order creation endpoint used by all form types.

        Required fields vary by form type but generally include:
        - StartAddress, StartAddressLat, StartAddressLong
        - DestinationAddress, DestinationAddressLat, DestinationAddressLong
        - TrailerTypeID, WhenYouWantDriver, DriverPayType, DriverBookDurations
        - StartAddressTaskID, EndAddressTaskID
        - IsRequestFromWeb: True
        """
        # Ensure web flag is set
        order_data.setdefault("IsRequestFromWeb", True)
        order_data.setdefault("IsOrderCreatedFromNewFlow", True)
        order_data.setdefault("CarrierName", self.carrier_name or "")
        order_data.setdefault("OrderAssign", "Find")
        order_data.setdefault("NetworkSelection", True)

        # RecurringDateTime must have at least one entry or the Relay API
        # throws "Index was out of range"
        if not order_data.get("RecurringDateTime"):
            order_data["RecurringDateTime"] = [{
                "DateTime": order_data.get("ScheduleTime", ""),
                "ScheduleTime": order_data.get("ScheduleTime", ""),
                "WhenWantDriver": order_data.get("WhenWantDriver", "notsure"),
                "WhenYouWantDriver": order_data.get("WhenYouWantDriver", "2"),
                "IsNotSureAboutDateTime": order_data.get("IsNotSureAboutDateTime", True),
                "DriverBookDurations": order_data.get("DriverBookDurations", "2"),
                "DriverPayType": order_data.get("DriverPayType", "0"),
                "OrderAssign": order_data.get("OrderAssign", "Find"),
                "NetworkSelection": order_data.get("NetworkSelection", True),
                "FlatAmount": order_data.get("FlatAmount", ""),
                "HourlyFlatAmount": order_data.get("HourlyFlatAmount", ""),
                "PerLoadAmount": order_data.get("PerLoadAmount", ""),
                "TotalLoads": order_data.get("TotalLoads", ""),
                "PerWeekAmount": order_data.get("PerWeekAmount", ""),
                "PerMileAmount": order_data.get("PerMileAmount", ""),
                "EstimatedTotalMiles": order_data.get("EstimatedTotalMiles", ""),
                "PreferredRelayDriverId": order_data.get("PreferredRelayDriverId", ""),
                "EstimatedPrice": order_data.get("EstimatedPrice", ""),
                "OrderRateId": order_data.get("OrderRateId", ""),
                "CustomizeRateFee": order_data.get("CustomizeRateFee", ""),
                "OrderLatestDate": order_data.get("OrderLatestDate", ""),
            }]

        return self._post("PlaceOrder/NewOrder", order_data)

    def build_order_data(
        self,
        start_address: str,
        destination_address: str,
        when_want_driver: str = "2",       # 0=exact, 1=timeframe, 2=notsure
        driver_pay_type: str = "0",         # 0=flat, 1=hourly, 2=weekly, 3=perload, 4=permile
        driver_book_duration: str = "2",    # hours
        flat_amount: str = "",
        hourly_amount: str = "",
        per_load_amount: str = "",
        per_mile_amount: str = "",
        per_week_amount: str = "",
        total_loads: str = "",
        estimated_total_miles: str = "",
        trailer_type_id: str = "",
        truck_unit_number: str = "",
        trailer_number: str = "",
        special_notes: str = "",
        internal_notes: str = "",
        endorsement_types: Optional[List[int]] = None,
        additional_stops: Optional[List[Dict]] = None,
        schedule_time: str = "",
        is_one_way: bool = True,
        from_smart_wizard: bool = False,
        order_assign: str = "Find",
        preferred_driver_id: str = "",
        # Classic entry fields
        carrier_driver_id: str = "",
        carrier_driver_name: str = "",
        schedule_date: str = "",
        # Address geocoding (lat/lng) - caller should provide if available
        start_lat: str = "",
        start_lng: str = "",
        start_city: str = "",
        start_state: str = "",
        dest_lat: str = "",
        dest_lng: str = "",
        dest_city: str = "",
        dest_state: str = "",
        start_task_id: str = "",
        start_task_hour: str = "",
        end_task_id: str = "",
        end_task_hour: str = "",
    ) -> Dict:
        """
        Build a complete order data payload from user-friendly parameters.
        Handles mapping to the raw API field names.
        """
        data = {
            "OrderID": "",
            "CarrierName": self.carrier_name or "",
            "StartAddress": start_address,
            "StartAddressLat": start_lat,
            "StartAddressLong": start_lng,
            "StartAddressCity": start_city,
            "StartAddressStateCode": start_state,
            "StartAddressTaskID": start_task_id,
            "StartAddressTaskHour": start_task_hour,
            "DestinationAddress": destination_address,
            "DestinationAddressLat": dest_lat,
            "DestinationAddressLong": dest_lng,
            "DestinationAddressCity": dest_city,
            "DestinationAddressStateCode": dest_state,
            "EndAddressTaskID": end_task_id,
            "EndAddressTaskHour": end_task_hour,
            "IsOneWay": is_one_way,
            "IsTruckOrdered": False,
            "IsMultipleStops": bool(additional_stops),
            "TrailerTypeID": trailer_type_id,
            "TruckUnitNumber": truck_unit_number,
            "TrailerNumber": trailer_number,
            "SpecialNotes": special_notes,
            "InternalNotes": internal_notes,
            "IsRequestFromWeb": True,
            "LeaseAgreement": "",
            "IsOrderEditable": True,
            "OrderNumber": "",
            "ChangedParamter": "",
            "RelayDriverID": "",
            "IsFromReviewOrder": False,
            "AdditionalStops": additional_stops or [],
            "EndorsementTypes": endorsement_types or [],
            "NetworkSelection": True if order_assign == "Find" else False,
            "OrderLatestDate": "",
            "EstimatedPrice": "",
            "OrderRateId": "",
            "CustomizeRateFee": "",
            "IsNotSureAboutDateTime": when_want_driver == "2",
            "ScheduleTime": schedule_time,
            "WhenYouWantDriver": when_want_driver,
            "DriverBookDurations": driver_book_duration,
            "DriverPayType": driver_pay_type,
            "FlatAmount": flat_amount,
            "HourlyFlatAmount": hourly_amount,
            "PerLoadAmount": per_load_amount,
            "TotalLoads": total_loads,
            "PerWeekAmount": per_week_amount,
            "PerMileAmount": per_mile_amount,
            "EstimatedTotalMiles": estimated_total_miles,
            "OrderAssign": order_assign,
            "PreferredRelayDriverId": preferred_driver_id,
            "IsOrderCreatedFromNewFlow": True,
            "FromSmartWizard": from_smart_wizard,
            "WhenWantDriver": (
                "exactdatetime" if when_want_driver == "0"
                else "timeframe" if when_want_driver == "1"
                else "notsure"
            ),
        }

        # RecurringDateTime MUST have at least one entry — the Relay API
        # throws "Index was out of range" if this array is empty.
        when_want_str = data["WhenWantDriver"]
        recurring_entry = {
            "DateTime": schedule_time,
            "ScheduleTime": schedule_time,
            "WhenWantDriver": when_want_str,
            "WhenYouWantDriver": when_want_driver,
            "IsNotSureAboutDateTime": when_want_driver == "2",
            "DriverBookDurations": driver_book_duration,
            "DriverPayType": driver_pay_type,
            "OrderAssign": order_assign,
            "NetworkSelection": True if order_assign == "Find" else False,
            "FlatAmount": flat_amount,
            "HourlyFlatAmount": hourly_amount,
            "PerLoadAmount": per_load_amount,
            "TotalLoads": total_loads,
            "PerWeekAmount": per_week_amount,
            "PerMileAmount": per_mile_amount,
            "EstimatedTotalMiles": estimated_total_miles,
            "PreferredRelayDriverId": preferred_driver_id,
            "EstimatedPrice": "",
            "OrderRateId": "",
            "CustomizeRateFee": "",
            "OrderLatestDate": "",
        }
        data["RecurringDateTime"] = [recurring_entry]

        # Classic entry fields (own fleet driver)
        if carrier_driver_id:
            data["CarrierDriverID"] = carrier_driver_id
            data["CarrierDriverName"] = carrier_driver_name
            # ScheduleDate is required for classic entry; default to today if empty
            if not schedule_date.strip():
                from datetime import date
                schedule_date = date.today().isoformat()
            data["ScheduleDate"] = schedule_date

        return data

    # ---- Order Management ----

    def get_orders(self, page: int = 1, page_size: int = 10) -> Dict:
        """Get list of carrier orders."""
        return self._post("Order/GetAllOrderOfCarrier", {
            "PageNumber": page,
            "PageSize": page_size,
        })

    def get_current_orders(self) -> Dict:
        """Get active 'Now' orders."""
        return self._post("Order/GetNowOnGoingOrders", {})

    def get_scheduled_orders(self) -> Dict:
        """Get active scheduled orders."""
        return self._post("Order/GetScheduledOnGoingOrders", {})

    def get_order_detail(self, order_id: int) -> Dict:
        """Get full detail for a specific order."""
        return self._get(f"Order/GetOrderDetailByOrderID/{order_id}")

    def get_order_status(self, order_id: int) -> Dict:
        """Get current status of an order."""
        return self._get(f"Order/GetOrderStatusById/{order_id}")

    def cancel_order(self, order_id: int, reason: str = "") -> Dict:
        """Cancel an order."""
        return self._post("Order/MarkAsCancelled", {
            "OrderID": order_id,
            "Reason": reason,
        })

    # ---- Quick Orders (Templates) ----

    def get_quick_orders(self) -> Dict:
        """Get saved quick order templates."""
        return self._get("PlaceOrder/GetQuickOrderList")

    def get_quick_order_by_id(self, quick_order_id: int) -> Dict:
        """Get a specific quick order template."""
        return self._post("PlaceOrder/GetQuickOrderByID", {
            "QuickOrderID": quick_order_id,
        })

    def save_quick_order(self, order_data: Dict) -> Dict:
        """Save an order as a quick order template."""
        return self._post("PlaceOrder/AddQuickOrder", order_data)

    # ---- Drivers ----

    def get_carrier_drivers(self) -> Dict:
        """Get all carrier's own drivers."""
        return self._get("CarrierDriver/GetAllDrivers")

    def get_active_drivers(self) -> Dict:
        """Get only active carrier drivers."""
        return self._get("CarrierDriver/GetActiveCarrierDrivers")

    def get_preferred_drivers(self) -> Dict:
        """Get preferred network drivers."""
        return self._get("RelayDriver/GetPreferredNetworkDriver")

    def search_available_drivers(self, criteria: Dict = None) -> Dict:
        """Search for available relay drivers."""
        return self._post("RelayDriver/SearchAvailableDrivers", criteria or {})

    # ---- Multi Driver Blocks ----

    def get_multi_driver_blocks(self) -> Dict:
        """Get multi driver blocks."""
        return self._get("MultiDriverBlock/Get")

    def create_relay_from_mdb(self, block_id: int) -> Dict:
        """Create a relay order from a multi driver block."""
        return self._post(f"PlaceOrder/NewRelayFromMultiDriverBlock/{block_id}")

    # ---- Carrier Info ----

    def get_carrier_detail(self) -> Dict:
        """Get carrier profile details."""
        return self._get("Carrier/GetCarrierDetail/0")

    def get_dashboard_counts(self) -> Dict:
        """Get dashboard counts."""
        return self._get("Carrier/GetCounts")

    def get_notification_count(self) -> Dict:
        """Get notification count."""
        return self._get("Carrier/GetAllNotificationCount")

    # ---- Form Type Descriptions ----

    @staticmethod
    def get_form_types() -> Dict[str, Dict]:
        """
        Return descriptions of all available form types for the LLM.
        The LLM uses this to decide which form to use based on user context.
        """
        return {
            "quick_entry": {
                "name": "Quick Entry",
                "description": "Fastest way to place an order. Minimal required fields. Best for simple, straightforward dispatches where you know the basics (addresses, pay type).",
                "use_when": [
                    "User wants to quickly dispatch a driver",
                    "Simple pickup/delivery with minimal details",
                    "User says 'quick', 'fast', 'simple', or 'just send a driver'",
                ],
                "route": "/client/place-order",
                "api_flags": {"IsOrderCreatedFromNewFlow": True, "FromSmartWizard": False},
            },
            "smart_wizard": {
                "name": "Smart Wizard",
                "description": "Guided step-by-step order placement. Walks through all options systematically. Best for users who need help or want to review each detail.",
                "use_when": [
                    "User is new or unsure about details",
                    "Complex order with multiple stops or special requirements",
                    "User says 'help me', 'guide me', 'step by step', or 'wizard'",
                ],
                "route": "/client/smart-wizard-place-order",
                "api_flags": {"IsOrderCreatedFromNewFlow": True, "FromSmartWizard": True},
            },
            "multi_driver_blocks": {
                "name": "Multi-Driver Blocks",
                "description": "Pre-scheduled driver blocks. For carriers who book drivers for recurring time blocks. Creates orders from existing block schedules.",
                "use_when": [
                    "User mentions 'block', 'recurring', 'scheduled blocks', or 'weekly'",
                    "User wants to assign drivers from pre-booked time blocks",
                    "Regular/recurring dispatches on a schedule",
                ],
                "route": "/client/multi-driver-blocks",
                "api_endpoint": "PlaceOrder/NewRelayFromMultiDriverBlock/{blockId}",
            },
            "classic_entry": {
                "name": "Classic Entry",
                "description": "Assign order to your own fleet driver. Uses CarrierDriverID instead of searching Relay network. Best when you know exactly which of YOUR drivers to send.",
                "use_when": [
                    "User wants to assign their OWN driver (not a Relay driver)",
                    "User mentions a specific driver by name",
                    "User says 'my driver', 'our driver', 'fleet', or 'assign to [name]'",
                ],
                "route": "/client/place-order",
                "api_flags": {"CarrierDriverID": "required", "CarrierDriverName": "required"},
            },
        }

    def get_form_context(self) -> Dict:
        """
        Get complete context for the LLM: form types, reference data, and carrier info.
        This replaces the Playwright-based page analysis.
        """
        context = {
            "form_types": self.get_form_types(),
            "reference_data": {},
            "carrier": {},
        }

        try:
            context["reference_data"]["task_types"] = self.get_task_types()
        except Exception:
            pass

        try:
            context["reference_data"]["trailer_types"] = self.get_trailer_types()
        except Exception:
            pass

        try:
            context["reference_data"]["endorsement_types"] = self.get_endorsement_types()
        except Exception:
            pass

        try:
            context["carrier"] = self.get_carrier_detail()
        except Exception:
            pass

        try:
            context["reference_data"]["can_place_orders"] = self.check_place_order_allowed()
        except Exception:
            pass

        return context


# ---- CLI for testing ----

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Relay On Demand API Client")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("login", help="Test login")
    sub.add_parser("context", help="Get full form context for LLM")
    sub.add_parser("task-types", help="Get task types")
    sub.add_parser("trailer-types", help="Get trailer types")
    sub.add_parser("endorsement-types", help="Get endorsement types")
    sub.add_parser("orders", help="Get current orders")
    sub.add_parser("drivers", help="Get carrier drivers")
    sub.add_parser("quick-orders", help="Get quick order templates")
    sub.add_parser("mdb", help="Get multi driver blocks")
    sub.add_parser("form-types", help="Show form type descriptions")
    sub.add_parser("check-order", help="Check if placing orders is allowed")

    p_detail = sub.add_parser("order-detail", help="Get order detail")
    p_detail.add_argument("order_id", type=int)

    args = parser.parse_args()

    api = RelayAPI()

    if args.command == "form-types":
        print(json.dumps(RelayAPI.get_form_types(), indent=2))
        sys.exit(0)

    # All other commands need auth
    login_result = api.login()
    if not login_result["success"]:
        print(json.dumps(login_result, indent=2))
        sys.exit(1)
    print(f"Logged in as {login_result['carrier_name']}", file=sys.stderr)

    if args.command == "login":
        print(json.dumps(login_result, indent=2))
    elif args.command == "context":
        print(json.dumps(api.get_form_context(), indent=2))
    elif args.command == "task-types":
        print(json.dumps(api.get_task_types(), indent=2))
    elif args.command == "trailer-types":
        print(json.dumps(api.get_trailer_types(), indent=2))
    elif args.command == "endorsement-types":
        print(json.dumps(api.get_endorsement_types(), indent=2))
    elif args.command == "orders":
        print(json.dumps(api.get_current_orders(), indent=2))
    elif args.command == "drivers":
        print(json.dumps(api.get_carrier_drivers(), indent=2))
    elif args.command == "quick-orders":
        print(json.dumps(api.get_quick_orders(), indent=2))
    elif args.command == "mdb":
        print(json.dumps(api.get_multi_driver_blocks(), indent=2))
    elif args.command == "check-order":
        print(json.dumps(api.check_place_order_allowed(), indent=2))
    elif args.command == "order-detail":
        print(json.dumps(api.get_order_detail(args.order_id), indent=2))
    else:
        parser.print_help()
