# -*- coding: utf-8 -*-
__author__ = 'Nikolay Mamashin (mamashin@gmail.com)'

import json
from pathlib import Path
from decouple import config # noqa
from pyzabbix import ZabbixAPI
import requests
from requests.auth import HTTPBasicAuth
from dictdiffer import diff
from loguru import logger


def read_json_file(filename):
    try:
        data = json.loads(Path(f'{Path.cwd()}/data', filename).read_text())
    except Exception as e:
        logger.debug(f"Oops. Cant open file - {e}")
        return {}
    return data


def get_dhcp_binding(host, mt_login, mt_pass):
    # payload = {'dynamic': 'false', 'disabled': 'false', '.proplist': 'address,comment'}
    # payload = {'dynamic': 'false', 'status': 'bound', '.proplist': 'address,mac-address,comment'}
    payload = {'dynamic': 'false', 'status': 'bound', '.proplist': 'address,comment'}
    mt_auth = HTTPBasicAuth(mt_login, mt_pass)
    try:
        leases_request = requests.get(f'https://{host}/rest/ip/dhcp-server/lease', params=payload, auth=mt_auth,
                                      verify=False)
    except Exception as e:
        logger.debug(f'Oops. Unable to connect - {e}')
        return []
    try:
        leases_json_list = leases_request.json()
    except Exception as e:
        logger.debug(f'Error to convert to JSON - {e}')
        return []

    result_dict = {}
    for single_lease in leases_json_list:  # remove .id key from answer
        if single_lease.get('comment') and single_lease.get('comment').startswith('#') and len(single_lease.get('comment')) > 2:
            result_dict[single_lease.get('address')] = single_lease.get('comment')[1:]

    return result_dict


def save_result(leases_list, file_name):
    with open(file_name, 'w') as out_file:
        json.dump(leases_list, out_file, sort_keys=True, indent=4, ensure_ascii=False)


def compare_dict(a, b):
    return diff(a, b)


def zbx_get_trigger(hostid) -> int:
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        get_trigger_result = zapi.do_request(
            method="trigger.get",
            params={
                "hostids": str(hostid),
                "tags": [{"tag": "state", "value": "fail", "operator": 0}],
                "output": ["triggerid"]
            }
        )
        logger.debug(f'Get trigger result: {get_trigger_result}')
        if get_trigger_result.get('result'):
            return int(get_trigger_result.get('result')[0].get('triggerid'))
    return 0


def zbx_set_parent_trigger(trigger_id, parent_trigger) -> None:
    logger.debug(f'{trigger_id=}, {parent_trigger=}')
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        parent_trigger_result = zapi.do_request(
            method="trigger.update",
            params={
                "triggerid": str(trigger_id),
                "dependencies": [{"triggerid": str(parent_trigger)}]
            }
        )
        logger.debug(f'Set parent trigger result: {parent_trigger_result}')


def zbx_find_host(host) -> int:
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        get_result = zapi.do_request(
            method="host.get",
            params={
                "filter": {
                    "host": [host]
                }
            }
        )
        if get_result.get('result'):
            logger.debug(f"Find host result - {int(get_result.get('result')[0].get('hostid'))}")
            return int(get_result.get('result')[0].get('hostid'))
        return 0


def zbx_host_create(ip, descr, location):
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        r = zapi.do_request(
            method="host.create",
            params={
                "host": ip,
                "name": descr,
                "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "10050"}],
                "groups": [{"groupid": f"{config('ZABBIX_GROUP_ID')}"}],
                "tags": [{"tag": "loc", "value": location}],
                "templates": [{"templateid": f"{config('ZABBIX_TEMPLATE_ID')}"}]
            }
        )
        logger.debug(f'Create new host: {r}')
        return r


def zbx_delete_host(host):
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        del_result = zapi.do_request(
            method="host.delete",
            params=[str(host)]
        )
        logger.debug(f'Delete result: {del_result}')


def zbx_update_host(host, descr):
    with ZabbixAPI(config('ZABBIX_SERVER_URL')) as zapi:
        zapi.login(config('ZABBIX_LOGIN'), config('ZABBIX_PASS'))
        update_result = zapi.do_request(
            method="host.update",
            params={
                "hostid": str(host),
                "name": descr
            }
        )
        logger.debug(f'Update result: {update_result}')
