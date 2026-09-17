"""Synchronous HTTP transport and typed read operations for otsdaq."""

from __future__ import annotations

import json
import warnings
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from .models import (
    FEMacro,
    OtsdaqHTTPError,
    OtsdaqProtocolError,
    OtsdaqResponse,
    OtsdaqTransportError,
)
from .settings import InstanceConfig

LID_GATEWAY = 200
LID_CONSOLE = 260
LID_CONFIG = 281
LID_SLOW_CONTROLS = 282
LID_TFM = 302
LID_MACRO_MAKER = 800


def _normalized_element(element: ET.Element) -> Dict[str, Any]:
    node: Dict[str, Any] = {}
    if element.attrib:
        node["@attributes"] = dict(element.attrib)
    text = (element.text or "").strip()
    if text:
        node["#text"] = text
    for child in list(element):
        value = _normalized_element(child)
        if child.tag in node:
            if not isinstance(node[child.tag], list):
                node[child.tag] = [node[child.tag]]
            node[child.tag].append(value)
        else:
            node[child.tag] = value
    return node


def _simple_element(element: ET.Element) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(element.attrib)
    text = (element.text or "").strip()
    if text:
        result["text"] = text
    for child in list(element):
        value: Any = _simple_element(child)
        if set(value) == {"value"}:
            value = value["value"]
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def _embedded_json(data: Mapping[str, Any], field: str = "JSON") -> Any:
    if field not in data:
        raise OtsdaqProtocolError("otsdaq response DATA is missing %s" % field)
    try:
        return json.loads(str(data[field]))
    except (TypeError, ValueError) as exc:
        raise OtsdaqProtocolError("otsdaq response contains invalid JSON in %s" % field) from exc


def _parse_count(tokens: Sequence[str], index: int, context: str) -> Tuple[int, int]:
    if index >= len(tokens):
        raise OtsdaqProtocolError("truncated %s macro record" % context)
    try:
        count = int(tokens[index])
    except ValueError as exc:
        raise OtsdaqProtocolError(
            "invalid argument count %r in %s macro record" % (tokens[index], context)
        ) from exc
    if count < 0:
        raise OtsdaqProtocolError("negative argument count in %s macro record" % context)
    return count, index + 1


