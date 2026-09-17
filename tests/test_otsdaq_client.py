"""Protocol and typed operation tests against the fake otsdaq origins."""

import json

import pytest

from fake_otsdaq import FakeOtsdaq
from mu2edaq_commandline_tools.otsdaq import (
    InstanceConfig,
    OtsdaqClient,
    OtsdaqHTTPError,
    OtsdaqProtocolError,
)


def client_for(fake, cookie=None):
    return OtsdaqClient(
        InstanceConfig(
            name="test",
            gateway_url=fake.origin("gateway"),
            slow_controls_url=fake.origin("slow-controls"),
            tfm_url=fake.origin("tfm"),
            timeout=1,
            verify_tls=True,
            cookie_code=cookie,
        )
    )


def json_xml(value):
    encoded = (
        json.dumps(value)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return '<ROOT><DATA JSON="%s"/></ROOT>' % encoded


def test_typed_reads_route_and_parse():
    with FakeOtsdaq() as fake:
        fake.add("gateway", "getCurrentState", '<ROOT><DATA state="Running"/></ROOT>')
        fake.add(
            "gateway",
            "getRunInfo",
            '<ROOT><DATA run_number="42" plugin="{&quot;mode&quot;:&quot;test&quot;}"/></ROOT>',
        )
        fake.add("tfm", "getDAQReport", '<ROOT><DATA report="healthy"/></ROOT>')
        fake.add(
            "tfm",
            "getDAQState",
            '<ROOT><DATA connected="true"><br value="{&quot;state&quot;:&quot;Running&quot;}"/></DATA></ROOT>',
        )
        fake.add("slow-controls", "getList", json_xml(["pv:a", "pv:b"]))
        fake.add("slow-controls", "getPvData", json_xml({"pv:a": {"value": 7}}))
        fake.add("slow-controls", "getPVSettings", json_xml({"pv:a": {"units": "V"}}))
        fake.add("slow-controls", "getLastAlarmsData", json_xml([{"pv": "pv:a"}]))
        fake.add("slow-controls", "getAlarmsCheck", json_xml({"ok": True}))
        fake.add("gateway", "GetConsoleMsgs", '<ROOT><DATA lcount="4"><message value="hi"/></DATA></ROOT>')
        fake.add(
            "gateway",
            "getSystemMessages",
            '<ROOT><DATA systemMessages="10%7Chello%7C11%7Cworld"/></ROOT>',
        )
        client = client_for(fake, cookie="secret")

        assert client.current_state()["state"] == "Running"
        assert client.run_info(42)["plugin"]["mode"] == "test"
        assert client.daq_report()["report"] == "healthy"
        assert client.daq_state()["br"]["state"] == "Running"
        assert client.pv_list() == ["pv:a", "pv:b"]
        assert client.pv_data(["pv:a"])["pv:a"]["value"] == 7
        assert client.pv_settings(["pv:a"])["pv:a"]["units"] == "V"
        assert client.alarms(["pv:a"])[0]["pv"] == "pv:a"
        assert client.alarm_checks()["ok"] is True
        assert client.console_messages(3)["message"] == "hi"
        assert client.system_messages()["systemMessages"][1]["message"] == "world"

        assert [request.role for request in fake.requests[2:5]] == [
            "tfm",
            "tfm",
            "slow-controls",
        ]
        run_request = fake.requests[1]
        assert run_request.query["RunNumber"] == ["42"]
        pv_request = next(
            item for item in fake.requests if item.query.get("RequestType") == ["getPvData"]
        )
        assert pv_request.form["pvList"] == ["pv:a,"]
        assert "CookieCode" not in pv_request.form


def test_cookie_is_sent_only_to_configuration_supervisor():
    with FakeOtsdaq() as fake:
        fake.add("gateway", "ConfigRead", "<ROOT><DATA/></ROOT>")
        fake.add("gateway", "GatewayRead", "<ROOT><DATA/></ROOT>")
        client = client_for(fake, cookie="secret")
        client.request("ConfigRead", lid=281)
        client.request("GatewayRead", lid=200)
        assert fake.requests[0].form["CookieCode"] == ["secret"]
        assert "CookieCode" not in fake.requests[1].form


def test_macro_inventory_parses_all_macro_types():
    body = (
        "<ROOT><DATA>"
        '<FEMacros value="sup:123:DTCFrontEndInterface:daq01DTC:'
        'DTC Read:1:1:address:1:readData:Reset:1:0:1:Status"/>'
        '<PublicMacro value="Public Check:1:1:target:1:result"/>'
        '<PrivateMacro value="My Check:1:0:0"/>'
        "</DATA></ROOT>"
    )
    with FakeOtsdaq() as fake:
        fake.add("gateway", "getFEMacroList", body)
        macros = client_for(fake).macro_list()
    assert [macro.macro_type for macro in macros] == ["fe", "fe", "public", "private"]
    assert macros[0].fe_uid == "daq01DTC"
    assert macros[0].inputs == ["address"]
    assert macros[1].name == "Reset"


def test_raw_response_preserves_xml_and_repeated_children():
    body = '<ROOT version="1"><DATA><item value="a"/><item value="b"/></DATA></ROOT>'
    with FakeOtsdaq() as fake:
        fake.add("gateway", "Anything", body)
        response = client_for(fake).request("Anything")
    assert response.xml == body
    items = response.normalized["ROOT"]["DATA"]["item"]
    assert [item["@attributes"]["value"] for item in items] == ["a", "b"]


@pytest.mark.parametrize(
    "status,body,error",
    [
        (500, "<ROOT><DATA/></ROOT>", OtsdaqHTTPError),
        (200, "not XML", OtsdaqProtocolError),
        (200, "<OTHER/>", OtsdaqProtocolError),
        (200, "<ROOT/>", OtsdaqProtocolError),
        (200, '<ROOT><DATA Error="bad request"/></ROOT>', OtsdaqProtocolError),
    ],
)
def test_protocol_failures_are_typed(status, body, error):
    with FakeOtsdaq() as fake:
        fake.add("gateway", "Failure", body, status=status)
        with pytest.raises(error):
            client_for(fake).request("Failure")


def test_invalid_embedded_json_is_rejected():
    with FakeOtsdaq() as fake:
        fake.add("slow-controls", "getList", '<ROOT><DATA JSON="{bad"/></ROOT>')
        with pytest.raises(OtsdaqProtocolError, match="invalid JSON"):
            client_for(fake).pv_list()


def test_malformed_macro_record_is_rejected():
    with FakeOtsdaq() as fake:
        fake.add(
            "gateway",
            "getFEMacroList",
            '<ROOT><DATA><FEMacros value="sup:not-a-lid:Class:UID"/></DATA></ROOT>',
        )
        with pytest.raises(OtsdaqProtocolError, match="invalid FE macro LID"):
            client_for(fake).macro_list()
