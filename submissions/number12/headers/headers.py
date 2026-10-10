from enum import Enum

class ServiceType(Enum):
    TYPE_3 = "type_3"
    TYPE_4 = "type_4"
    TYPE_4S = "type_4s"
    TYPE_4M = "type_4m"
    TYPE_5 = "type_5"
    UNKNOWN = "UNKNOWN"

class Service:
    def __init__(self, type: ServiceType, number: str):
        self.type = type
        self.number = number

class Performer:
    def __init__(self, number: str, has_signature: bool):
        self.number = number
        self.has_signature = has_signature

class Invoice:
    def __init__(self, tier_number: str, 
                 lot_number: str, 
                 invoice_number: str, 
                 client_number: str, 
                 total_local_service_fee: int, 
                 total_outsider_service_fee: int,
                 services: list[Service]):
        
        self.tier_number = tier_number
        self.lot_number = lot_number
        self.invoice_number = invoice_number # Common to all sub invoices
        self.client_number = client_number

        self.total_local_service_fee = total_local_service_fee
        self.total_outsider_service_fee = total_outsider_service_fee

        self.services = services

class Lot:
    def __init__(self, number: str, invoices: list[Invoice]):
        self.number = number
        self.invoices = invoices

class Cerfa:
    def __init__(self, cerfa_identifier: str,
                cerfa_code: str,
                performers: list[Performer],
                tier_number: str,
                lot_number: str,
                invoice_number: str,
                client_number: str,
                services: list[Service],
                total_local_service_fee: int,
                total_outsider_service_fee: int,
                total_service_fee: int,
                has_signature: bool
                ):
        
        self.cerfa_identifier = cerfa_identifier
        self.cerfa_code = cerfa_code

        self.performers = performers

        self.tier_number = tier_number
        self.lot_number = lot_number
        self.invoice_number = invoice_number # Common to all sub invoices
        self.client_number = client_number
        self.services = services
        self.total_local_service_fee = total_local_service_fee
        self.total_outsider_service_fee = total_outsider_service_fee
        self.total_service_fee = total_service_fee
        self.has_signature = has_signature # Director's signature
        
