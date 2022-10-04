# -*- coding: utf-8 -*-
__author__ = 'Nikolay Mamashin (mamashin@gmail.com)'

from loguru import logger
from services import read_json_file, get_dhcp_binding, save_result, compare_dict, zbx_host_create, \
    zbx_find_host, zbx_delete_host, zbx_update_host, zbx_get_trigger, zbx_set_parent_trigger
import urllib3
from pathlib import Path

urllib3.disable_warnings()
logger.remove()
logger.add(f"{Path.cwd()}/debug.log", format="{time} {level} {message}",
           filter=lambda record: record["level"].name == "DEBUG")


if __name__ == '__main__':
    for mt_item in read_json_file('mt_hosts.json'):
        clean_dhcp_list = get_dhcp_binding(mt_item.get('host'), mt_item.get('login'), mt_item.get('pass'))
        prev_data = read_json_file(f'{mt_item.get("loc")}.json')
        if diff_data := list(compare_dict(prev_data, clean_dhcp_list)):
            logger.debug(diff_data)
            for dt in diff_data:
                cmd = dt[0]  # diff result -> remove, add, change
                if cmd == 'remove':
                    for remove_item in dt[2]:
                        logger.debug(f'remove ip - {remove_item[0]}')
                        if host_to_remove := zbx_find_host(remove_item[0]):
                            zbx_delete_host(host_to_remove)
                if cmd == 'add':
                    for add_item in dt[2]:
                        logger.debug(f'add ip - {add_item[0]}, descr - {add_item[1]}')
                        create_result = zbx_host_create(add_item[0], add_item[1], mt_item.get("loc"))
                        if create_result.get('result'):
                            new_trigger_id = zbx_get_trigger(create_result.get('result').get('hostids')[0])
                            if new_trigger_id:
                                zbx_set_parent_trigger(new_trigger_id, mt_item.get("parent_trigger"))
                if cmd == 'change':
                    logger.debug(f'change ip - {dt[1][0]}, new data - {dt[2][1]}')
                    if host_to_update := zbx_find_host(dt[1][0]):
                        zbx_update_host(host_to_update, dt[2][1])
        save_result(clean_dhcp_list, f'data/{mt_item.get("loc")}.json')
