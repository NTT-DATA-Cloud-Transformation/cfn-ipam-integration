#!/usr/bin/env python3

import ipaddress
import json
import logging
import os

import boto3
import crhelper
import pynetbox

logger = logging.getLogger(__name__)
helper = crhelper.CfnResource()


def get_netbox():
    ssm = boto3.client("ssm")

    # The NetBox endpoint and token can be explicitly set in the environment,
    # which can be useful for testing.
    url = os.environ.get("NETBOX_URL", None)
    token = os.environ.get("NETBOX_TOKEN", None)

    if url is None:
        url = ssm.get_parameter(Name=os.environ["PARAM_URL"], WithDecryption=True)["Parameter"]["Value"]

    if token is None:
        token = ssm.get_parameter(Name=os.environ["PARAM_TOKEN"], WithDecryption=True)["Parameter"]["Value"]

    logger.debug(f"NetBox URL <{url}>")
    logger.debug(f'NetBox Token <{token[0:7]}...>')

    logger.info(
        "Constructing the NetBox API object. If the Lambda function times "
        "out at this point, it likely means it is unable to communicate with "
        "AWS Systems Manager Parameter Store. "
        "Please refer to <https://aws.amazon.com/premiumsupport/knowledge-center/lambda-vpc-parameter-store/> "
        "for instructions on how to address this."
    )

    return pynetbox.api(url=url, token=token)


def check_input(p):
    if "ParentPrefix" not in p:
        raise Exception("Property ParentPrefix cannot be empty.")

    if "VPC" not in p:
        raise Exception("Property VPC cannot be empty.")

    if "Name" not in p["VPC"]:
        raise Exception("Property VPC.Name cannot be empty.")

    if "BlockSize" not in p["VPC"]:
        raise Exception("Property VPC.BlockSize cannot be empty.")

    if "Subnets" not in p:
        raise Exception("Property Subnets cannot be empty.")

    if type(p["Subnets"]) != list:
        raise Exception("Property Subnets must be a list of subnets.")

    for i in range(len(p["Subnets"])):
        if type(p["Subnets"][i]) != dict:
            raise Exception(f"Property Subnets[{i}] must be a subnet.")

        if "Name" not in p["Subnets"][i]:
            raise Exception(f"Property Subnets[{i}].Name cannot be empty.")

        if "BlockSize" not in p["Subnets"][i]:
            raise Exception(f"Property Subnets[{i}].BlockSize cannot be empty.")


# We fake the nested attributes here, to support syntax like,
#
#     Fn::GetAtt:
#       - <resourceName>
#       - <vpcName>.CidrBlock
#
#     !GetAtt <resourceName>.<vpcName>.CidrBlock
#     !GetAtt <resourceName>.<subnetName>.CidrBlock

def make_blocks(p, nb):
    parent = ipaddress.ip_network(p["ParentPrefix"])
    logger.debug(f"Requested parent prefix <{parent}>")

    # Create a new VPC prefix in NetBox, using the first available prefix
    # found under the parent prefix.
    prefix = nb.ipam.prefixes.get(q=parent.network_address, mask_length=parent.prefixlen)
    if prefix is None:
        raise Exception(f"Parent prefix {parent} is not defined in NetBox")
    logger.debug(f"NetBox parent prefix <{prefix}>")

    # The NetBox API will raise an exception if the prefix fails to create,
    # which will be caught by the CfnResource helper and passed to
    # CloudFormation as a resource error.
    vpc = ipaddress.ip_network(prefix.available_prefixes.create({"prefix_length": int(p["VPC"]["BlockSize"])})["prefix"])
    logger.debug(f"{p['VPC']['Name']}.CidrBlock <{vpc}>")
    helper.Data.update({f"{p['VPC']['Name']}.CidrBlock": str(vpc)})

    # The first subnet will start at the beginning of the VPC block.
    # Subsequent subnets will start at the first address following the
    # previous subnet.
    address = vpc.network_address

    for i in range(len(p["Subnets"])):
        # Generate a single subnet based on the first available address.
        subnet = next(ipaddress.IPv4Network((address, int(p["Subnets"][i]["BlockSize"]))).subnets(new_prefix=int(p["Subnets"][i]["BlockSize"])))
        logger.debug(f"{p['Subnets'][i]['Name']}.CidrBlock <{subnet}>")
        helper.Data.update({f"{p['Subnets'][i]['Name']}.CidrBlock": str(subnet)})

        # The next subnet will start at the next available address.
        address = subnet[-1] + 1


@helper.create
def create(event, context):
    logger.info("Received Create event")

    rp = event["ResourceProperties"]

    check_input(rp)
    make_blocks(rp, get_netbox())


@helper.update
def update(event, context):
    logger.info("Received Update event")


@helper.delete
def delete(event, context):
    logger.info("Received Delete event")


def handler(event, context):
    if "Records" in event:
        logger.debug("SNS event: " + json.dumps(event))
        event = json.loads(event["Records"][0]["Sns"]["Message"])

    logger.debug("Lambda event: " + json.dumps(event))
    helper(event, context)
