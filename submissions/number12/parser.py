import os
from headers.headers import *

def parse_invoice(filepath) -> list[Lot]:

    if not os.path.exists(filepath):
        print("The file doesn't exist")
        return None

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()

    except Exception as e:
        print(f"Unable to read file. Error : {e}")
        return None

    nb_lines = len(lines)
    if nb_lines < 6:
        print("Invalid format")
        return None

    i = 0
    lots: list[Lot] = []
    while i < nb_lines:
        
        if lines[i][0] == "1":
            lot_number: str = lines[i][19:22]
            tier_number: str = lines[i][1:10]
            invoices: list[Invoice] = []
        
        i += 1
        while i < nb_lines and lines[i][0] != "6":

            client_number: str = lines[i][11:24]
            invoice_number: str = lines[i][29:38].lstrip("0")
            services: list[Service] = []

            while i < nb_lines and lines[i][0] == "2":
                i += 1
            while i < nb_lines and lines[i][0] != "5":
                
                match lines[i][0]:
                    case "3":
                        if lines[i][38] != "S" and lines[i][35] != "H": 
                            if lines[i][55:60].strip() == "GHS":
                                number = lines[i][109:113]
                                services.append(Service(ServiceType.TYPE_3, number))
                    case "4":
                        match lines[i][35]:
                            case "S":
                                number = lines[i][119:123]
                                type = ServiceType.TYPE_4S   
                            case "M":
                                number = lines[i][42:55].strip()
                                type = ServiceType.TYPE_4M
                            case "B":
                                pass
                            case _:
                                number = lines[i][75:80].strip()
                                type = ServiceType.TYPE_4
                        
                        if (lines[i][35] != "B"):
                            services.append(Service(type, number))
                    
                    case _:
                        # Maybe raise an error here
                        pass

                i += 1

            total_local_service_fee = int(lines[i][41:49])
            total_outsider_service_fee = int(lines[i][57:65])

            invoices.append(Invoice(tier_number,
                        lot_number,
                        invoice_number,
                        client_number,
                        total_local_service_fee,
                        total_outsider_service_fee,
                        services
                        ))
                    
            i += 1

        lots.append(Lot(lot_number, invoices))
        i += 1

    return lots
