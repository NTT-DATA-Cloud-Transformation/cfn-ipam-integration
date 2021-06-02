#!/usr/bin/env python3

import os

from mock import Mock
from netbox_function import app


def test_get_netbox():
    os.environ["NETBOX_URL"] = "http://localhost:8000/"
    os.environ["NETBOX_TOKEN"] = "0123456789abcdef0123456789abcdef01234567"

    nb = app.get_netbox()
    assert isinstance(nb, object)  # pynetbox.core.api.Api


def test_make_blocks():
    # Mock the use of the NetBox SDK, used as follows.
    #
    #     prefix = nb.ipam.prefixes.get(
    #         q=parent.network_address,
    #         mask_length=parent.prefixlen,
    #     )
    #
    #     vpc = ipaddress.ip_network(
    #         prefix.available_prefixes.create(
    #             {"prefix_length": int(p["VPC"]["BlockSize"])}
    #         )["prefix"]
    #     )

    nb = Mock(
        ipam=Mock(
            prefixes=Mock(
                get=Mock(
                    return_value=Mock(
                        available_prefixes=Mock(
                            create=Mock(
                                return_value={
                                    "prefix": "172.31.0.0/16",
                                }
                            )
                        )
                    )
                )
            )
        )
    )

    parameters = {
        "ParentPrefix": "172.16.0.0/12",
        "VPC": {"Name": "TestVPC", "BlockSize": "16"},
        "Subnets": [
            {"Name": "TestSubnet0", "BlockSize": "20"},
            {"Name": "TestSubnet1", "BlockSize": "20"},
            {"Name": "TestSubnet2", "BlockSize": "20"},
            {"Name": "TestSubnet3", "BlockSize": "20"},
            {"Name": "TestSubnet4", "BlockSize": "20"},
            {"Name": "TestSubnet5", "BlockSize": "20"},
            {"Name": "TestSubnet6", "BlockSize": "20"},
            {"Name": "TestSubnet7", "BlockSize": "20"},
            {"Name": "TestSubnet8", "BlockSize": "20"},
        ],
    }

    app.make_blocks(parameters, nb)

    assert app.helper.Data["TestVPC.CidrBlock"] == "172.31.0.0/16"
    assert app.helper.Data["TestSubnet0.CidrBlock"] == "172.31.0.0/20"
    assert app.helper.Data["TestSubnet1.CidrBlock"] == "172.31.16.0/20"
    assert app.helper.Data["TestSubnet2.CidrBlock"] == "172.31.32.0/20"
    assert app.helper.Data["TestSubnet3.CidrBlock"] == "172.31.48.0/20"
    assert app.helper.Data["TestSubnet4.CidrBlock"] == "172.31.64.0/20"
    assert app.helper.Data["TestSubnet5.CidrBlock"] == "172.31.80.0/20"
    assert app.helper.Data["TestSubnet6.CidrBlock"] == "172.31.96.0/20"
    assert app.helper.Data["TestSubnet7.CidrBlock"] == "172.31.112.0/20"
    assert app.helper.Data["TestSubnet8.CidrBlock"] == "172.31.128.0/20"
