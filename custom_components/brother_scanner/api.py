import uuid
import aiohttp
import re


# --- SOAP XML templates ---
GET_SCANNER_STATUS_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/GetScannerElements</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:{fromid}</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:GetScannerElementsRequest>
      <sca:RequestedElements>
        <sca:Name>sca:ScannerStatus</sca:Name>
      </sca:RequestedElements>
    </sca:GetScannerElementsRequest>
  </soap:Body>
</soap:Envelope>
"""

CREATE_SCAN_JOB_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/CreateScanJob</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:python-client</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:CreateScanJobRequest>
      <sca:ScanTicket>
        <sca:JobDescription>
          <sca:JobName>Python Scan Job</sca:JobName>
          <sca:JobOriginatingUserName>Python Client</sca:JobOriginatingUserName>
          <sca:JobInformation>Scanning in auto mode..</sca:JobInformation>
        </sca:JobDescription>
        <sca:DocumentParameters>
          <sca:Format sca:MustHonor="true">exif</sca:Format>
        </sca:DocumentParameters>
      </sca:ScanTicket>
    </sca:CreateScanJobRequest>
  </soap:Body>
</soap:Envelope>
"""

RETRIEVE_IMAGE_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:sca="http://schemas.microsoft.com/windows/2006/08/wdp/scan">
  <soap:Header>
    <wsa:To>{url}</wsa:To>
    <wsa:Action>http://schemas.microsoft.com/windows/2006/08/wdp/scan/RetrieveImage</wsa:Action>
    <wsa:MessageID>urn:uuid:{msgid}</wsa:MessageID>
    <wsa:ReplyTo>
      <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:From>
      <wsa:Address>urn:uuid:python-client</wsa:Address>
    </wsa:From>
  </soap:Header>
  <soap:Body>
    <sca:RetrieveImageRequest>
      <sca:JobId>{jobid}</sca:JobId>
      <sca:JobToken>{jobtoken}</sca:JobToken>
      <sca:DocumentDescription>
        <sca:DocumentName>Python Scan</sca:DocumentName>
      </sca:DocumentDescription>
    </sca:RetrieveImageRequest>
  </soap:Body>
</soap:Envelope>
"""


# --- Helpers ---
def make_uuid() -> str:
    return str(uuid.uuid4())


async def async_soap_request(
    session: aiohttp.ClientSession, url: str, xml: str
) -> bytes:
    headers = {"Content-Type": "application/soap+xml"}
    async with session.post(url, data=xml.encode("utf-8"), headers=headers) as resp:
        resp.raise_for_status()
        return await resp.read()


def extract_jpeg_from_mtom(response_bytes: bytes) -> bytes:
    # Detect boundary from Content-Type
    m = re.search(rb"^--([^\r\n]+)", response_bytes, re.MULTILINE)
    if not m:
        raise Exception("MIME boundary not found in response")
    boundary = m.group(1)
    parts = response_bytes.split(b"--" + boundary)
    for part in parts:
        if b"Content-Type: image/jpeg" in part:
            split = re.split(rb"\r?\n\r?\n", part, maxsplit=1)
            if len(split) == 2:
                return split[1].strip().rstrip(b"--").strip()
    raise Exception("JPEG not found in MTOM response")


# --- Main API function ---
async def scan_jpeg(ip: str) -> bytes:
    # return b"\xff\xd8\xff\xe0" + b"DUMMYJPEGDATA" + b"\xff\xd9"
    url = f"http://{ip}/WebServices/ScannerService"
    async with aiohttp.ClientSession() as session:
        # 1. Ensure idle
        state_xml = GET_SCANNER_STATUS_XML.format(
            url=url, msgid=make_uuid(), fromid=make_uuid()
        )
        resp_bytes = await async_soap_request(session, url, state_xml)
        m = re.search(rb"<wscn:ScannerState>(.*?)</wscn:ScannerState>", resp_bytes)
        state = m.group(1).decode() if m else "Unknown"
        if state.lower() != "idle":
            raise Exception(f"Scanner not idle (state={state})")

        # 2. Create scan job
        xml = CREATE_SCAN_JOB_XML.format(url=url, msgid=make_uuid())
        resp_bytes = await async_soap_request(session, url, xml)
        jid = re.search(rb"<wscn:JobId>(\d+)</wscn:JobId>", resp_bytes)
        jtok = re.search(rb"<wscn:JobToken>(.*?)</wscn:JobToken>", resp_bytes)
        if not jid or not jtok:
            raise Exception("Failed to create scan job")
        jobid, jobtoken = jid.group(1).decode(), jtok.group(1).decode()

        # 3. Retrieve image
        xml = RETRIEVE_IMAGE_XML.format(
            url=url, msgid=make_uuid(), jobid=jobid, jobtoken=jobtoken
        )
        resp_bytes = await async_soap_request(session, url, xml)
        return extract_jpeg_from_mtom(resp_bytes)
