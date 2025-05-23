import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import time
import uuid
import zipfile
import os
import json

# === Configuration ===
TRACCAR_DEVICES_URL = 'https://demo4.traccar.org/api/devices'
TRACCAR_POSITIONS_URL = 'https://demo4.traccar.org/api/positions'
TRACCAR_AUTH = ('your_username', 'your_password')  # Replace with actual Traccar credentials

OUTPUT_DIR = r'C:\Users\Mark\Desktop\test\gladefilehosting\BODS mock'
XML_PATH = os.path.join(OUTPUT_DIR, 'siri.xml')
ZIP_PATH = os.path.join(OUTPUT_DIR, 'siri.zip')
CACHE_PATH = os.path.join(OUTPUT_DIR, 'origin_time_cache.json')

# === Global Cache ===
origin_time_cache = {}

# === Helper Functions ===
def iso_time_now():
    return datetime.now(timezone.utc).isoformat()

def load_origin_time_cache():
    global origin_time_cache
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r') as f:
            origin_time_cache = json.load(f)

def save_origin_time_cache():
    with open(CACHE_PATH, 'w') as f:
        json.dump(origin_time_cache, f)

def build_vehicle_activity(position, attributes):
    now = iso_time_now()

    line_ref = attributes.get('lineRef', 'L1')
    direction_ref = attributes.get('directionRef', 'outbound')
    published_line_name = attributes.get('publishedLineName', line_ref)
    operator_ref = attributes.get('operatorRef', 'MDEM')
    origin_ref = attributes.get('originRef', '3390VB09')
    origin_name = attributes.get('originName', 'Travelshop')
    destination_ref = attributes.get('destinationRef', '3390BU01')
    destination_name = attributes.get('destinationName', 'Bulwell')
    journey_code = attributes.get('journeyCode', '1025')
    service_code = attributes.get('ticketMachineServiceCode', 'NOTTINGHAM')
    block_ref = attributes.get('blockRef', '1')
    vehicle_unique_id = attributes.get('vehicleUniqueId', str(position['deviceId']))
    dated_vehicle_journey_ref = attributes.get('datedVehicleJourneyRef')

    raw_departure_time = position.get('deviceTime')
    origin_aimed_departure_time = None
    destination_aimed_arrival_time = None

    if raw_departure_time:
        dt_origin = datetime.fromisoformat(raw_departure_time.replace('Z', '+00:00'))

        journey_key = dated_vehicle_journey_ref or f"{line_ref}_{direction_ref}_{dt_origin.strftime('%Y%m%d')}_{journey_code}"

        # Set the departure time if not already cached
        if journey_key not in origin_time_cache:
            origin_time_cache[journey_key] = dt_origin.isoformat()

        origin_aimed_departure_time = origin_time_cache[journey_key]
        destination_aimed_arrival_time = (datetime.fromisoformat(origin_aimed_departure_time) + timedelta(hours=1)).isoformat()

    root = ET.Element('VehicleActivity')
    ET.SubElement(root, 'RecordedAtTime').text = now
    ET.SubElement(root, 'ItemIdentifier').text = str(uuid.uuid4())
    valid_until = datetime.now(timezone.utc) + timedelta(minutes=6)
    ET.SubElement(root, 'ValidUntilTime').text = valid_until.isoformat()

    journey = ET.SubElement(root, 'MonitoredVehicleJourney')
    ET.SubElement(journey, 'LineRef').text = line_ref
    ET.SubElement(journey, 'DirectionRef').text = direction_ref

    frame = ET.SubElement(journey, 'FramedVehicleJourneyRef')
    ET.SubElement(frame, 'DataFrameRef').text = now.split("T")[0]
    ET.SubElement(frame, 'DatedVehicleJourneyRef').text = dated_vehicle_journey_ref or journey_key

    ET.SubElement(journey, 'PublishedLineName').text = published_line_name
    ET.SubElement(journey, 'OperatorRef').text = operator_ref
    ET.SubElement(journey, 'OriginRef').text = origin_ref
    ET.SubElement(journey, 'OriginName').text = origin_name
    ET.SubElement(journey, 'DestinationRef').text = destination_ref
    ET.SubElement(journey, 'DestinationName').text = destination_name

    if origin_aimed_departure_time:
        ET.SubElement(journey, 'OriginAimedDepartureTime').text = origin_aimed_departure_time
    if destination_aimed_arrival_time:
        ET.SubElement(journey, 'DestinationAimedArrivalTime').text = destination_aimed_arrival_time
    if 'bearing' in position:
        ET.SubElement(journey, 'Bearing').text = str(position['bearing'])

    location = ET.SubElement(journey, 'VehicleLocation')
    ET.SubElement(location, 'Longitude').text = str(position['longitude'])
    ET.SubElement(location, 'Latitude').text = str(position['latitude'])

    ET.SubElement(journey, 'BlockRef').text = block_ref
    ET.SubElement(journey, 'VehicleRef').text = str(position['deviceId'])

    extensions = ET.SubElement(root, 'Extensions')
    vj = ET.SubElement(extensions, 'VehicleJourney')
    op = ET.SubElement(vj, 'Operational')
    tm = ET.SubElement(op, 'TicketMachine')
    ET.SubElement(tm, 'TicketMachineServiceCode').text = service_code
    ET.SubElement(tm, 'JourneyCode').text = journey_code
    ET.SubElement(vj, 'VehicleUniqueId').text = vehicle_unique_id

    return root

def fetch_data():
    devices = requests.get(TRACCAR_DEVICES_URL, auth=TRACCAR_AUTH).json()
    positions = requests.get(TRACCAR_POSITIONS_URL, auth=TRACCAR_AUTH).json()
    device_map = {device['id']: device for device in devices}
    return [(pos, device_map.get(pos['deviceId'], {})) for pos in positions]

def update_xml():
    siri = ET.Element('Siri', attrib={
        'version': '2.0',
        'xmlns': 'http://www.siri.org.uk/siri',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': 'http://www.siri.org.uk/siri http://www.siri.org.uk/schema/2.0/xsd/siri.xsd'
    })

    delivery = ET.SubElement(siri, 'ServiceDelivery')
    timestamp = iso_time_now()
    ET.SubElement(delivery, 'ResponseTimestamp').text = timestamp
    ET.SubElement(delivery, 'ProducerRef').text = 'DepartmentForTransport'

    vmd = ET.SubElement(delivery, 'VehicleMonitoringDelivery')
    ET.SubElement(vmd, 'ResponseTimestamp').text = timestamp
    ET.SubElement(vmd, 'RequestMessageRef').text = str(uuid.uuid4())
    ET.SubElement(vmd, 'ValidUntil').text = timestamp
    ET.SubElement(vmd, 'ShortestPossibleCycle').text = 'PT5S'

    for position, device in fetch_data():
        attributes = device.get('attributes', {})
        vmd.append(build_vehicle_activity(position, attributes))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tree = ET.ElementTree(siri)
    tree.write(XML_PATH, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(XML_PATH, arcname='siri.xml')

    save_origin_time_cache()
    print(f"[{timestamp}] XML saved to {XML_PATH} and zipped as {ZIP_PATH}")

# === Main Loop ===
if __name__ == "__main__":
    load_origin_time_cache()
    while True:
        try:
            update_xml()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(10)