class OtsdaqClient:
    """Client for the observed Mu2e otsdaq HTTP API."""

    def __init__(
        self, instance: InstanceConfig, session: Optional[requests.Session] = None
    ) -> None:
        self.instance = instance
        self.session = session or requests.Session()

    def request(
        self,
        request_type: str,
        *,
        lid: int = LID_GATEWAY,
        service: Optional[str] = None,
        query: Optional[Mapping[str, Any]] = None,
        form: Optional[Mapping[str, Any]] = None,
        handler: str = "request",
        require_data: bool = True,
    ) -> OtsdaqResponse:
        """POST an otsdaq request and retain exact and normalized XML."""
        if handler not in ("request", "state-machine"):
            raise OtsdaqProtocolError("unknown otsdaq handler %r" % handler)
        origin = self.instance.origin_for(lid, service)
        base = "%s/urn:xdaq-application:lid=%d" % (origin, lid)
        params: Dict[str, Any] = dict(query or {})
        if handler == "request":
            url = base + "/Request"
            params = {"RequestType": request_type, **params}
        else:
            url = base + "/StateMachineXgiHandler"
            params = {"StateMachine": request_type, **params}
        body: Dict[str, Any] = dict(form or {})
        # The observed otsdaq client authenticates Configuration Supervisor
        # requests this way. Do not spread that credential to other origins.
        if lid == LID_CONFIG and self.instance.cookie_code and "CookieCode" not in body:
            body["CookieCode"] = self.instance.cookie_code

        try:
            with warnings.catch_warnings():
                if not self.instance.requests_verify:
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                response = self.session.post(
                    url,
                    params=params,
                    data=body,
                    timeout=self.instance.timeout,
                    verify=self.instance.requests_verify,
                )
        except requests.RequestException as exc:
            raise OtsdaqTransportError(
                "%s (instance %s, LID %d, RequestType %s)"
                % (exc, self.instance.name, lid, request_type)
            ) from exc
        if not 200 <= response.status_code < 300:
            raise OtsdaqHTTPError(
                "HTTP %d from instance %s, LID %d, RequestType %s"
                % (response.status_code, self.instance.name, lid, request_type)
            )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise OtsdaqProtocolError(
                "invalid XML from instance %s, LID %d, RequestType %s"
                % (self.instance.name, lid, request_type)
            ) from exc
        if root.tag != "ROOT":
            raise OtsdaqProtocolError("otsdaq response root is <%s>, expected <ROOT>" % root.tag)
        data_element = root.find("DATA")
        if require_data and data_element is None:
            raise OtsdaqProtocolError("otsdaq response is missing <ROOT>/<DATA>")
        data = _simple_element(data_element) if data_element is not None else None
        self._raise_server_error(data, root)
        return OtsdaqResponse(
            status_code=response.status_code,
            url=response.url,
            xml=response.text,
            normalized={root.tag: _normalized_element(root)},
            data=data,
        )

    @staticmethod
    def _raise_server_error(data: Optional[Mapping[str, Any]], root: ET.Element) -> None:
        for element in root.findall(".//Error") + root.findall(".//ERROR"):
            message = element.attrib.get("value") or (element.text or "").strip()
            if message:
                raise OtsdaqProtocolError("otsdaq error: %s" % message)
        if not data:
            return
        if str(data.get("state_transition_attempted", "1")) == "0":
            raise OtsdaqProtocolError(
                "otsdaq error: %s"
                % data.get("state_transition_attempted_err", "transition was rejected")
            )
        for key in ("Error", "error", "ErrorMessage", "error_message"):
            value = data.get(key)
            if value not in (None, "", "0", "false", "False"):
                raise OtsdaqProtocolError("otsdaq error: %s" % value)

    def current_state(self) -> Dict[str, Any]:
        return self._data("getCurrentState", lid=LID_GATEWAY)

    def run_info(self, run_number: int = 0) -> Dict[str, Any]:
        data = self._data(
            "getRunInfo", lid=LID_GATEWAY, query={"RunNumber": str(run_number)}
        )
        if "plugin" in data and isinstance(data["plugin"], str):
            try:
                data["plugin"] = json.loads(data["plugin"])
            except ValueError as exc:
                raise OtsdaqProtocolError("getRunInfo plugin contains invalid JSON") from exc
        return data

    def daq_report(self) -> Dict[str, Any]:
        return self._data("getDAQReport", lid=LID_TFM)

    def daq_state(self) -> Dict[str, Any]:
        data = self._data("getDAQState", lid=LID_TFM)
        for key, value in list(data.items()):
            if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                try:
                    data[key] = json.loads(value)
                except ValueError as exc:
                    raise OtsdaqProtocolError(
                        "getDAQState field %s contains invalid JSON" % key
                    ) from exc
        return data

    def macro_list(self) -> List[FEMacro]:
        response = self.request("getFEMacroList", lid=LID_MACRO_MAKER)
        try:
            root = ET.fromstring(response.xml)
        except ET.ParseError as exc:  # request() already validated this
            raise OtsdaqProtocolError("invalid macro-list XML") from exc
        macros: List[FEMacro] = []
        for element in root.findall(".//FEMacros"):
            value = element.attrib.get("value")
            if value is None:
                raise OtsdaqProtocolError("FEMacros element is missing value")
            macros.extend(self._parse_fe_macro_record(value))
        for tag, macro_type in (("PublicMacro", "public"), ("PrivateMacro", "private")):
            for element in root.findall(".//" + tag):
                value = element.attrib.get("value")
                if value is None:
                    raise OtsdaqProtocolError("%s element is missing value" % tag)
                macros.append(self._parse_stored_macro_record(value, macro_type))
        return macros

    def pv_list(self) -> Any:
        return self._json_data("getList")

    def pv_data(self, pv_names: Iterable[str]) -> Any:
        return self._json_data("getPvData", pv_names)

    def pv_settings(self, pv_names: Iterable[str]) -> Any:
        return self._json_data("getPVSettings", pv_names)

    def alarms(self, pv_names: Iterable[str] = ()) -> Any:
        return self._json_data("getLastAlarmsData", pv_names)

    def alarm_checks(self) -> Any:
        return self._json_data("getAlarmsCheck")

    def console_messages(self, last_count: int = 0) -> Dict[str, Any]:
        return self._data(
            "GetConsoleMsgs", lid=LID_CONSOLE, form={"lcount": str(last_count)}
        )

    def system_messages(self, history: bool = False) -> Dict[str, Any]:
        data = self._data(
            "getSystemMessages",
            lid=LID_GATEWAY,
            form={"history": "true"} if history else {},
        )
        encoded = data.get("systemMessages")
        if isinstance(encoded, str):
            from urllib.parse import unquote

            parts = unquote(encoded).split("|") if encoded else []
            data["systemMessages"] = [
                {"time": parts[i], "message": parts[i + 1]}
                for i in range(0, len(parts) - 1, 2)
            ]
        return data

    def _data(self, request_type: str, **kwargs: Any) -> Dict[str, Any]:
        data = self.request(request_type, **kwargs).data
        if data is None:
            raise OtsdaqProtocolError("otsdaq response has no DATA payload")
        return data

    def _json_data(
        self, request_type: str, pv_names: Optional[Iterable[str]] = None
    ) -> Any:
        form: Dict[str, Any] = {}
        if pv_names is not None:
            names = list(pv_names)
            form["pvList"] = ",".join(names) + ","
        data = self._data(request_type, lid=LID_SLOW_CONTROLS, form=form)
        return _embedded_json(data)

    @staticmethod
    def _parse_fe_macro_record(value: str) -> List[FEMacro]:
        tokens = value.split(":")
        if len(tokens) < 4:
            raise OtsdaqProtocolError("truncated FEMacros record: %r" % value)
        supervisor, lid_text, fe_class, fe_uid = tokens[:4]
        try:
            lid = int(lid_text)
        except ValueError as exc:
            raise OtsdaqProtocolError("invalid FE macro LID %r" % lid_text) from exc
        index = 4
        out: List[FEMacro] = []
        while index < len(tokens):
            if index + 2 > len(tokens):
                raise OtsdaqProtocolError("truncated FE macro header for %s" % fe_uid)
            name, permissions = tokens[index : index + 2]
            index += 2
            input_count, index = _parse_count(tokens, index, fe_uid)
            if index + input_count > len(tokens):
                raise OtsdaqProtocolError("truncated FE macro inputs for %s" % name)
            inputs = list(tokens[index : index + input_count])
            index += input_count
            output_count, index = _parse_count(tokens, index, fe_uid)
            if index + output_count > len(tokens):
                raise OtsdaqProtocolError("truncated FE macro outputs for %s" % name)
            outputs = list(tokens[index : index + output_count])
            index += output_count
            out.append(
                FEMacro(
                    macro_type="fe",
                    name=name,
                    required_permissions=permissions,
                    inputs=inputs,
                    outputs=outputs,
                    supervisor=supervisor,
                    lid=lid,
                    fe_class=fe_class,
                    fe_uid=fe_uid,
                )
            )
        return out

    @staticmethod
    def _parse_stored_macro_record(value: str, macro_type: str) -> FEMacro:
        tokens = value.split(":")
        if len(tokens) < 3:
            raise OtsdaqProtocolError("truncated %s macro record" % macro_type)
        name, permissions = tokens[:2]
        index = 2
        input_count, index = _parse_count(tokens, index, macro_type)
        if index + input_count > len(tokens):
            raise OtsdaqProtocolError("truncated %s macro inputs" % macro_type)
        inputs = list(tokens[index : index + input_count])
        index += input_count
        output_count, index = _parse_count(tokens, index, macro_type)
        if index + output_count != len(tokens):
            raise OtsdaqProtocolError("malformed %s macro outputs" % macro_type)
        outputs = list(tokens[index : index + output_count])
        return FEMacro(
            macro_type=macro_type,
            name=name,
            required_permissions=permissions,
            inputs=inputs,
            outputs=outputs,
        )
