from flask import jsonify, request  # type: ignore
from src.trmeric_database.dao import PinBoardDao
import traceback

class PinsController:
    def listPins(self):
        try:
            # Get user_id from decoded token
            user_id = request.decoded.get("user_id")
            if not user_id:
                return jsonify({"error": "Unauthorized: User ID not provided"}), 401

            # Fetch headers and pins from DAO
            headers, result = PinBoardDao.listFullPinsDetails(user_id=user_id)
            
            # Group pins by header
            grouped_pins = {header.get("label", "General"): [] for header in headers}  # Initialize all headers
            for pin in result:
                header = pin.get("header", "General")
                # Ensure only valid pins are included
                if pin.get("question") and pin.get("answer"):
                    grouped_pins[header].append({
                        "id": str(pin.get("id")),  # Ensure ID is string
                        "question": pin.get("question"),
                        "answer": pin.get("answer"),
                        "timestamp": pin.get("timestamp", ""),
                        "category": pin.get("category"),
                        "header_pin": pin.get("pin_text")
                    })
            
            # Convert to list of { header, pins }
            grouped_response = [
                {"header": header, "pins": pins}
                for header, pins in grouped_pins.items()
            ]
            
            return jsonify(grouped_response), 200
        
        except Exception as e:
            print(f"Exception in listPins: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"Failed to fetch pins: {str(e)}"}), 500